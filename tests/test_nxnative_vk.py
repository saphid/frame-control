"""Exercise the portable replay helpers shipped in the Android source patch."""
import sandbox  # noqa: F401
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VulkanReplayTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'native C compiler unavailable')
    def test_uniform_bounds_clip_conventions_and_shader_vertex_indices(self):
        patch = (ROOT / 'frame/nxnative/android-frame.patch').read_text()
        section = next(s for s in patch.split('diff --git ') if
                       s.startswith('a/dm/android/src_vk/frame_vk_state.h '))
        header = '\n'.join(line[1:] for line in section.splitlines()
                           if line.startswith('+') and not line.startswith('+++'))
        program = r'''
#include <assert.h>
#include "frame_vk_state.h"
int main(void) {
    unsigned char data[65536] = {0}; uint32_t value = 0xa5b12345;
    memcpy(data + 1, &value, 4); memcpy(data + 65532, &value, 4);
    uint64_t addr = (uintptr_t)data;
    assert(frame_vk_ubo_handle(addr, sizeof data, 1) == value);
    assert(frame_vk_ubo_handle(addr, sizeof data, 65532) == value);
    assert(!frame_vk_ubo_handle(addr, sizeof data, 65533));
    assert(!frame_vk_ubo_handle(addr, sizeof data, -1));
    assert(!frame_vk_ubo_handle(addr, 3, 0));
    assert(!frame_vk_ubo_handle(0, 8, 0));
    assert(!frame_vk_ubo_handle(UINTPTR_MAX, 8, 0));
    for (int lower = 0; lower < 2; lower++) for (int flip = 0; flip < 2; flip++) {
        float y = 27, height = -12;
        assert(frame_vk_viewport_y(lower, flip ? 0x100 : 0, &y, &height));
        assert(y == ((lower ^ flip) ? 15 : 27));
        assert(height == ((lower ^ flip) ? 12 : -12));
    }
    float y = 27, height = -12;
    assert(!frame_vk_viewport_y(0, 0x200, &y, &height));
    assert(y == 27 && height == -12);
    int32_t first, last;
    frame_vk_present_y(0, 7, 13, &first, &last); assert(first == 7 && last == 20);
    frame_vk_present_y(1, 7, 13, &first, &last); assert(first == 20 && last == 7);
    uint32_t spv[] = {0x07230203,0,0,0,0, (4u<<16)|71,33,11,42};
    assert(frame_vk_preserve_vertex_index(spv, sizeof spv / 4));
    spv[8] = 4424; assert(frame_vk_preserve_vertex_index(spv, sizeof spv / 4));
    spv[8] = 43; assert(!frame_vk_preserve_vertex_index(spv, sizeof spv / 4));
    spv[5] = 0; assert(!frame_vk_preserve_vertex_index(spv, sizeof spv / 4));
    spv[5] = (20u<<16)|71; assert(!frame_vk_preserve_vertex_index(spv, sizeof spv / 4));
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'frame_vk_state.h').write_text(header)
            (root / 'test.c').write_text(program)
            binary = root / 'check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(root / 'test.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
