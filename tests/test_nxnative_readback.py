"""Compile the shipped CPU readback helper against independent tile fixtures."""
import sandbox  # noqa: F401
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

# A small synthetic NVN layout provider keeps this test independent of an
# nxnative checkout. Fixed mip/layer offsets make view selection observable.
LAYOUT = r'''
#include <stdint.h>
#include <stddef.h>
typedef struct {
    int target, format, flags, samples;
    uint32_t width, height, depth, levels, stride;
    int pkg_block_h;
} nvn_texdesc;
typedef struct {
    uint64_t size, layer_size;
    uint32_t align, layers, bpb;
    unsigned tileH, tileD;
} nvn_texlayout;
static int nvn_fmt_bpb(int f, int *bw, int *bh) {
    *bw = *bh = f == 0x41 ? 4 : 1;
    return f == 1 ? 1 : f == 0x25 ? 4 : f == 0x2e ? 16 : f == 0x41 ? 8 : 0;
}
static void nvn_tex_layout(const nvn_texdesc *d, nvn_texlayout *l) {
    *l = (nvn_texlayout){65536, 16384, 512, d->target == 4 ? d->depth : 1, 1, 0, 0};
}
static uint32_t nvn_tex_level_gobs(const nvn_texdesc *d, unsigned lv) {
    int bw, bh, bpb = nvn_fmt_bpb(d->format, &bw, &bh);
    unsigned w = d->width >> lv; if (!w) w = 1;
    return ((w + bw - 1) / bw * bpb + 63) / 64;
}
static int nvn_deswizzle_geom(const nvn_texdesc *d, unsigned lv, unsigned layer,
        uint32_t *rb, uint32_t *rows, uint32_t *slices, uint64_t *base,
        unsigned *th, unsigned *td, uint32_t *bp) {
    int bw, bh; *bp = nvn_fmt_bpb(d->format, &bw, &bh);
    unsigned w = d->width >> lv, h = d->height >> lv;
    if (!w) w = 1; if (!h) h = 1;
    *rb = (w + bw - 1) / bw * *bp; *rows = (h + bh - 1) / bh;
    *slices = d->target == 2 ? d->depth >> lv : 1;
    *base = 4096u * lv + 16384u * layer; *th = *td = 0;
    return 0;
}
static uint64_t nvn_bl_offset(uint32_t x, uint32_t y, uint32_t z,
        uint32_t rb, uint32_t rows, unsigned th, unsigned td) {
    static const unsigned ry[8] = {0,16,64,80,128,144,192,208};
    static const unsigned rx[4] = {0,32,256,288};
    (void)th; (void)td;
    unsigned gobs = (rb + 63) / 64;
    return z * gobs * ((rows + 7) / 8) * 512ull +
        (y / 8 * gobs + x / 64) * 512ull + ry[y % 8] + rx[x % 64 / 16] + x % 16;
}
'''

PROGRAM = r'''
#include <assert.h>
#include "frame_vk_readback.h"
int main(void) {
    uint8_t mem[65536], out[64];
    for (unsigned i = 0; i < sizeof mem; i++) mem[i] = i % 251;
    memset(out, 0xa5, sizeof out);
    nvn_texdesc d = {.target=1,.format=1,.width=64,.height=32,.depth=1,.levels=3};
    assert(frame_vk_read_storage(&d,mem,sizeof mem,0,0,
        (frame_vk_read_region){15,1,0,3,2,1},out,5,10));
    /* Independent known addresses cross a 16-byte GOB run boundary. */
    assert(out[0]==31 && out[1]==48 && out[2]==49);
    assert(out[5]==79 && out[6]==96 && out[7]==97);
    assert(out[3]==0xa5 && out[4]==0xa5 && out[8]==0xa5);
    assert(frame_vk_read_storage(&d,mem,sizeof mem,2,0,
        (frame_vk_read_region){0,0,0,2,1,0},out,0,0));
    assert(out[0]==mem[8192] && out[1]==mem[8193]);
    d.target=4; d.depth=4;
    assert(frame_vk_read_storage(&d,mem,sizeof mem,0,1,
        (frame_vk_read_region){0,0,1,2,1,2},out,2,5));
    assert(out[0]==mem[32768] && out[5]==mem[49152]);
    d.target=2; d.height=8;
    assert(frame_vk_read_storage(&d,mem,sizeof mem,0,0,
        (frame_vk_read_region){0,0,1,2,1,2},out,2,5));
    assert(out[0]==mem[512] && out[5]==mem[1024]);
    d=(nvn_texdesc){.target=1,.format=0x41,.width=5,.height=5,.depth=1,.levels=1};
    assert(frame_vk_read_storage(&d,mem,sizeof mem,0,0,
        (frame_vk_read_region){4,4,0,1,1,1},out,0,0));
    assert(!memcmp(out,mem+24,8));
    assert(!frame_vk_read_storage(&d,mem,sizeof mem,0,0,
        (frame_vk_read_region){1,0,0,4,1,1},out,0,0));
    d=(nvn_texdesc){.target=1,.format=0x25,.flags=FVR_LINEAR,
        .stride=40,.width=6,.height=3,.depth=1,.levels=1};
    memset(out,0xa5,sizeof out);
    assert(frame_vk_read_storage(&d,mem,sizeof mem,0,0,
        (frame_vk_read_region){1,1,0,3,2,1},out,16,32));
    assert(!memcmp(out,mem+44,12) && !memcmp(out+16,mem+84,12));
    assert(out[12]==0xa5);
    /* Invalid storage must leave the destination untouched. */
    memset(out,0xa5,sizeof out);
    assert(!frame_vk_read_storage(&d,mem,1,0,0,
        (frame_vk_read_region){1,1,0,3,2,1},out,16,32));
    for (unsigned i=0;i<sizeof out;i++) assert(out[i]==0xa5);
    frame_vk_read_layout q;
    frame_vk_read_region r={0,0,0,1,2,1};
    assert(!frame_vk_read_layout_get(&d,0,0,r,SIZE_MAX,0,(uintptr_t)out,&q));
    assert(!frame_vk_read_layout_get(&d,0,0,r,0,0,UINTPTR_MAX-2,&q));
    assert(!frame_vk_read_layout_get(&d,32,0,r,0,0,(uintptr_t)out,&q));
    d.width=UINT32_MAX; d.format=0x2e;
    assert(!frame_vk_read_layout_get(&d,0,0,r,0,0,(uintptr_t)out,&q));
    return 0;
}
'''


class VulkanReadbackTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'native C compiler unavailable')
    def test_readtexels_regions_layout_and_bounds(self):
        patch = (ROOT / 'frame/nxnative/android-frame.patch').read_text()
        sections = [s for s in patch.split('diff --git ')
                    if s.startswith('a/dm/android/src_vk/frame_vk_readback.h ')]
        self.assertEqual(len(sections), 1, 'shipped patch must contain readback helper')
        header = '\n'.join(line[1:] for line in sections[0].splitlines()
                           if line.startswith('+') and not line.startswith('+++'))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src_vk').mkdir()
            (root / 'tex').mkdir()
            (root / 'tex/nvn_deswizzle.h').write_text(LAYOUT)
            (root / 'src_vk/frame_vk_readback.h').write_text(header)
            (root / 'src_vk/test.c').write_text(PROGRAM)
            binary = root / 'check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-misleading-indentation', '-fsanitize=undefined',
                            '-fno-sanitize-recover=all', str(root / 'src_vk/test.c'),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
