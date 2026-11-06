"""Exercise texture-copy subresources from the shipped Android backend patch."""
import sandbox  # noqa: F401
from nxnative_c import sanitizer_flags
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VulkanCopyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'native C compiler unavailable')
    def test_view_relative_array_layers_and_volume_depth(self):
        patch = (ROOT / 'frame/nxnative/android-frame.patch').read_text()
        sections = [s for s in patch.split('diff --git ')
                    if s.startswith('a/dm/android/src_vk/nvn_vk.c ')]
        self.assertEqual(len(sections), 1)
        source = '\n'.join(line[1:] for line in sections[0].splitlines()
                           if line.startswith((' ', '+')) and not line.startswith('+++'))
        # Both changed copy functions are complete in the shipped diff hunks.
        # Vulkan commands, resource lookup and the unchanged host bounds helper
        # are local fixtures; no private source or Vulkan SDK is required.
        start = source.index('// NVN copy-region z is relative')
        end = source.index('static void copy_t2b(', start)
        program = PREAMBLE + source[start:end] + CHECKS
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            (temporary / 'check.c').write_text(program)
            binary = temporary / 'check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-missing-field-initializers', '-Wno-misleading-indentation',
                            *sanitizer_flags('address,undefined'),
                            str(temporary / 'check.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


PREAMBLE = r'''#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef uintptr_t VkImage,VkCommandBuffer;
typedef unsigned VkFormat,VkImageAspectFlags,VkFormatFeatureFlags,VkImageLayout,VkFilter;
typedef struct {uint32_t width,height,depth;} VkExtent3D;
typedef struct {int32_t x,y,z;} VkOffset3D;
typedef struct {uint32_t aspectMask,mipLevel,baseArrayLayer,layerCount;} VkImageSubresourceLayers;
typedef struct {VkImageSubresourceLayers srcSubresource;VkOffset3D srcOffset;VkImageSubresourceLayers dstSubresource;VkOffset3D dstOffset;VkExtent3D extent;} VkImageCopy;
typedef struct {VkImageSubresourceLayers srcSubresource;VkOffset3D srcOffsets[2];VkImageSubresourceLayers dstSubresource;VkOffset3D dstOffsets[2];} VkImageBlit;
enum {VK_IMAGE_LAYOUT_GENERAL=1,VK_IMAGE_ASPECT_COLOR_BIT=1,VK_IMAGE_ASPECT_DEPTH_BIT=2,VK_FORMAT_R8G8B8A8_UNORM=37,VK_FORMAT_FEATURE_BLIT_SRC_BIT=1024,VK_FORMAT_FEATURE_BLIT_DST_BIT=2048,VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT=4096,VK_FILTER_NEAREST=0,VK_FILTER_LINEAR=1};

#define NVN_TEXTURE_TARGET_3D 2
#define NVN_TEXTURE_TARGET_1D_ARRAY 3
#define RED_ONCE(...) ((void)0)
#define LOG(...) ((void)0)
#define SK_T2T 2
static int vk_skip(void) {return 0;}
static int g_plog;
static int probe_trace(void) {return 1;}
static struct {VkCommandBuffer cb;} ctx,*C=&ctx;
typedef struct {VkFormat f;} fmt_t;
typedef struct vtex {uint64_t serial;int nvn_fmt,target;uint32_t w,h,d,layers,levels,samples;VkImageAspectFlags aspect;fmt_t f;VkImage img;} vtex;
typedef struct {vtex *mock;} tex_t;
typedef struct {int set_levels,set_layers;uint32_t base_level,min_layer,nlayers;} view_t;
typedef struct {int xoffset,yoffset,zoffset,width,height,depth;} NVNcopyRegion;
typedef struct {tex_t *src,*dst;view_t sv,dv;int has_sv,has_dv;NVNcopyRegion sr,dr;int flags;} p_copy_t2t;
static vtex *tex_get(const tex_t *t,int rt) {(void)rt;return t->mock;}
static VkFormatFeatureFlags fmt_feat(VkFormat f) {(void)f;return VK_FORMAT_FEATURE_BLIT_SRC_BIT|VK_FORMAT_FEATURE_BLIT_DST_BIT|VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT;}
static int end_calls,barrier_calls,copy_calls,blit_calls;static VkImageCopy last_copy;static VkImageBlit last_blit;static VkFilter last_filter;
static void pass_end(void) {end_calls++;}
static void barrier_all(VkCommandBuffer c) {(void)c;barrier_calls++;}
static uint32_t pixels[4][32][32];
static unsigned iid(VkImage i) {return (unsigned)(uintptr_t)i;}
static void vkCmdCopyImage(VkCommandBuffer cb,VkImage s,VkImageLayout sl,VkImage d,VkImageLayout dl,uint32_t n,const VkImageCopy *p) {
 (void)cb;assert(sl==VK_IMAGE_LAYOUT_GENERAL&&dl==sl&&n==1);copy_calls++;last_copy=*p;
 for(unsigned z=0;z<p->srcSubresource.layerCount;z++)pixels[iid(d)][p->dstSubresource.mipLevel][p->dstSubresource.baseArrayLayer+z]=pixels[iid(s)][p->srcSubresource.mipLevel][p->srcSubresource.baseArrayLayer+z];
}
static void vkCmdBlitImage(VkCommandBuffer cb,VkImage s,VkImageLayout sl,VkImage d,VkImageLayout dl,uint32_t n,const VkImageBlit *p,VkFilter f) {
 (void)cb;(void)s;(void)d;assert(sl==VK_IMAGE_LAYOUT_GENERAL&&dl==sl&&n==1);blit_calls++;last_blit=*p;last_filter=f;
}
static int lvl_fits(const vtex *v, uint32_t lv, uint32_t layer, uint32_t nlayers, int32_t x, int32_t y, int32_t z, uint32_t w, uint32_t h, uint32_t d) {
    if (lv >= v->levels || x < 0 || y < 0 || z < 0) return 0;
    uint32_t lw = v->w >> lv ? v->w >> lv : 1, lh = v->h >> lv ? v->h >> lv : 1, ld = v->d >> lv ? v->d >> lv : 1;
    if (v->target == NVN_TEXTURE_TARGET_1D_ARRAY) lh = 1;
    if ((uint64_t)x + w > lw || (uint64_t)y + h > lh || (uint64_t)z + d > ld) return 0;
    return v->target == NVN_TEXTURE_TARGET_3D || (uint64_t)layer + nlayers <= v->layers;
}
'''

CHECKS = r'''int main(void) {
 vtex a={.serial=1,.nvn_fmt=0x25,.target=9,.w=64,.h=32,.d=1,.layers=18,.levels=3,.samples=1,.aspect=VK_IMAGE_ASPECT_COLOR_BIT,.f={VK_FORMAT_R8G8B8A8_UNORM},.img=(VkImage)(uintptr_t)1}, b=a;b.serial=2;b.img=(VkImage)(uintptr_t)2;
 for(unsigned lv=0;lv<3;lv++)for(unsigned l=0;l<18;l++)pixels[1][lv][l]=1000+lv*100+l;
 tex_t at={&a},bt={&b};p_copy_t2t c={.src=&at,.dst=&bt,.has_sv=1,.has_dv=1,.sv={.set_levels=1,.base_level=1,.set_layers=1,.min_layer=6,.nlayers=12},.dv={.set_levels=1,.base_level=1,.set_layers=1,.min_layer=12,.nlayers=6},.sr={2,3,1,8,7,3},.dr={4,2,1,8,7,3}};
 copy_t2t(&c);assert(copy_calls==1&&blit_calls==0&&end_calls==1&&barrier_calls==1);
 assert(last_copy.srcSubresource.mipLevel==1&&last_copy.srcSubresource.baseArrayLayer==7&&last_copy.srcSubresource.layerCount==3);
 assert(last_copy.dstSubresource.baseArrayLayer==13&&last_copy.dstSubresource.layerCount==3&&last_copy.extent.depth==1&&last_copy.srcOffset.z==0);
 for(unsigned l=0;l<3;l++)assert(pixels[2][1][13+l]==pixels[1][1][7+l]);assert(!pixels[2][1][12]&&!pixels[2][1][16]);
 VkImageSubresourceLayers sub;VkOffset3D off;VkExtent3D extent;NVNcopyRegion r=c.sr;view_t vw=c.sv;
 assert(copy_region_plan(&a,&vw,1,&r,&sub,&off,&extent));vw.nlayers=3;r.zoffset=1;assert(!copy_region_plan(&a,&vw,1,&r,&sub,&off,&extent));vw=c.sv;r=c.sr;vw.min_layer=UINT32_MAX;assert(!copy_region_plan(&a,&vw,1,&r,&sub,&off,&extent));vw=c.sv;vw.base_level=32;assert(!copy_region_plan(&a,&vw,1,&r,&sub,&off,&extent));
 vw=c.sv;r.depth=-1;assert(!copy_region_plan(&a,&vw,1,&r,&sub,&off,&extent));r=c.sr;r.xoffset=-1;assert(!copy_region_plan(&a,&vw,1,&r,&sub,&off,&extent));r=c.sr;r.width=0;assert(!copy_region_plan(&a,&vw,1,&r,&sub,&off,&extent));r=c.sr;r.zoffset=INT32_MAX;assert(!copy_region_plan(&a,&vw,1,&r,&sub,&off,&extent));r=c.sr;assert(!copy_region_plan(&a,NULL,1,&r,&sub,&off,&extent));
 r=(NVNcopyRegion){0,0,0,64,32,0};assert(copy_region_plan(&a,NULL,0,&r,&sub,&off,&extent)&&sub.baseArrayLayer==0&&sub.layerCount==1&&extent.depth==1);r.width=65;assert(!copy_region_plan(&a,NULL,0,&r,&sub,&off,&extent));
 c.dr.width=4;c.dr.height=4;c.flags=1;copy_t2t(&c);assert(blit_calls==1&&last_filter==VK_FILTER_LINEAR&&last_blit.srcSubresource.baseArrayLayer==7&&last_blit.dstSubresource.baseArrayLayer==13&&last_blit.srcSubresource.layerCount==3);
 int copied=copy_calls,blitted=blit_calls;c.dr.depth=2;copy_t2t(&c);assert(copy_calls==copied&&blit_calls==blitted);c.dr.depth=3;a.samples=4;copy_t2t(&c);assert(copy_calls==copied&&blit_calls==blitted);a.samples=1;
 /* Volume coordinates must stay z offsets, never array layers. */
 a.target=b.target=2;a.d=b.d=8;a.layers=b.layers=1;c.has_sv=c.has_dv=0;c.sr=(NVNcopyRegion){1,2,2,8,8,3};c.dr=(NVNcopyRegion){2,1,3,8,8,3};copy_t2t(&c);assert(copy_calls==copied+1&&last_copy.srcSubresource.baseArrayLayer==0&&last_copy.srcSubresource.layerCount==1&&last_copy.srcOffset.z==2&&last_copy.dstOffset.z==3&&last_copy.extent.depth==3);
 c.sr=(NVNcopyRegion){0,0,0,8,8,4};c.dr=(NVNcopyRegion){0,0,1,4,4,2};copy_t2t(&c);assert(blit_calls==blitted+1&&last_blit.srcOffsets[1].z==4&&last_blit.dstOffsets[0].z==1&&last_blit.dstOffsets[1].z==3);
 copied=copy_calls;blitted=blit_calls;b.target=9;b.layers=18;c.dr.depth=4;copy_t2t(&c);assert(copy_calls==copied&&blit_calls==blitted); /* mixed volume/array rejected */
 puts("copy subresources: view-relative cube/array layers, actual copied contents, mips, multi-layer blits, 3D coordinates/depth, bounds and unsupported sample/dimension rejection passed");
}
'''
