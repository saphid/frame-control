"""Compile the image reflection/view guards from the Android patch we ship."""
import sandbox  # noqa: F401
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PATCH = Path(__file__).resolve().parents[1] / 'frame/nxnative/android-frame.patch'


class VulkanImageTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'native C compiler unavailable')
    def test_spirv_image_interfaces_and_legal_view_ranges(self):
        sections = [s for s in PATCH.read_text().split('diff --git ')
                    if s.startswith('a/dm/android/src_vk/frame_vk_image.h ')]
        self.assertEqual(len(sections), 1, 'shipped patch must contain image helper')
        header = '\n'.join(line[1:] for line in sections[0].splitlines()
                           if line.startswith('+') and not line.startswith('+++'))
        program = r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "frame_vk_image.h"
static uint32_t w[256]; static size_t n;
static void emit(const uint32_t *p,size_t k) { memcpy(w+n,p,k*4); n+=k; }
#define E(...) do { const uint32_t p[]={__VA_ARGS__}; emit(p,sizeof p/4); } while(0)
static void module(int dim,int array,int ms,int descriptors) {
    memset(w,0,sizeof w); n=5; w[0]=0x07230203; w[1]=0x10000; w[3]=64;
    /* Decorations deliberately precede their variables and types. */
    E(4u<<16|71,5,33,7); E(4u<<16|71,5,34,0);
    E(3u<<16|22,1,32);
    E(9u<<16|25,2,1,(uint32_t)dim,0,(uint32_t)array,(uint32_t)ms,1,0);
    E(3u<<16|27,3,2);
    if(descriptors) { E(4u<<16|28,6,3,7); E(4u<<16|32,4,0,6); }
    else E(4u<<16|32,4,0,3);
    E(4u<<16|59,4,5,0);
}
static int reflect(frame_vk_image_binding *out) {
    size_t count=123; int ok=frame_vk_image_reflect(w,n,out,4,&count);
    assert(ok ? count==1 : count==0); return ok;
}
static void good(int dim,int array,int ms,int wanted) {
    frame_vk_image_binding out[4]; module(dim,array,ms,0);
    assert(reflect(out)); assert(out[0].view==wanted);
    assert(out[0].set==0 && out[0].binding==7 && out[0].ms==ms && !out[0].descriptor_array);
}
int main(void) {
    frame_vk_image_binding out[4]; size_t count;
    good(0,0,0,FVI_1D); good(0,1,0,FVI_1D_ARRAY);
    good(1,0,0,FVI_2D); good(1,1,0,FVI_2D_ARRAY);
    good(1,0,1,FVI_2D); good(1,1,1,FVI_2D_ARRAY);
    good(2,0,0,FVI_3D); good(3,0,0,FVI_CUBE); good(3,1,0,FVI_CUBE_ARRAY);
    good(5,0,0,FVI_UNSUPPORTED); /* Buffer images need another descriptor path. */
    module(1,1,0,1); assert(reflect(out) && out[0].descriptor_array);
    module(1,0,0,0); w[12]=3; assert(reflect(out) && out[0].set==3);
    /* Separate sampled-image variables can point directly to OpTypeImage. */
    module(1,0,0,0); w[n-5]=2; assert(reflect(out));
    module(1,0,0,0); assert(!frame_vk_image_reflect(w,n,out,0,&count) && !count);
    assert(!frame_vk_image_reflect(NULL,n,out,4,&count));
    assert(!frame_vk_image_reflect(w,4,out,4,&count));
    assert(!frame_vk_image_reflect(w,4194305,out,4,&count));
    assert(!frame_vk_image_reflect(w,n,NULL,4,&count));
    assert(!frame_vk_image_reflect(w,n,out,4,NULL));
    module(1,0,0,0); w[0]=0; assert(!reflect(out));
    module(1,0,0,0); w[3]=0; assert(!reflect(out));
    module(1,0,0,0); w[3]=UINT32_MAX; assert(!reflect(out));
    module(1,0,0,0); w[4]=1; assert(!reflect(out));
    module(1,0,0,0); w[5]=71; assert(!reflect(out)); /* zero word count */
    module(1,0,0,0); w[5]=255u<<16|71; assert(!reflect(out));
    module(1,0,0,0); n--; assert(!reflect(out)); /* truncated final variable */
    module(1,0,0,0); E(4u<<16|71,5,33,8); assert(!reflect(out));
    module(1,0,0,0); E(4u<<16|71,64,33,8); assert(!reflect(out));
    module(1,0,0,0); E(4u<<16|59,4,5,0); assert(!reflect(out));
    module(1,0,0,0); w[n-5]=64; assert(!reflect(out)); /* invalid pointer pointee */
    module(1,0,0,0); w[n-5]=0; assert(!reflect(out));
    module(1,0,0,0); w[n-5]=4; assert(!reflect(out)); /* pointer cycle */
    module(1,0,0,0); w[n-5]=60; assert(!reflect(out)); /* undefined ID */
    module(7,0,0,0); assert(!reflect(out));
    module(1,2,0,0); assert(!reflect(out));
    module(1,0,2,0); assert(!reflect(out));
    /* Non-image uniform constants must not turn into image bindings. */
    module(1,0,0,0); w[n-5]=1;
    assert(frame_vk_image_reflect(w,n,out,4,&count) && count==0);
    /* Duplicate binding interfaces are rejected instead of choosing one. */
    module(1,0,0,0); E(4u<<16|59,4,8,0); E(4u<<16|71,8,33,7);
    assert(!reflect(out));

    uint32_t selected=99;
    assert(frame_vk_image_view_layers(1,0,256,128,1,0,1,FVI_2D_ARRAY,&selected) && selected==1);
    assert(frame_vk_image_view_layers(1,0,256,128,4,2,2,FVI_2D,&selected) && selected==1);
    assert(frame_vk_image_view_layers(1,0,256,128,4,1,3,FVI_2D_ARRAY,&selected) && selected==3);
    assert(frame_vk_image_view_layers(0,0,64,1,3,1,2,FVI_1D,&selected) && selected==1);
    assert(frame_vk_image_view_layers(0,0,64,1,3,1,2,FVI_1D_ARRAY,&selected) && selected==2);
    assert(!frame_vk_image_view_layers(0,0,64,1,1,0,1,FVI_2D,&selected));
    assert(!frame_vk_image_view_layers(1,0,64,1,1,0,1,FVI_1D,&selected));
    assert(frame_vk_image_view_layers(1,1,64,64,12,6,6,FVI_CUBE,&selected) && selected==6);
    assert(frame_vk_image_view_layers(1,1,64,64,13,0,13,FVI_CUBE_ARRAY,&selected) && selected==12);
    assert(!frame_vk_image_view_layers(1,0,64,64,6,0,6,FVI_CUBE,&selected));
    assert(!frame_vk_image_view_layers(1,1,64,32,6,0,6,FVI_CUBE,&selected));
    assert(!frame_vk_image_view_layers(1,1,64,64,6,0,5,FVI_CUBE_ARRAY,&selected));
    assert(!frame_vk_image_view_layers(1,1,64,64,12,1,6,FVI_CUBE,&selected));
    assert(frame_vk_image_view_layers(2,0,64,64,1,0,1,FVI_3D,&selected) && selected==1);
    assert(!frame_vk_image_view_layers(2,0,64,64,1,0,1,FVI_2D,&selected));
    assert(!frame_vk_image_view_layers(1,0,64,64,1,0,1,FVI_3D,&selected));
    assert(!frame_vk_image_view_layers(1,0,64,64,1,0,0,FVI_2D,&selected));
    assert(!frame_vk_image_view_layers(1,0,64,64,1,UINT32_MAX,2,FVI_2D,&selected));
    assert(!frame_vk_image_view_layers(1,0,64,64,2,1,UINT32_MAX,FVI_2D,&selected));
    assert(!frame_vk_image_view_layers(1,0,0,64,1,0,1,FVI_2D,&selected));
    assert(!frame_vk_image_view_layers(1,0,64,64,1,0,1,FVI_UNSUPPORTED,&selected));
    assert(!frame_vk_image_view_layers(1,0,64,64,1,0,1,FVI_2D,NULL));
    puts("image interfaces: bounded SPIR-V and compatible view ranges passed");
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'frame_vk_image.h').write_text(header)
            (root / 'test.c').write_text(program)
            binary = root / 'check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            str(root / 'test.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
