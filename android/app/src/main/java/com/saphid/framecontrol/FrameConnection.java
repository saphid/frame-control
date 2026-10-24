package com.saphid.framecontrol;

import android.content.Context;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import com.jcraft.jsch.*;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.regex.*;

/** All headset traffic goes through one pinned, authenticated SSH connection. */
final class FrameConnection implements AutoCloseable, SyncEngine.Transport {
  private final Context context;
  private Session session;
  private ChannelExec server;
  private PipedOutputStream serverInput;
  private int localPort;
  private String apiKey;
  private static final String HOST_ALGORITHMS = "ecdsa-sha2-nistp256,rsa-sha2-512,rsa-sha2-256";

  FrameConnection(Context context) {
    this.context = context.getApplicationContext();
  }

  static String fingerprint(String pin) throws Exception {
    return "SHA256:"
        + Base64.getEncoder()
            .withoutPadding()
            .encodeToString(
                MessageDigest.getInstance("SHA-256").digest(Base64.getDecoder().decode(pin)));
  }

  static String hash(String value) throws Exception {
    byte[] bytes =
        MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
    StringBuilder result = new StringBuilder();
    for (byte b : bytes) result.append(String.format(Locale.ROOT, "%02x", b & 255));
    return result.toString();
  }

  static String quote(String s) {
    return "'" + s.replace("'", "'\\''") + "'";
  }

  private static Session session(JSch jsch, String host, int port, String user) throws Exception {
    if (host.trim().isEmpty()
        || host.length() > 253
        || host.contains("/")
        || host.chars().anyMatch(Character::isWhitespace)
        || port < 1
        || port > 65535
        || !user.matches("[a-zA-Z0-9_-]{1,32}"))
      throw new IOException("Check the headset address, port and username.");
    Session s = jsch.getSession(user, host, port);
    s.setConfig("StrictHostKeyChecking", "yes");
    s.setConfig("server_host_key", HOST_ALGORITHMS);
    s.setConfig("PreferredAuthentications", "publickey");
    s.setTimeout(20000);
    s.setServerAliveInterval(15000);
    s.setServerAliveCountMax(2);
    return s;
  }

  private static final class PinRepository implements HostKeyRepository {
    String observed;
    final String expected;

    PinRepository(String expected) {
      this.expected = expected;
    }

    @Override
    public int check(String host, byte[] key) {
      observed = Base64.getEncoder().encodeToString(key);
      return observed.equals(expected) ? OK : CHANGED;
    }

    @Override
    public void add(HostKey k, UserInfo u) {}

    @Override
    public void remove(String h, String t) {}

    @Override
    public void remove(String h, String t, byte[] k) {}

    @Override
    public String getKnownHostsRepositoryID() {
      return "Frame Control pinned headset";
    }

    @Override
    public HostKey[] getHostKey() {
      return new HostKey[0];
    }

    @Override
    public HostKey[] getHostKey(String h, String t) {
      return new HostKey[0];
    }
  }

  /** Intentionally refuses the key exchange before any authentication is sent. */
  static String probe(String host, int port, String user) throws Exception {
    JSch jsch = new JSch();
    PinRepository pin = new PinRepository(null);
    jsch.setHostKeyRepository(pin);
    Session s = session(jsch, host, port, user);
    try {
      s.connect(10000);
    } catch (JSchException e) {
      if (pin.observed == null) throw e;
    } finally {
      s.disconnect();
    }
    return pin.observed;
  }

  static void pair(String host, int port, String user, String pin, String password, String install)
      throws Exception {
    JSch jsch = new JSch();
    jsch.setHostKeyRepository(new PinRepository(pin));
    Session s = session(jsch, host, port, user);
    s.setConfig("PreferredAuthentications", "password,keyboard-interactive");
    s.setPassword(password);
    s.setUserInfo(
        new UserInfo() {
          public String getPassphrase() {
            return null;
          }

          public String getPassword() {
            return password;
          }

          public boolean promptPassword(String x) {
            return true;
          }

          public boolean promptPassphrase(String x) {
            return false;
          }

          public boolean promptYesNo(String x) {
            return false;
          }

          public void showMessage(String x) {}
        });
    try {
      s.connect(15000);
      String key = new PhoneIdentity().authorizedKey(install);
      run(
          s,
          "umask 077; mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod"
              + " 600 ~/.ssh/authorized_keys && (grep -qxF "
              + quote(key)
              + " ~/.ssh/authorized_keys || printf '%s\\n' "
              + quote(key)
              + " >> ~/.ssh/authorized_keys)",
          10000);
    } finally {
      s.disconnect();
    }
    // Verify the new key before storing any pairing settings.
    JSch verified = new JSch();
    verified.setHostKeyRepository(new PinRepository(pin));
    verified.addIdentity(new PhoneIdentity(), null);
    Session check = session(verified, host, port, user);
    try {
      check.connect(15000);
    } finally {
      check.disconnect();
    }
  }

