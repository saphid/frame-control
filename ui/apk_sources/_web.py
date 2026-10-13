"""Small HTTPS cache and APK downloader for public publisher sources."""
import hashlib, http.client, ipaddress, os, shutil, socket, ssl, tempfile, threading, time
import urllib.error, urllib.parse, urllib.request, zipfile
from email.utils import parsedate_to_datetime

import frame_host
from . import SourceError, SourceLimited

UA = 'FrameControl/0.1'
APK_CAP = 2 * 1024 ** 3  # cached APKs across all sources, least recently used go first
RECENT = 3600  # an APK used this recently may be about to be installed; never pruned
_use_lock = threading.Lock()  # pruning's final check and delete vs touch()/claim()
_in_use = {}  # APK path -> installs using it


def touch(path):
    """Mark a cached APK as just used; False if pruning already removed it."""
    with _use_lock:
        try:
            os.utime(str(path))
            return True
        except FileNotFoundError:
            return False


def claim(path):
    """Protect a downloaded APK from pruning until release(path)."""
    path = os.path.abspath(str(path))
    with _use_lock:
        os.utime(path)  # raises if it has gone
        _in_use[path] = _in_use.get(path, 0) + 1


def release(path):
    path = os.path.abspath(str(path))
    with _use_lock:
        if _in_use.get(path, 0) > 1:
            _in_use[path] -= 1
        else:
            _in_use.pop(path, None)
BACKOFF = 600  # seconds to leave a host alone after 403/429 without Retry-After
_limited = {}  # host -> time.time() before which we don't contact it
_limited_lock = threading.Lock()


def _host(url):
    return (urllib.parse.urlsplit(url).hostname or '').lower()


def throttle(url, headers=None):
    """Remember that url's host asked us to back off; return the delay in seconds."""
    headers = headers or {}
    now, delay = time.time(), None
    value = (headers.get('Retry-After') or '').strip()
    if value.isdigit():
        delay = int(value)
    elif value:
        try:
            delay = parsedate_to_datetime(value).timestamp() - now
        except (TypeError, ValueError, OverflowError):
            pass
    reset = headers.get('X-RateLimit-Reset') or ''
    if delay is None and headers.get('X-RateLimit-Remaining') == '0' and reset.isdigit():
        delay = int(reset) - now  # GitHub
    delay = min(max(delay if delay is not None else BACKOFF, 1), 6 * 3600)
    with _limited_lock:
        _limited[_host(url)] = max(_limited.get(_host(url), 0), now + delay)
    return delay


def wait_time(url):
    with _limited_lock:
        return max(0, _limited.get(_host(url), 0) - time.time())


def limited_error(name, seconds, hint=''):
    minutes = max(1, int(round(seconds / 60)))
    return SourceLimited('%s is limiting requests; try again in %d minute%s%s'
                         % (name, minutes, '' if minutes == 1 else 's', hint), seconds)


def cache():
    path = frame_host.cache_dir('apk-sources', 'publisher')
    os.makedirs(path, exist_ok=True)
    return str(path)


def prune():
    """Trim the download caches: APKs to APK_CAP by mtime, orphaned .part/temp files, old listings.

    Only the long-running app prunes (at start and after store downloads): claim() is
    in-process, so the CLIs never prune and so can't delete an APK the app is installing.
    """
    now, apks = time.time(), []
    for folder in (str(frame_host.cache_dir('apk-sources')), cache()):
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            path = os.path.join(folder, name)
            try:
                st = os.lstat(path)
                age = now - st.st_mtime
                if os.path.isdir(path) and not os.path.islink(path):
                    if name.startswith('tmp') and age > 86400:  # an interrupted F-Droid index download
                        shutil.rmtree(path, ignore_errors=True)
                elif (name.endswith('.part') and age > 86400) or (name.endswith('.data') and age > 7 * 86400):
                    os.remove(path)
                elif name.endswith('.apk'):
                    apks.append((st.st_mtime, st.st_size, path))
            except OSError:
                pass
    total = sum(size for _, size, _ in apks)
    for _, size, path in sorted(apks):
        if total <= APK_CAP:
            break
        with _use_lock:  # the scan is old news: check again right before deleting
            try:
                if os.path.abspath(path) in _in_use or time.time() - os.stat(path).st_mtime < RECENT:
                    continue
                os.remove(path)
                total -= size
            except OSError:
                pass


def checked_url(url, hosts):
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except (ValueError, TypeError) as e:
        raise SourceError('Source returned an invalid URL') from e
    if p.scheme != 'https' or p.username or p.password or port not in (None, 443) or p.hostname not in hosts:
        raise SourceError('Source returned an unexpected download URL')
    return url


class Redirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to hosts; an Authorization header never follows one."""

    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl, self.hosts)
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        if result:
            result.remove_header('Authorization')
        return result


def open_url(url, hosts, headers=None):
    checked_url(url, hosts)
    return urllib.request.build_opener(Redirect(hosts)).open(
        urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})}), timeout=60)


def read(url, hosts, headers=None, ttl=3600, name=None, hint=''):
    path = os.path.join(cache(), hashlib.sha256(url.encode()).hexdigest() + '.data')
    name = name or _host(url) or 'The source'

    def cached():
        if os.path.isfile(path):  # throttled: an older copy beats no results
            with open(path, 'rb') as f:
                return f.read()
    try:
        if os.path.isfile(path) and time.time() - os.path.getmtime(path) < ttl:
            with open(path, 'rb') as f:
                return f.read()
        wait = wait_time(url)
        if wait:
            data = cached()
            if data is None:
                raise limited_error(name, wait, hint)
            return data
        with open_url(url, hosts, headers) as r:
            data = r.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise SourceError('Source index is too large')
        fd, tmp = tempfile.mkstemp(dir=cache(), suffix='.part')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return data
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            delay = throttle(url, e.headers)
            data = cached()
            if data is None:
                raise limited_error(name, delay, hint) from e
            return data
        raise SourceError('Source HTTP error: ' + str(e.code)) from e
    except (OSError, ValueError) as e:
        raise SourceError('Could not read source: ' + str(e)) from e


def save_apk(response, digest=None):
    """Stream response (anything with read(n)) into the cache as a checked APK."""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=cache(), suffix='.part')
        h = hashlib.sha256()
        with os.fdopen(fd, 'wb') as f:
            size = 0
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                if size > 2 * 1024 ** 3:
                    raise SourceError('APK exceeds the 2 GiB download limit')
                h.update(chunk)
                f.write(chunk)
        actual = h.hexdigest()
        if digest and actual != digest:
            raise SourceError('SHA-256 mismatch; download discarded')
        with zipfile.ZipFile(tmp) as z:
            if 'AndroidManifest.xml' not in z.namelist():
                raise SourceError('Download is not an APK')
        path = os.path.join(cache(), actual + '.apk')
        os.replace(tmp, path)
        return {'apk': path, 'obb': [], 'sha256': actual, 'verified': bool(digest)}
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def apk(url, hosts, digest=None, name=None):
    name = name or _host(url)
    wait = wait_time(url)
    if wait:
        raise limited_error(name, wait)
    try:
        with open_url(url, hosts) as r:
            return save_apk(r, digest)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise limited_error(name, throttle(url, e.headers)) from e
        raise SourceError('Could not download APK: HTTP error ' + str(e.code)) from e
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        raise SourceError('Could not download APK: ' + str(e)) from e


def public_address(ip):
    """True for an address on the public internet: never loopback, private, link-local,
    shared (CGNAT), reserved or multicast, including IPv4 written oddly or mapped into IPv6."""
    try:
        a = ipaddress.ip_address(ip.split('%', 1)[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_global and not a.is_multicast


def resolve_public(host):
    """host's address for port 443, if every address it has is public; else SourceError."""
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as e:
        raise SourceError('Could not find the download server ' + host) from e
    if not addresses or not all(public_address(a[4][0]) for a in addresses):
        raise SourceError('The download server is on a private network address; refused')
    return addresses[0][4][:2]


def _public_connection(host, timeout):
    """A verified TLS connection to host:443, made to an address checked to be public.

    The checked address is the one connected to, so a second lookup can't swap in another."""
    return _connect(host, resolve_public(host), timeout)


def _connect(host, address, timeout):
    sock = socket.create_connection(address, timeout=timeout)
    try:
        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
    except BaseException:
        sock.close()
        raise
    conn = http.client.HTTPConnection(host, 443, timeout=timeout)
    conn.sock = sock
    return conn


def public_apk(url, name, redirects=3, timeout=60):
    """Download an APK from a public HTTPS host that no source lists in advance (itch.io's
    storage). No credentials are sent. Every hop, redirects included, is re-checked."""
    for _ in range(redirects + 1):
        try:
            p = urllib.parse.urlsplit(url)
            port = p.port
        except (ValueError, TypeError) as e:
            raise SourceError(name + ' returned an invalid download URL') from e
        if p.scheme != 'https' or not p.hostname or p.username or p.password or port not in (None, 443):
            raise SourceError(name + ' returned an unexpected download URL')
        wait = wait_time(url)
        if wait:
            raise limited_error(name, wait)
        try:
            conn = _public_connection(p.hostname, timeout)
        except OSError as e:
            raise SourceError('Could not download APK: ' + str(e)) from e
        try:
            conn.request('GET', (p.path or '/') + ('?' + p.query if p.query else ''), headers={'User-Agent': UA})
            r = conn.getresponse()
            if r.status in (301, 302, 303, 307, 308):
                url = urllib.parse.urljoin(url, r.getheader('Location') or '')
                continue
            if r.status == 429:
                raise limited_error(name, throttle(url, r.headers))
            if r.status != 200:
                raise SourceError("%s's download server refused the file (HTTP %d); try again later"
                                  % (name, r.status))
            return save_apk(r)
        except (OSError, ValueError, http.client.HTTPException, zipfile.BadZipFile) as e:
            raise SourceError('Could not download APK: ' + str(e)) from e
        finally:
            conn.close()
    raise SourceError(name + ' redirected the download too many times')
