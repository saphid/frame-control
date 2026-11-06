"""Compile the vertex fetch helpers from the Android patch that we ship."""
import sandbox  # noqa: F401
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VulkanVertexTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'native C compiler unavailable')
    def test_register_values_numeric_classes_and_source_bounds(self):
        patch = (ROOT / 'frame/nxnative/android-frame.patch').read_text()
        sections = [s for s in patch.split('diff --git ')
                    if s.startswith('a/dm/android/src_vk/frame_vk_vertex.h ')]
        self.assertEqual(len(sections), 1, 'shipped patch must contain vertex helper')
        header = '\n'.join(line[1:] for line in sections[0].splitlines()
                           if line.startswith('+') and not line.startswith('+++'))
        program = r'''#include <assert.h>
#include <stdio.h>
#include "frame_vk_vertex.h"
static uint32_t fb(float f) { uint32_t u; memcpy(&u,&f,4); return u; }
static void plan(int f,int ct,int converted,int result) {
    frame_vk_vertex_plan p=frame_vk_vertex_plan_get(f,ct);
    assert(p.convert==converted); assert(p.fmt==result);
}
int main(void) {
    frame_vk_vertex_range range;
    assert(frame_vk_vertex_range_get(3,5,12,4,8,4096,72,3,&range));
    assert(range.from==40 && range.bytes==32 && range.count==3);
    assert(!frame_vk_vertex_range_get(3,5,12,4,8,4096,71,3,&range));
    assert(!frame_vk_vertex_range_get(3,5,12,4,8,4096,72,2,&range));
    assert(frame_vk_vertex_range_get(100,200,0,4,8,4096,12,1,&range));
    assert(range.from==4 && range.bytes==8 && range.count==1);
    assert(!frame_vk_vertex_range_get(5,3,12,4,8,4096,72,3,&range));
    assert(!frame_vk_vertex_range_get(0,1,UINT64_MAX,0,4,1,UINT64_MAX,2,&range));
    assert(!frame_vk_vertex_range_get(0,0,0,UINT64_MAX,4,1,UINT64_MAX,1,&range));
    assert(!frame_vk_vertex_range_get(0,UINT64_MAX,1,0,1,1,UINT64_MAX,UINT64_MAX,&range));
    assert(!frame_vk_vertex_range_get(0,0,4,0,4,UINTPTR_MAX-2,4,1,&range));
    assert(!frame_vk_vertex_range_get(0,0,4,0,4,0,4,1,&range));
    /* Float vertex color/UV fetch must keep normalization and half conversion. */
    plan(0x25,0,0,0x25); plan(0x26,0,0,0x26); plan(0x11,0,0,0x11);
    plan(0x3d,0,0,0x3d); plan(0x69,0,0,0x69); plan(0x3f,0,0,0x3f);
    plan(0x9a,0,0,0x9a); plan(0x57,0,0,0x57);
    /* Integer declarations reading normalized/half data take converted float bits. */
    plan(0x25,1,1,0x2f); plan(0x11,2,1,0x30); plan(0x69,1,1,0x2f);
    /* Same signed integer formats pass through; signedness changes preserve
     * original sign extension, and float declarations preserve integer bits. */
    plan(0x27,1,0,0x27); plan(0x28,2,0,0x28); plan(0x28,1,1,0x2f);
    plan(0x27,0,1,0x2e); plan(0x2f,0,0,0x2e); plan(0x30,1,0,0x2f);
    plan(0x2e,1,0,0x2f); plan(0x0a,1,1,0x2f);
    plan(0x55,0,1,0x2e); plan(0x56,1,1,0x2f); plan(0x57,1,1,0x2f);
    for(int f=1;f<=0x9a;f++) for(int ct=0;ct<3;ct++) {
        frame_vk_vertex_desc d=frame_vk_vertex_desc_get(f); if(!d.n) continue;
        frame_vk_vertex_plan p=frame_vk_vertex_plan_get(f,ct);
        frame_vk_vertex_desc o=frame_vk_vertex_desc_get(p.fmt);
        assert(o.n>0); int cls=o.kind==FVV_UINT?1:o.kind==FVV_SINT?2:0;
        assert(cls==ct); assert(p.size>=1 && p.size<=16);
    }
    uint32_t o[4];
    uint8_t rgba[4]={0,128,255,64}; frame_vk_vertex_convert(0x25,rgba,o);
    assert(o[0]==fb(0)); assert(o[1]==fb(128.0f/255)); assert(o[2]==fb(1));
    int8_t sn[2]={-128,127}; frame_vk_vertex_convert(0x0e,(const uint8_t*)sn,o);
    assert(o[0]==fb(-1)); assert(o[1]==fb(1)); assert(o[2]==0); assert(o[3]==fb(1));
    uint16_t half[2]={0x3c00,0xc000}; frame_vk_vertex_convert(0x11,(const uint8_t*)half,o);
    assert(o[0]==fb(1)); assert(o[1]==fb(-2)); assert(o[3]==fb(1));
    assert(frame_vk_vertex_half(1)==ldexpf(1,-24));
    assert(isinf(frame_vk_vertex_half(0x7c00))); assert(isnan(frame_vk_vertex_half(0x7e00)));
    assert(signbit(frame_vk_vertex_half(0x8000)));
    int16_t si[4]={-32768,-1,0,32767}; frame_vk_vertex_convert(0x2d,(const uint8_t*)si,o);
    assert(o[0]==0xffff8000u); assert(o[1]==0xffffffffu); assert(o[2]==0); assert(o[3]==32767);
    uint8_t ui=255; frame_vk_vertex_convert(0x03,&ui,o);
    assert(o[0]==255); assert(o[1]==0); assert(o[3]==1);
    uint32_t bits=0xdeadbeef; frame_vk_vertex_convert(0x0a,(const uint8_t*)&bits,o);
    assert(o[0]==bits); assert(o[3]==fb(1));
    int32_t scaled=-200; frame_vk_vertex_convert(0x56,(const uint8_t*)&scaled,o);
    assert(o[0]==fb(-200)); assert(o[3]==fb(1));
    uint8_t bgra[4]={10,20,30,40}; frame_vk_vertex_convert(0x9a,bgra,o);
    assert(o[0]==fb(30.0f/255)); assert(o[2]==fb(10.0f/255));
    uint32_t packed=1023u|(512u<<10)|(0u<<20)|(3u<<30);
    frame_vk_vertex_convert(0x3d,(const uint8_t*)&packed,o);
    assert(o[0]==fb(1)); assert(o[1]==fb(512.0f/1023)); assert(o[3]==fb(1));
    packed=0x200u|(0x1ffu<<10)|(0x3ffu<<20)|(2u<<30);
    frame_vk_vertex_convert(0x69,(const uint8_t*)&packed,o);
    assert(o[0]==fb(-1)); assert(o[1]==fb(1)); assert(o[3]==fb(-1));
    frame_vk_vertex_convert(0x6a,(const uint8_t*)&packed,o);
    assert(o[0]==(uint32_t)-512); assert(o[1]==511); assert(o[3]==(uint32_t)-2);
    packed=960u|(960u<<11)|(480u<<22); /*1.0 for 11-, 11-, 10-bit floats*/
    frame_vk_vertex_convert(0x3f,(const uint8_t*)&packed,o);
    assert(o[0]==fb(1)); assert(o[1]==fb(1)); assert(o[2]==fb(1)); assert(o[3]==fb(1));
    puts("vertex conversion: numeric-class matrix and register-value cases passed");
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'frame_vk_vertex.h').write_text(header)
            (root / 'test.c').write_text(program)
            binary = root / 'check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=undefined', '-fno-sanitize-recover=all',
                            str(root / 'test.c'), '-o', str(binary), '-lm'], check=True)
            subprocess.run([str(binary)], check=True)
