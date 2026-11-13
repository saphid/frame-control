"""Guest rootfs packing preserves usable timestamp-based Python caches."""
import gzip
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import py_compile
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'syncthing_service_pack', ROOT / 'scripts/framey-test-syncthing-service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def entries(path):
    """Read newc independently of the writer, including its fixed-width fields."""
    data = gzip.decompress(path.read_bytes())
    offset, result = 0, {}
    while offset < len(data):
        header = data[offset:offset + 110]
        if header[:6] != b'070701' or len(header) != 110:
            raise AssertionError('Invalid newc header')
        fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        size, namesize = fields[6], fields[11]
        offset += 110
        name = data[offset:offset + namesize]
        if not name.endswith(b'\0'):
            raise AssertionError('Invalid newc name')
        offset = (offset + namesize + 3) & ~3
        payload = data[offset:offset + size]
        if len(payload) != size:
            raise AssertionError('Truncated newc payload')
        offset = (offset + size + 3) & ~3
        name = name[:-1].decode()
        if name == 'TRAILER!!!':
            if offset != len(data):
                raise AssertionError('Unexpected trailing newc bytes')
            return result
        result[name] = dict(mode=fields[1], uid=fields[2], gid=fields[3],
                            mtime=fields[5], major=fields[9], minor=fields[10], data=payload)
    raise AssertionError('Missing newc trailer')


class RootfsPacking(unittest.TestCase):
    def pack(self, folder, members):
        archive, output = folder / 'rootfs.tar', folder / 'initrd.gz'
        with tarfile.open(archive, 'w') as tar:
            kernel = tarfile.TarInfo('boot/vmlinuz-fixture')
            kernel.size = len(b'owned test kernel')
            tar.addfile(kernel, io.BytesIO(b'owned test kernel'))
            for member, data in members:
                tar.addfile(member, io.BytesIO(data) if member.isfile() else None)
        self.assertEqual(service.pack(archive, output, {}, bootstrap=b'', user_probe=b''),
                         b'owned test kernel')
        return entries(output)

    def test_existing_timestamp_bytecode_imports_without_recompilation(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'fixture.py'
            source.write_bytes(b'VALUE = "published bytecode"\n')
            stamp = 1786363619
            os.utime(source, (stamp, stamp))
            cache = Path(py_compile.compile(str(source), doraise=True,
                         invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP))
            members = []
            for path in (source, cache):
                member = tarfile.TarInfo(path.relative_to(folder).as_posix())
                member.size, member.mtime = path.stat().st_size, path.stat().st_mtime
                members.append((member, path.read_bytes()))
            packed = self.pack(folder, members)
            restored = folder / 'restored'
            # Restore only the two known, owned fixture files, never archive paths.
            for path in (source, cache):
                name = path.relative_to(folder)
                entry = packed[name.as_posix()]
                target = restored / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(entry['data'])
                os.utime(target, (entry['mtime'], entry['mtime']))
            module_spec = importlib.util.spec_from_file_location('packed_cache_fixture',
                                                               restored / 'fixture.py')
            module = importlib.util.module_from_spec(module_spec)
            with patch.object(importlib.machinery.SourceFileLoader, 'source_to_code',
                              side_effect=AssertionError('Packed bytecode cache was invalidated')):
                module_spec.loader.exec_module(module)
            self.assertEqual(module.VALUE, 'published bytecode')
            self.assertEqual(packed['fixture.py']['mtime'], stamp)
            self.assertEqual(packed['fixture.py']['data'], source.read_bytes())
            self.assertEqual(packed[cache.relative_to(folder).as_posix()]['data'], cache.read_bytes())

    def test_member_metadata_and_generated_overlays_keep_their_own_timestamps(self):
        with tempfile.TemporaryDirectory() as temporary:
            members = []
            for name, kind, payload in (
                ('usr/share/fixture', tarfile.REGTYPE, b'unchanged bytes'),
                ('usr/share/alias', tarfile.SYMTYPE, b''),
                ('usr/share/hard', tarfile.LNKTYPE, b''),
                ('usr/share/folder', tarfile.DIRTYPE, b''),
                ('dev/fixture', tarfile.CHRTYPE, b''),
            ):
                member = tarfile.TarInfo(name)
                member.type, member.mode = kind, 0o750
                member.mtime, member.uid, member.gid = 1786363619.75, 123, 456
                member.linkname = 'usr/share/fixture'
                member.devmajor, member.devminor = 7, 9
                member.size = len(payload)
                members.append((member, payload))
            packed = self.pack(Path(temporary), members)
            for member, _ in members:
                with self.subTest(name=member.name):
                    entry = packed[member.name]
                    self.assertEqual((entry['mtime'], entry['uid'], entry['gid']),
                                     (1786363619, 123, 456))
                    self.assertEqual(stat.S_IMODE(entry['mode']), 0o750)
            self.assertEqual(packed['usr/share/alias']['data'], b'usr/share/fixture')
            self.assertEqual(packed['usr/share/hard']['data'], b'unchanged bytes')
            self.assertEqual((packed['dev/fixture']['major'], packed['dev/fixture']['minor']), (7, 9))
            self.assertEqual(packed['init']['mtime'], 0)
            self.assertEqual(packed['etc/hostname']['mtime'], 0)

    def test_unrepresentable_member_timestamp_is_refused(self):
        for stamp in (-1, 1 << 32):
            with self.subTest(stamp=stamp), tempfile.TemporaryDirectory() as temporary:
                member = tarfile.TarInfo('usr/share/fixture')
                member.mtime = stamp
                with self.assertRaisesRegex(ValueError, 'timestamp'):
                    self.pack(Path(temporary), [(member, b'')])