  static String run(Session s, String command, int timeout) throws Exception {
    ChannelExec channel = (ChannelExec) s.openChannel("exec");
    channel.setCommand(command);
    channel.setInputStream(null);
    channel.setErrStream(
        new OutputStream() {
          public void write(int b) {}

          public void write(byte[] b, int offset, int length) {}
        });
    InputStream input = channel.getInputStream();
    long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeout);
    ByteArrayOutputStream output = new ByteArrayOutputStream();
    try {
      channel.connect(timeout);
      while (true) {
        while (input.available() > 0) {
          byte[] b = new byte[Math.min(input.available(), 8192)];
          int n = input.read(b);
          if (n > 0) output.write(b, 0, n);
          if (output.size() > 2 * 1024 * 1024)
            throw new IOException("Headset command returned too much data.");
        }
        if (channel.isClosed() && input.available() == 0) break;
        if (System.nanoTime() > deadline) throw new IOException("The headset command timed out.");
        Thread.sleep(25);
      }
      if (channel.getExitStatus() != 0)
        throw new IOException("The headset command failed (" + channel.getExitStatus() + ").");
      return output.toString(StandardCharsets.UTF_8.name());
    } finally {
      channel.disconnect();
    }
  }

  void connect(String host, int port, String user, String pin, String install) throws Exception {
    JSch jsch = new JSch();
    jsch.setHostKeyRepository(new PinRepository(pin));
    jsch.addIdentity(new PhoneIdentity(), null);
    session = session(jsch, host, port, user);
    session.connect(15000);
    String version;
    try (InputStream in = context.getAssets().open("frame-bundle.version")) {
      version = new String(readBounded(in, 128), StandardCharsets.US_ASCII).trim();
    }
    if (!version.matches("[0-9a-f]{16}")) throw new IOException("Invalid bundled server version.");
    String dir = ".cache/frame-control/" + version;
    String present =
        run(session, "test -f " + dir + "/ui/server.py && printf ready || true", 10000);
    if (!present.equals("ready")) {
      run(session, "mkdir -p .cache/frame-control", 10000);
      String temp = dir + ".android-" + UUID.randomUUID();
      ChannelSftp sftp = (ChannelSftp) session.openChannel("sftp");
      try (InputStream in = context.getAssets().open("frame-bundle.tar.gz")) {
        sftp.connect(10000);
        sftp.put(in, temp + ".tar.gz");
      } finally {
        sftp.disconnect();
      }
      run(
          session,
          "mkdir "
              + temp
              + " && tar xzf "
              + temp
              + ".tar.gz -C "
              + temp
              + " && "
              + "(test -f "
              + dir
              + "/ui/server.py && rm -rf "
              + temp
              + " || mv "
              + temp
              + " "
              + dir
              + ") && rm -f "
              + temp
              + ".tar.gz",
          60000);
    }
    apiKey = UUID.randomUUID().toString().replace("-", "");
    server = (ChannelExec) session.openChannel("exec");
    serverInput = new PipedOutputStream();
    server.setInputStream(new PipedInputStream(serverInput));
    server.setCommand(
        "cd "
            + dir
            + " && FRAME_LOCAL=1 FRAME_UI_KEY="
            + apiKey
            + " FRAME_DEVICE="
            + quote(host)
            + " FRAME_CLIENT="
            + quote(install)
            + " exec python3 -I -u -B \"$PWD/ui/server.py\" --port 0 --exit-on-eof 2>&1");
    InputStream input = server.getInputStream();
    server.connect(10000);
    ByteArrayOutputStream startup = new ByteArrayOutputStream();
    Pattern portPattern = Pattern.compile("Frame Control on http://127\\.0\\.0\\.1:([0-9]+)\\s");
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(40);
    int portFound = 0;
    while (System.nanoTime() < deadline) {
      while (input.available() > 0) {
        startup.write(input.read());
        if (startup.size() > 65536) throw new IOException("The headset server did not start.");
      }
      Matcher m = portPattern.matcher(startup.toString(StandardCharsets.UTF_8.name()));
      if (m.find()) {
        portFound = Integer.parseInt(m.group(1));
        break;
      }
      if (server.isClosed())
        throw new IOException("The headset server stopped before it was ready.");
      Thread.sleep(50);
    }
    if (portFound < 1 || portFound > 65535)
      throw new IOException("The headset server did not answer in time.");
    localPort = session.setPortForwardingL("127.0.0.1", 0, "127.0.0.1", portFound);
    // Drain the session-bound server output; never log session keys or user data.
    Thread drain =
        new Thread(
            () -> {
              try {
                byte[] b = new byte[4096];
                while (input.read(b) != -1) {}
              } catch (IOException ignored) {
              }
            },
            "frame-server-output");
    drain.setDaemon(true);
    drain.start();
  }

  String page() {
    return "http://127.0.0.1:" + localPort + "/?key=" + apiKey;
  }

  boolean connected() {
    return session != null && session.isConnected() && server != null && !server.isClosed();
  }

  private HttpURLConnection request(String path) throws Exception {
    HttpURLConnection c =
        (HttpURLConnection) new URL("http://127.0.0.1:" + localPort + path).openConnection();
    c.setConnectTimeout(10000);
    c.setReadTimeout(20000);
    c.setInstanceFollowRedirects(false);
    c.setRequestProperty("X-Frame-UI", apiKey);
    return c;
  }

  List<SyncEngine.Shot> shots() throws Exception {
    HttpURLConnection c = request("/api/shots");
    try (InputStream in = c.getInputStream()) {
      byte[] body = readBounded(in, 2 * 1024 * 1024);
      JsonArray array =
          JsonParser.parseString(new String(body, StandardCharsets.UTF_8))
              .getAsJsonObject()
              .getAsJsonArray("shots");
      List<SyncEngine.Shot> shots = new ArrayList<>();
      for (JsonElement e : array) {
        var s = e.getAsJsonObject();
        shots.add(
            new SyncEngine.Shot(
                s.get("id").getAsString(), s.get("size").getAsLong(), s.get("time").getAsDouble()));
      }
      return shots;
    } finally {
      c.disconnect();
    }
  }

  private static byte[] readBounded(InputStream input, int limit) throws IOException {
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    byte[] b = new byte[8192];
    int n;
    while ((n = input.read(b)) != -1) {
      if (out.size() + n > limit) throw new IOException("The headset response is too large.");
      out.write(b, 0, n);
    }
    return out.toByteArray();
  }

  @Override
  public void download(SyncEngine.Shot shot, File destination) throws Exception {
    HttpURLConnection c =
        request("/api/shots/image?id=" + URLEncoder.encode(shot.id, StandardCharsets.UTF_8.name()));
    try (InputStream in = c.getInputStream();
        FileOutputStream out = new FileOutputStream(destination)) {
      byte[] b = new byte[65536];
      long count = 0;
      int n;
      while ((n = in.read(b)) != -1) {
        count += n;
        if (count > shot.size) throw new IOException("Screenshot changed while downloading.");
        out.write(b, 0, n);
      }
      out.getFD().sync();
    } finally {
      c.disconnect();
    }
  }

  @Override
  public boolean validImage(File file) {
    android.graphics.BitmapFactory.Options options = new android.graphics.BitmapFactory.Options();
    options.inJustDecodeBounds = true;
    android.graphics.BitmapFactory.decodeFile(file.getPath(), options);
    if (options.outWidth <= 0
        || options.outHeight <= 0
        || options.outWidth > 16384
        || options.outHeight > 16384
        || (long) options.outWidth * options.outHeight > 60_000_000) return false;
    options.inJustDecodeBounds = false;
    options.inSampleSize = Math.max(1, Math.max(options.outWidth, options.outHeight) / 2048);
    android.graphics.Bitmap b = android.graphics.BitmapFactory.decodeFile(file.getPath(), options);
    if (b == null) return false;
    b.recycle();
    return true;
  }

  @Override
  public void close() {
    try {
      if (serverInput != null) serverInput.close();
    } catch (IOException ignored) {
    }
    if (server != null) server.disconnect();
    if (session != null) session.disconnect();
  }
}
