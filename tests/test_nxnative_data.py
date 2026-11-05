import sandbox  # noqa: F401
from pathlib import Path
import runpy
import struct
import hashlib
import io
import os
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
extract = runpy.run_path(str(ROOT / 'frame/nxnative/extract_romfs.py'))['extract']


def image(name=b'hello', flags=0, child=1, start=32):
    # Root, one folder, then a file, as the upstream breadth-first writer emits.
    entries = (struct.pack('<QQIHBB', child, 1, 0, 0, 0, 0)
               + struct.pack('<QQIHBB', 2, 1, 0, 3, 0, 0)
               + struct.pack('<QQIHBB', start, 7, 3, len(name), 1, flags))
    index = entries + b'dir' + name
    return struct.pack('<8sQQQ', b'DMROMFS1', 39, len(index), 3) + b'payload' + index


class RomfsExtractionTests(unittest.TestCase):
    def test_expands_files_and_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / 'image'
            src.write_bytes(image())
            dest = root / 'out'
            self.assertEqual(extract(src, dest), {'files': 1, 'bytes': 7})
            self.assertEqual((dest / 'dir/hello').read_bytes(), b'payload')
            with self.assertRaises(FileExistsError):
                extract(src, dest)
            self.assertEqual(src.read_bytes(), image())

    def test_rejects_corruption_and_unsafe_paths_before_creating_destination(self):
        for content in [image(b'../escape'), image(b'/absolute'), image(flags=1),
                        image(child=0), image(start=38), image()[:-1], b'bad']:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                src = root / 'image'
                src.write_bytes(content)
                with self.assertRaises(ValueError):
                    extract(src, root / 'out')
                self.assertFalse((root / 'out').exists())


publish = runpy.run_path(str(ROOT / 'frame/nxnative/stage.py'))['publish_script']


@unittest.skipIf(os.name == 'nt', 'publication script runs inside Android/POSIX, not Windows Git Bash')
class DatasetPublicationTests(unittest.TestCase):
    def test_bad_hash_or_truncated_stream_keeps_old_selection_and_saves(self):
        for truncated in (False, True):
            with self.subTest(truncated=truncated), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'frame-data').mkdir()
                (root / 'frame-data.current').write_text('old-dataset\n')
                (root / 'save').mkdir()
                (root / 'save/progress').write_bytes(b'keep me')
                upload = io.BytesIO()
                with tarfile.open(fileobj=upload, mode='w') as archive:
                    for name, data in [('dm/main.patched.bin', b'changed'),
                                       ('frame-data.sha256', b'0' * 64 + b'  dm/main.patched.bin\n')]:
                        info = tarfile.TarInfo(name)
                        info.size = len(data)
                        archive.addfile(info, io.BytesIO(data))
                content = upload.getvalue()
                if truncated:
                    content = content[:600]
                temporary, final = root / 'frame-data/.stage', root / 'frame-data/new'
                result = subprocess.run(['sh', '-c', publish('org.example.nxnative', root, temporary, final, 'new')],
                                        input=content, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((root / 'frame-data.current').read_text(), 'old-dataset\n')
                self.assertEqual((root / 'save/progress').read_bytes(), b'keep me')
                self.assertFalse(final.exists())
                self.assertFalse(temporary.exists())

    def test_verified_dataset_is_selected_and_can_be_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b'game module'
            upload = io.BytesIO()
            with tarfile.open(fileobj=upload, mode='w') as archive:
                for name, data in [('dm/main.patched.bin', payload), ('frame-data.sha256',
                        (hashlib.sha256(payload).hexdigest() + '  dm/main.patched.bin\n').encode())]:
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
            final = root / 'frame-data/new'
            for i in range(2):
                temporary = root / ('frame-data/.stage' + str(i))
                result = subprocess.run(['sh', '-c', publish('org.example.nxnative', root, temporary, final, 'new')],
                                        input=upload.getvalue(), capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root / 'frame-data.current').read_text(), 'new\n')
                self.assertEqual((final / 'dm/main.patched.bin').read_bytes(), payload)
                self.assertFalse(temporary.exists())


if __name__ == '__main__':
    unittest.main()
