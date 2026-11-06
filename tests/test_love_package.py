import sandbox  # noqa: F401
import runpy
import hashlib
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from apk_fixtures import pool
import frame_apk
from frame_apk_vr import _append_string

package = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'frame/love/package.py'))
clipboard = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'frame/love/clipboard.py'))


class LoveIdentityTests(unittest.TestCase):
    def test_manifest_strings_keep_unicode_and_multibyte_lengths(self):
        text = 'My game \U0001f3ae ' + 'x' * 150
        for utf8 in (False, True):
            changed, index = _append_string(pool(['original'], utf8=utf8), text)
            self.assertEqual(index, 1)
            self.assertEqual(frame_apk._string_pool(changed, 0), ['original', text])

    def test_separate_identity_keeps_java_activity_and_jni_package(self):
        original = 'org.love2d.android'
        strings = ['manifest', 'package', original, 'application', 'label', 'LÖVE for Android',
                   'activity', 'name', original + '.GameActivity', 'permission',
                   original + '.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION', 'provider',
                   'authorities', original + '.androidx-startup']

        def element(tag, key, value):
            body = struct.pack('<IIHHHHHH', 0xffffffff, strings.index(tag), 20, 20, 1, 0, 0, 0)
            body += struct.pack('<IIIHBBI', 0xffffffff, strings.index(key), strings.index(value),
                                8, 0, 3, strings.index(value))
            return struct.pack('<HHIII', 0x0102, 16, 16 + len(body), 1, 0xffffffff) + body

        chunks = pool(strings) + b''.join([
            element('manifest', 'package', original),
            element('application', 'label', 'LÖVE for Android'),
            element('activity', 'name', original + '.GameActivity'),
            element('permission', 'name', original + '.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'),
            element('provider', 'authorities', original + '.androidx-startup')])
        data = struct.pack('<HHI', 3, 8, 8 + len(chunks)) + chunks
        changed = package['manifest'](data, 'com.example.game', 'My Game')
        attrs = dict(frame_apk.manifest_elements(changed))
        self.assertEqual(attrs['manifest']['package'][2], 'com.example.game')
        self.assertEqual(attrs['application']['label'][2], 'My Game')
        self.assertEqual(attrs['activity']['name'][2], original + '.GameActivity')
        self.assertEqual(attrs['permission']['name'][2], 'com.example.game.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION')
        self.assertEqual(attrs['provider']['authorities'][2], 'com.example.game.androidx-startup')

    def test_generic_runtime_identity_cannot_replace_the_users_other_love_apps(self):
        with self.assertRaises(ValueError):
            package['manifest'](b'', 'org.love2d.android', 'Game')

    def test_dex_class_replacement_preserves_other_definitions_and_checksums(self):
        descriptors = [clipboard['CLASS'], 'Lorg/libsdl/app/SDLActivity;']
        data = bytearray(112 + 8 + 8 + 64)
        data[:8] = b'dex\n035\0'
        struct.pack_into('<IIII', data, 56, 2, 112, 2, 120)
        struct.pack_into('<II', data, 96, 2, 128)
        struct.pack_into('<II', data, 120, 0, 1)
        struct.pack_into('<I', data, 128 + 32, 1)
        preserved = bytes(data[160:192])
        for i, text in enumerate(descriptors):
            struct.pack_into('<I', data, 112 + 4*i, len(data))
            data += bytes([len(text)]) + text.encode() + b'\0'
        data += bytes(-len(data) % 4)
        struct.pack_into('<I', data, 52, len(data))
        data += struct.pack('<IHHII', 1, 6, 0, 2, 128)
        struct.pack_into('<I', data, 32, len(data))
        data[12:32] = hashlib.sha1(data[32:]).digest()
        struct.pack_into('<I', data, 8, zlib.adler32(data[12:]))
        changed = clipboard['remove_class'](bytes(data))
        self.assertEqual(len(changed), len(data))
        self.assertEqual(changed[128:160], preserved)
        self.assertEqual(struct.unpack_from('<I', changed, 96)[0], 1)
        self.assertEqual(changed[12:32], hashlib.sha1(changed[32:]).digest())
        self.assertEqual(struct.unpack_from('<I', changed, 8)[0], zlib.adler32(changed[12:]))
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            clipboard['remove_class'](changed)
        data[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            clipboard['remove_class'](bytes(data))

    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK executes actual SDL Java source')
    def test_clipboard_service_missing_and_available(self):
        sources = {
            'android/content/Context.java': '''package android.content;
                public class Context { public static final String CLIPBOARD_SERVICE="clipboard";
                    public static ClipboardManager service;
                    public Object getSystemService(String name) { return service; } }''',
            'android/content/ClipData.java': '''package android.content;
                public class ClipData { String text; ClipData(String s) {text=s;}
                    public static ClipData newPlainText(String label,String text) {return new ClipData(text);}
                    public Item getItemAt(int i) {return new Item();}
                    public class Item {public CharSequence getText(){return text;}} }''',
            'android/content/ClipboardManager.java': '''package android.content;
                public class ClipboardManager {
                    public interface OnPrimaryClipChangedListener {void onPrimaryClipChanged();}
                    public int listeners; ClipData clip;
                    public void addPrimaryClipChangedListener(OnPrimaryClipChangedListener l){listeners++;}
                    public void removePrimaryClipChangedListener(OnPrimaryClipChangedListener l){listeners--;}
                    public boolean hasPrimaryClip(){return clip!=null;}
                    public ClipData getPrimaryClip(){return clip;}
                    public void setPrimaryClip(ClipData c){clip=c;} }''',
            'org/libsdl/app/SDL.java': '''package org.libsdl.app;
                class SDL {static android.content.Context getContext(){return new android.content.Context();}}''',
            'org/libsdl/app/SDLActivity.java': '''package org.libsdl.app;
                class SDLActivity {static int callbacks; static void onNativeClipboardChanged(){callbacks++;}}''',
            'org/libsdl/app/Probe.java': '''package org.libsdl.app;
                import android.content.*;
                public class Probe {public static void main(String[] args){
                    SDLClipboardHandler absent=new SDLClipboardHandler();
                    if(absent.clipboardHasText() || absent.clipboardGetText()!=null) throw new AssertionError();
                    absent.clipboardSetText("ignored");
                    Context.service=new ClipboardManager();
                    SDLClipboardHandler live=new SDLClipboardHandler();
                    if(live.clipboardHasText() || live.clipboardGetText()!=null) throw new AssertionError();
                    live.clipboardSetText("working");
                    if(!live.clipboardHasText() || !"working".equals(live.clipboardGetText()) ||
                       Context.service.listeners!=1) throw new AssertionError();
                    live.onPrimaryClipChanged();
                    if(SDLActivity.callbacks!=1) throw new AssertionError(); }}''',
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources['org/libsdl/app/SDLClipboardHandler.java'] = (
                Path(__file__).resolve().parents[1] / 'frame/love/SDLClipboardHandler.java').read_text()
            for name, text in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            result = subprocess.run(['javac', '-d', str(root), *[str(root/n) for n in sources]],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(['java', '-cp', str(root), 'org.libsdl.app.Probe'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
