"""Exercise feedback image copies and pass boundaries from the shipped backend patch."""
import sandbox  # noqa: F401
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VulkanFeedbackTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'native C compiler unavailable')
    def test_full_texture_contents_lifetime_and_pass_boundaries(self):
        patch = (ROOT / 'frame/nxnative/android-frame.patch').read_text()
        sections = [s for s in patch.split('diff --git ')
                    if s.startswith('a/dm/android/src_vk/nvn_vk.c ')]
        self.assertEqual(len(sections), 1)
        # Preserve context and additions. Both tested function blocks are fully
        # present in these shipped hunks; no private checkout is needed.
        source = '\n'.join(line[1:] for line in sections[0].splitlines()
                           if line.startswith((' ', '+')) and not line.startswith('+++'))
        feedback = source[source.index('// Same-pass feedback samples'):
                          source.index('// Bindless texture/sampler handles')]
        prepare = source[source.index('static int fb_prepare('):
                         source.index('static gw_t g_wb')]
        self.assertIn('tex_view(fb_sample_image(v, stage), &tr.t, &tr.v, tr.has_v, want_type, 0)', source)
        self.assertIn('if (fs && P.n) { if (!fb_prepare(fs)) SKIP(6); }', source)
        program = PREAMBLE + feedback + FIXTURE + prepare + CHECKS
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            (temporary / 'check.c').write_text(program)
            binary = temporary / 'check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-missing-field-initializers', '-Wno-misleading-indentation',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            '-pthread', str(temporary / 'check.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


PREAMBLE = r'''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
typedef uintptr_t VkDevice,VkImage,VkDeviceMemory,VkImageView,VkCommandBuffer;
typedef uint64_t VkDeviceSize;
typedef unsigned VkFormat,VkImageAspectFlags,VkMemoryPropertyFlags,VkSampleCountFlagBits,VkImageLayout;
typedef int VkResult;
typedef struct {int unused;} VkAllocationCallbacks;
typedef struct {uint32_t width,height,depth;} VkExtent3D;
typedef struct {int32_t x,y,z;} VkOffset3D;
typedef struct {uint32_t aspectMask,mipLevel,baseArrayLayer,layerCount;} VkImageSubresourceLayers;
typedef struct {VkImageSubresourceLayers srcSubresource;VkOffset3D srcOffset;VkImageSubresourceLayers dstSubresource;VkOffset3D dstOffset;VkExtent3D extent;} VkImageCopy;
typedef struct {unsigned sType;const void *pNext;unsigned flags,imageType;VkFormat format;VkExtent3D extent;unsigned mipLevels,arrayLayers,samples,tiling,usage,sharingMode,queueFamilyIndexCount;const unsigned *pQueueFamilyIndices;unsigned initialLayout;} VkImageCreateInfo;
typedef struct {uint64_t size,alignment;uint32_t memoryTypeBits;} VkMemoryRequirements;
enum {VK_SUCCESS=0,VK_ERROR_OUT_OF_DEVICE_MEMORY=-2,VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO=14,VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT=8,VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT=16,VK_IMAGE_TYPE_1D=0,VK_IMAGE_TYPE_2D=1,VK_IMAGE_TILING_OPTIMAL=0,VK_IMAGE_USAGE_SAMPLED_BIT=4,VK_IMAGE_USAGE_TRANSFER_DST_BIT=2,VK_SHARING_MODE_EXCLUSIVE=0,VK_IMAGE_LAYOUT_UNDEFINED=0,VK_IMAGE_LAYOUT_GENERAL=1,VK_IMAGE_ASPECT_COLOR_BIT=1,VK_IMAGE_ASPECT_DEPTH_BIT=2,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT=1,VK_FORMAT_R8G8B8A8_SRGB=43,VK_FORMAT_R8G8B8A8_UNORM=37};

#define NVN_TEXTURE_TARGET_1D 0
#define NVN_TEXTURE_TARGET_2D 1
#define NVN_TEXTURE_TARGET_3D 2
#define NVN_TEXTURE_TARGET_1D_ARRAY 3
#define NVN_TEXTURE_TARGET_2D_ARRAY 4
#define NVN_TEXTURE_TARGET_2D_MULTISAMPLE_ARRAY 6
#define NVN_TEXTURE_TARGET_CUBEMAP 7
#define NVN_TEXTURE_TARGET_CUBEMAP_ARRAY 8
#define LOG(...) ((void)0)
#define RED_ONCE(...) ((void)0)
#define VKCHECK(x) assert((x)==VK_SUCCESS)
typedef struct { VkFormat f; uint8_t noalpha,dec,depth,stencil; } fmt_t;
static fmt_t fmt_of(int n) { return (fmt_t){.f=n==0x38?VK_FORMAT_R8G8B8A8_SRGB:VK_FORMAT_R8G8B8A8_UNORM,.noalpha=n==0x6d}; }
typedef struct { uint64_t key; VkImageView v; } vview;
typedef struct vtex { uint64_t serial; VkImage img; VkDeviceMemory m; fmt_t f; int nvn_fmt,target; uint32_t w,h,d,levels,layers,samples; VkImageAspectFlags aspect; vview *views; int nviews; } vtex;
typedef struct { struct {int target,format;} d; int set_swz;uint32_t swz;vtex *mock; } tex_t;
typedef struct { int set_target,target,set_format,format,set_levels,set_layers,set_swizzle;uint32_t base_level,nlevels,min_layer,nlayers;uint8_t swz[4]; } view_t;
static VkDevice g_dev;
static struct { VkCommandBuffer cb; } ctx,*C=&ctx;
static struct {uint32_t clv[8],cly[8];uint8_t cwr[8];int n;vtex *ct[8];VkImageView cv[8];} P;
struct image {VkImageCreateInfo d;uint32_t pixels[32][64];};static struct image images[512];static unsigned ni,ncopies;static int fail_create;
static unsigned image_id(VkImage i) {return (unsigned)(uintptr_t)i;}
static VkResult vkCreateImage(VkDevice d,const VkImageCreateInfo *p,const VkAllocationCallbacks *a,VkImage *o) {(void)d;(void)a;if(fail_create)return VK_ERROR_OUT_OF_DEVICE_MEMORY;assert(ni+1<512);assert(p->arrayLayers<=64 && p->mipLevels<=32 && p->samples==1);*o=(VkImage)(uintptr_t)++ni;images[ni].d=*p;return VK_SUCCESS;}
static void vkGetImageMemoryRequirements(VkDevice d,VkImage i,VkMemoryRequirements *r) {(void)d;(void)i;*r=(VkMemoryRequirements){4096,256,1};}
static VkDeviceMemory mem_alloc(VkMemoryRequirements r,VkMemoryPropertyFlags p) {(void)r;(void)p;return (VkDeviceMemory)(uintptr_t)1;}
static VkResult vkBindImageMemory(VkDevice d,VkImage i,VkDeviceMemory m,VkDeviceSize o) {(void)d;(void)i;(void)m;(void)o;return VK_SUCCESS;}
static void to_general(VkCommandBuffer b,VkImage i,VkImageAspectFlags a) {(void)b;(void)i;assert(a==VK_IMAGE_ASPECT_COLOR_BIT);}
static void vkCmdCopyImage(VkCommandBuffer b,VkImage src,VkImageLayout sl,VkImage dst,VkImageLayout dl,uint32_t count,const VkImageCopy *p) {
 (void)b;assert(sl==VK_IMAGE_LAYOUT_GENERAL&&dl==sl&&count==1);struct image *s=&images[image_id(src)],*d=&images[image_id(dst)];
 assert(p->srcSubresource.aspectMask==VK_IMAGE_ASPECT_COLOR_BIT&&p->dstSubresource.aspectMask==VK_IMAGE_ASPECT_COLOR_BIT);
 unsigned lv=p->srcSubresource.mipLevel;assert(lv==p->dstSubresource.mipLevel&&lv<s->d.mipLevels&&lv<d->d.mipLevels);
 unsigned w=s->d.extent.width>>lv,h=s->d.extent.height>>lv;assert(p->extent.width==(w?w:1)&&p->extent.height==(h?h:1)&&p->extent.depth==1);
 assert(p->srcSubresource.baseArrayLayer==0&&p->dstSubresource.baseArrayLayer==0);
 assert(p->srcSubresource.layerCount==s->d.arrayLayers&&p->dstSubresource.layerCount==d->d.arrayLayers);
 for(unsigned l=0;l<p->srcSubresource.layerCount;l++)d->pixels[lv][l]=s->pixels[lv][l];ncopies++;
}
'''

FIXTURE = r'''#define BT_CIS 2
typedef struct {int type;uint32_t handle;} sbind;
typedef struct {int nb;sbind b[8];} shader_t;
typedef struct {int ok;tex_t t;} treg_t;
static treg_t g_treg[8];static int g_ntreg=8;static pthread_mutex_t g_rmu=PTHREAD_MUTEX_INITIALIZER;
static struct {struct {unsigned mask;} chmask;} S;
static uint32_t texture_handle(const sbind *b,int stage) {(void)stage;return b->handle;}
static vtex *tex_get(const tex_t *t,int rt) {(void)rt;return t->mock;}
static int pass_open,end_calls,begin_calls,barrier_calls;
static void pass_end(void) {assert(pass_open);pass_open=0;end_calls++;}
static int pass_begin(void) {assert(!pass_open);pass_open=1;begin_calls++;return 1;}
static void barrier_all(VkCommandBuffer cb) {(void)cb;assert(!pass_open);barrier_calls++;}
'''

CHECKS = r'''static vtex source(int target,unsigned layers,unsigned levels,unsigned serial) {
 vtex v={.serial=serial,.f=fmt_of(0x25),.nvn_fmt=0x25,.target=target,.w=64,.h=64,.d=1,.levels=levels,.layers=layers,.samples=1,.aspect=VK_IMAGE_ASPECT_COLOR_BIT};
 VkImageCreateInfo i={.extent={64,64,1},.mipLevels=levels,.arrayLayers=layers,.samples=1};assert(vkCreateImage(g_dev,&i,NULL,&v.img)==VK_SUCCESS);
 for(unsigned lv=0;lv<levels;lv++)for(unsigned l=0;l<layers;l++)images[image_id(v.img)].pixels[lv][l]=serial*1000+lv*100+l;
 return v;
}
static void copied(vtex *v,fbsnap_t *s) { assert(s&&s->image.img!=v->img);for(unsigned lv=0;lv<v->levels;lv++)for(unsigned l=0;l<v->layers;l++)assert(images[image_id(s->image.img)].pixels[lv][l]==images[image_id(v->img)].pixels[lv][l]); }
int main(void) {
 vtex a=source(NVN_TEXTURE_TARGET_CUBEMAP_ARRAY,12,3,1);P.cly[0]=7;P.clv[0]=1;P.cwr[0]=1;
 unsigned before=ncopies;fbsnap_t *sa=fb_snap_for(&a,0);copied(&a,sa);assert(ncopies==before+3);assert(images[image_id(sa->image.img)].d.flags&VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT);
 before=ncopies;assert(fb_snap_for(&a,0)==sa&&ncopies==before); /* unchanged attachment reuses its copy */
 images[image_id(a.img)].pixels[2][11]=777;P.cwr[0]=1;assert(fb_snap_for(&a,0)==sa);copied(&a,sa);
 g_fb_src[0]=&a;g_fb_snap[0]=sa;g_fb_n=1;assert(fb_sample_image(&a,1)==&sa->image&&fb_sample_image(&a,0)==&a);
 vtex b=source(NVN_TEXTURE_TARGET_CUBEMAP_ARRAY,12,3,2);P.cly[1]=0;P.clv[1]=0;P.cwr[1]=1;fbsnap_t *sb=fb_snap_for(&b,1);assert(sb&&sb!=sa);copied(&a,sa);copied(&b,sb); /* no same-draw cache collision */
 g_fb_n=0;vtex c=source(NVN_TEXTURE_TARGET_2D_ARRAY,4,2,3);P.cwr[0]=1;P.clv[0]=0;P.cly[0]=2;fbsnap_t *sc=fb_snap_for(&c,0);copied(&c,sc);assert(!(images[image_id(sc->image.img)].d.flags&VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT));
 before=ncopies;a.samples=4;assert(!fb_snap_for(&a,0)&&ncopies==before);a.samples=1;a.aspect=VK_IMAGE_ASPECT_DEPTH_BIT;assert(!fb_snap_for(&a,0));a.aspect=VK_IMAGE_ASPECT_COLOR_BIT;a.levels=33;assert(!fb_snap_for(&a,0));a.levels=3;P.clv[0]=3;assert(!fb_snap_for(&a,0));P.clv[0]=0;P.cly[0]=12;assert(!fb_snap_for(&a,0));P.cly[0]=0;a.target=NVN_TEXTURE_TARGET_3D;assert(!fb_snap_for(&a,0));
 /* Reused guest-object address cannot reuse stale contents after serial change. */
 a.target=NVN_TEXTURE_TARGET_CUBEMAP_ARRAY;a.serial=9;images[image_id(a.img)].pixels[0][0]=999;P.cwr[0]=0;before=ncopies;sa=fb_snap_for(&a,0);assert(ncopies==before+3);copied(&a,sa);
 fail_create=1;vtex fail=c;fail.w=32;assert(!fb_snap_for(&fail,0));fail_create=0;
 /* Cache exhaustion cannot fall back to an incompatible or live source image. */
 int old=g_nfbs;g_nfbs=16;fail.w=31;assert(!fb_snap_for(&fail,0));g_nfbs=old;
 /* Execute the actual preparation integration: close/copy/barrier/reopen. */
 P.n=2;P.ct[0]=&a;P.ct[1]=&b;P.cv[0]=(VkImageView)(uintptr_t)1;P.cv[1]=(VkImageView)(uintptr_t)2;P.cwr[0]=P.cwr[1]=1;
 S.chmask.mask=0xff;g_treg[1]=(treg_t){.ok=1,.t={.mock=&a}};g_treg[2]=(treg_t){.ok=1,.t={.mock=&b}};
 shader_t fs={.nb=2,.b={{BT_CIS,1},{BT_CIS,2}}};pass_open=1;
 assert(fb_prepare(&fs));assert(pass_open&&end_calls==1&&begin_calls==1&&barrier_calls==1&&g_fb_n==2);assert(g_fb_snap[0]!=g_fb_snap[1]);copied(&a,g_fb_snap[0]);copied(&b,g_fb_snap[1]);
 a.samples=4;P.cwr[0]=1;assert(!fb_prepare(&fs));assert(pass_open);a.samples=1;
 shader_t empty={0};assert(fb_prepare(&empty)&&g_fb_n==0); /* failure is not sticky */
 for(int j=0;j<g_nfbs;j++)free(g_fbs[j].image.views);
 puts("feedback snapshot: full cube/array levels and contents, ownership, reuse, collisions and rejected unsupported shapes passed");
}
'''
