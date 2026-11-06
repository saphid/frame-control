"""Execute null-image binding/initialization code from the Android patch we ship.

The minimal Vulkan declarations below model only this code's API boundary. No
Android checkout, Vulkan SDK, captured shaders or private game files are needed.
"""
import sandbox  # noqa: F401
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PATCH = Path(__file__).resolve().parents[1] / 'frame/nxnative/android-frame.patch'


def patched_source(path, *, new_file=False):
    sections = [section for section in PATCH.read_text().split('diff --git ')
                if section.startswith(f'a/{path} ')]
    if len(sections) != 1:
        raise AssertionError(f'expected one shipped patch section for {path}')
    prefixes = ('+',) if new_file else (' ', '+')
    return '\n'.join(line[1:] for line in sections[0].splitlines()
                     if line.startswith(prefixes) and not line.startswith('+++'))


def function(source, signature):
    """Require the complete real function, including unchanged patch context."""
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    for at in range(opening + 1, len(source)):
        depth += (source[at] == '{') - (source[at] == '}')
        if depth == 0:
            return source[start:at + 1] + '\n'
    raise AssertionError(f'patch must retain full function context: {signature}')


@unittest.skipUnless(shutil.which('cc'), 'native C compiler unavailable')
class VulkanNullImageTests(unittest.TestCase):
    def compile_and_run(self, program, header=''):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'frame_vk_image.h').write_text(header)
            (root / 'check.c').write_text(program)
            binary = root / 'check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-missing-field-initializers', '-Wno-misleading-indentation',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            '-pthread', str(root / 'check.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_reflected_null_eligibility_and_real_descriptor_selection(self):
        source = patched_source('dm/android/src_vk/nvn_vk.c')
        header = patched_source('dm/android/src_vk/frame_vk_image.h', new_file=True)
        # A correct standalone helper must also reach actual descriptor writes.
        self.assertIn('b->image_null_black = frame_vk_image_null_black(image);', source)
        self.assertIn('b->image_view, b->image_ms, b->image_null_black)', source)
        self.compile_and_run(SLOT_PREAMBLE + function(source, 'static VkImageView tex_slot(')
                             + SLOT_CHECKS, header)

    def test_all_cube_faces_initialized_and_visible_before_completion(self):
        source = patched_source('dm/android/src_vk/nvn_vk.c')
        actual = ''.join(function(source, name) for name in (
            'static void barrier_all(VkCommandBuffer',
            'static void to_general(VkCommandBuffer', 'static void dummies(void) {'))
        self.compile_and_run(INIT_PREAMBLE + actual + INIT_CHECKS)


SLOT_PREAMBLE = r'''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include "frame_vk_image.h"
typedef uintptr_t VkImageView, VkSampler;
enum {VK_NULL_HANDLE=0, VK_IMAGE_VIEW_TYPE_2D=1, VK_IMAGE_VIEW_TYPE_CUBE=3};
#define LOG(...) ((void)0)
#define RED_ONCE(...) ((void)0)
typedef struct vtex {uint64_t serial; unsigned samples,w,h,d,levels,layers; int gpu,uploaded;} vtex;
typedef struct {int ignored;} view_t;
typedef struct {uint64_t serial; struct {int target,format,flags;} d; const void *mem; struct {uint64_t size;} L; struct {int flags;} *pool; int has_layout;} tex_t;
typedef struct {int ok; tex_t t; view_t v; int has_v;} treg_t;
static treg_t g_treg[4]; static int g_ntreg=4,g_plog;
static pthread_mutex_t g_rmu=PTHREAD_MUTEX_INITIALIZER;
static VkImageView g_dummy_view=7,g_dummy_cube_view=10; static VkSampler g_dummy_samp=8;
static uint64_t g_tex_miss[4]; static vtex image={.serial=22,.samples=1};
static int create_fail,view_fail,texture_get_calls,views,last_wanted;
static vtex *tex_get(const tex_t *t,int rt) {(void)t;(void)rt;texture_get_calls++;return create_fail?NULL:&image;}
static vtex *fb_sample_image(vtex *v,int stage) {(void)stage;return v;}
static VkImageView tex_view(vtex *v,const tex_t *t,const view_t *vw,int has,int wanted,int rt) {
    (void)v;(void)t;(void)vw;(void)has;(void)rt;views++;last_wanted=wanted;return view_fail?VK_NULL_HANDLE:9;
}
'''

SLOT_CHECKS = r'''static uint32_t words[128]; static size_t n;
static void emit(const uint32_t *p,size_t k) {assert(n+k<=128);memcpy(words+n,p,k*4);n+=k;}
#define E(...) do {const uint32_t p[]={__VA_ARGS__};emit(p,sizeof p/sizeof *p);} while(0)
/* scalar: float32, float64, float16, signed/unsigned int, bool, undefined. */
static void module(int scalar,int dim,int array,int ms,int descriptors,int depth,int sampled) {
    memset(words,0,sizeof words);n=5;words[0]=0x07230203;words[1]=0x10000;words[3]=64;
    E(4u<<16|71,5,33,7);E(4u<<16|71,5,34,0);
    if(scalar<=2) {E(3u<<16|22,1,scalar==0?32u:scalar==1?64u:16u);}
    else if(scalar<=4) {E(4u<<16|21,1,32,scalar==3?1u:0u);}
    else if(scalar==5) {E(2u<<16|20,1);}
    E(9u<<16|25,2,1,(uint32_t)dim,(uint32_t)depth,(uint32_t)array,(uint32_t)ms,(uint32_t)sampled,0);
    E(3u<<16|27,3,2);
    if(descriptors) {E(4u<<16|28,6,3,7);E(4u<<16|32,4,0,6);}
    else {E(4u<<16|32,4,0,3);}
    E(4u<<16|59,4,5,0);
}
int main(void) {
    frame_vk_image_binding out[1];size_t count;
    /* The full matrix comes from real reflection, then executes real tex_slot. */
    for(int scalar=0;scalar<=5;scalar++)for(int dim=0;dim<=6;dim++)
    for(int array=0;array<=1;array++)for(int ms=0;ms<=1;ms++)
    for(int descriptors=0;descriptors<=1;descriptors++)
    for(int depth=0;depth<=2;depth++)for(int sampled=0;sampled<=2;sampled++) {
        module(scalar,dim,array,ms,descriptors,depth,sampled);
        assert(frame_vk_image_reflect(words,n,out,1,&count)&&count==1);
        int eligible=scalar==0&&(dim==1||dim==3)&&!array&&!ms&&!descriptors&&!depth&&sampled==1;
        assert(out[0].float32==(scalar==0)&&out[0].depth==depth&&out[0].sampled==sampled);
        assert(frame_vk_image_null_black(out)==eligible);
        VkSampler sampler=0;int ok=99;vtex *v=&image;
        VkImageView selected=tex_slot(1,0,&sampler,&ok,&v,out[0].view,out[0].ms,frame_vk_image_null_black(out));
        assert(ok==eligible&&!v&&!texture_get_calls&&!views);
        assert(selected==(eligible?(dim==1?g_dummy_view:g_dummy_cube_view):VK_NULL_HANDLE));
        assert(sampler==(eligible?g_dummy_samp:VK_NULL_HANDLE));
    }
    assert(!frame_vk_image_null_black(NULL));
    module(6,1,0,0,0,0,1);assert(!frame_vk_image_reflect(words,n,out,1,&count)&&!count);
    /* Literal full zero alone is eligible; sampler bits cannot disguise invalid handles. */
    VkSampler sampler=0;int ok;vtex *v=&image;VkImageView selected;
    selected=tex_slot(1,UINT64_C(1)<<20,&sampler,&ok,&v,FVI_2D,0,1);assert(!selected&&!ok&&!v&&!texture_get_calls);
    selected=tex_slot(1,UINT64_C(1)<<63,&sampler,&ok,&v,FVI_CUBE,0,1);assert(!selected&&!ok&&!v&&!texture_get_calls);
    uint64_t before=g_tex_miss[1];
    selected=tex_slot(1,1,&sampler,&ok,&v,FVI_2D,0,1);assert(!selected&&!ok&&g_tex_miss[1]==before+1&&!texture_get_calls);
    selected=tex_slot(1,4,&sampler,&ok,&v,FVI_2D,0,1);assert(!selected&&!ok&&!texture_get_calls);
    g_treg[1].ok=1;create_fail=1;
    selected=tex_slot(1,1,&sampler,&ok,&v,FVI_2D,0,1);assert(!selected&&!ok&&g_tex_miss[2]==1);create_fail=0;
    image.samples=4;selected=tex_slot(1,1,&sampler,&ok,&v,FVI_2D,0,1);assert(!selected&&!ok&&!views);image.samples=1;
    selected=tex_slot(1,1,&sampler,&ok,&v,FVI_2D,1,1);assert(!selected&&!ok&&!views);
    view_fail=1;selected=tex_slot(1,1,&sampler,&ok,&v,FVI_CUBE,0,1);assert(!selected&&!ok&&g_tex_miss[3]==1);view_fail=0;
    selected=tex_slot(1,1,&sampler,&ok,&v,FVI_CUBE,0,0);assert(selected==9&&ok&&v==&image&&last_wanted==FVI_CUBE);
    /* Also exercise optional outputs and absent fallback resources. */
    selected=tex_slot(1,0,NULL,&ok,NULL,FVI_CUBE,0,1);assert(selected==g_dummy_cube_view&&ok);
    g_dummy_cube_view=0;selected=tex_slot(1,0,&sampler,&ok,&v,FVI_CUBE,0,1);assert(!selected&&!ok);
    g_dummy_view=0;selected=tex_slot(1,0,&sampler,&ok,&v,FVI_2D,0,1);assert(!selected&&!ok);
    g_dummy_view=7;g_dummy_samp=0;selected=tex_slot(1,0,&sampler,&ok,&v,FVI_2D,0,1);assert(!selected&&!ok);
    /* Keep existing compatible-view guard covered in the included real header. */
    uint32_t layers;assert(frame_vk_image_view_layers(1,1,1,1,6,0,6,FVI_CUBE,&layers)&&layers==6);
    puts("null reflection/binding: 3024 type/shape interfaces and invalid resource cases passed");
}
'''

INIT_PREAMBLE = r'''#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef uintptr_t VkDevice,VkSampler,VkImage,VkImageView,VkBuffer,VkDeviceMemory,VkCommandBuffer;
typedef uint64_t VkDeviceSize;
typedef unsigned VkMemoryPropertyFlags,VkBufferUsageFlags,VkPipelineStageFlags,VkDependencyFlags,VkImageAspectFlags,VkImageLayout;
typedef int VkResult;
typedef struct {int unused;} VkAllocationCallbacks;
typedef struct {uint32_t width,height,depth;} VkExtent3D;
typedef struct {uint32_t aspectMask,baseMipLevel,levelCount,baseArrayLayer,layerCount;} VkImageSubresourceRange;
typedef struct {unsigned sType;const void *pNext;unsigned srcAccessMask,dstAccessMask;} VkMemoryBarrier;
typedef struct {int unused;} VkBufferMemoryBarrier;
typedef struct {unsigned sType;const void *pNext;unsigned srcAccessMask,dstAccessMask,oldLayout,newLayout,srcQueueFamilyIndex,dstQueueFamilyIndex;VkImage image;VkImageSubresourceRange subresourceRange;} VkImageMemoryBarrier;
typedef struct {unsigned sType;const void *pNext;unsigned flags,imageType,format;VkExtent3D extent;unsigned mipLevels,arrayLayers,samples,tiling,usage,sharingMode,queueFamilyIndexCount;const unsigned *pQueueFamilyIndices;unsigned initialLayout;} VkImageCreateInfo;
typedef struct {unsigned r,g,b,a;} VkComponentMapping;
typedef struct {unsigned sType;const void *pNext;unsigned flags;VkImage image;unsigned viewType,format;VkComponentMapping components;VkImageSubresourceRange subresourceRange;} VkImageViewCreateInfo;
typedef struct {unsigned sType;const void *pNext;unsigned flags,magFilter,minFilter,mipmapMode,addressModeU,addressModeV,addressModeW;float mipLodBias;unsigned anisotropyEnable;float maxAnisotropy;unsigned compareEnable,compareOp;float minLod,maxLod;unsigned borderColor,unnormalizedCoordinates;} VkSamplerCreateInfo;
typedef struct {VkDeviceSize size,alignment;uint32_t memoryTypeBits;} VkMemoryRequirements;
typedef union {float float32[4];int32_t int32[4];uint32_t uint32[4];} VkClearColorValue;
enum {VK_SUCCESS=0,VK_STRUCTURE_TYPE_MEMORY_BARRIER=46,VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER=45,VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO=31,VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO=14,VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO=15,VK_ACCESS_MEMORY_READ_BIT=0x8000,VK_ACCESS_MEMORY_WRITE_BIT=0x10000,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT=0x10000,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT=1,VK_IMAGE_LAYOUT_UNDEFINED=0,VK_IMAGE_LAYOUT_GENERAL=1,VK_FILTER_LINEAR=1,VK_IMAGE_TYPE_2D=1,VK_FORMAT_R8G8B8A8_UNORM=37,VK_SAMPLE_COUNT_1_BIT=1,VK_IMAGE_TILING_OPTIMAL=0,VK_IMAGE_USAGE_SAMPLED_BIT=4,VK_IMAGE_USAGE_TRANSFER_DST_BIT=2,VK_SHARING_MODE_EXCLUSIVE=0,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT=1,VK_IMAGE_VIEW_TYPE_2D=1,VK_IMAGE_VIEW_TYPE_CUBE=3,VK_IMAGE_ASPECT_COLOR_BIT=1,VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT=16};
#define VK_QUEUE_FAMILY_IGNORED UINT32_MAX
#define VK_REMAINING_MIP_LEVELS UINT32_MAX
#define VK_REMAINING_ARRAY_LAYERS UINT32_MAX
#define VKCHECK(x) assert((x)==VK_SUCCESS)
#define ALL_BUF_USAGE 3u
static VkDevice g_dev;
static VkSampler g_dummy_samp;static VkImage g_dummy_img,g_dummy_cube_img;static VkImageView g_dummy_view,g_dummy_cube_view;static VkBuffer g_zero_buf,g_support_buf;static VkDeviceMemory g_zero_mem,g_support_mem;
static unsigned images,views,clears,memory_barriers,done,transitioned[3];static float pixels[3][6][4];static void *buffers[2];static unsigned nbuf;
static VkResult vkCreateSampler(VkDevice d,const VkSamplerCreateInfo *p,const VkAllocationCallbacks *a,VkSampler *out) {
    (void)d;(void)a;assert(p->sType==VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO&&p->magFilter==VK_FILTER_LINEAR&&p->minFilter==VK_FILTER_LINEAR&&p->maxLod==0);*out=20;return VK_SUCCESS;
}
static VkResult vkCreateImage(VkDevice d,const VkImageCreateInfo *p,const VkAllocationCallbacks *a,VkImage *out) {
    (void)d;(void)a;images++;
    assert(images<=2&&p->sType==VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO&&p->imageType==VK_IMAGE_TYPE_2D&&p->format==VK_FORMAT_R8G8B8A8_UNORM&&p->extent.width==1&&p->extent.height==1&&p->extent.depth==1&&p->mipLevels==1&&p->samples==VK_SAMPLE_COUNT_1_BIT&&p->initialLayout==VK_IMAGE_LAYOUT_UNDEFINED&&p->usage==(VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT));
    assert(p->arrayLayers==(images==1?1:6)&&p->flags==(images==1?0:VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT));
    for(unsigned l=0;l<6;l++)for(unsigned c=0;c<4;c++)pixels[images][l][c]=99;
    *out=images;return VK_SUCCESS;
}
static void vkGetImageMemoryRequirements(VkDevice d,VkImage i,VkMemoryRequirements *r) {(void)d;assert(i==images);*r=(VkMemoryRequirements){4096,4096,1};}
static VkDeviceMemory mem_alloc(VkMemoryRequirements r,VkMemoryPropertyFlags f) {assert(r.size==4096&&f==VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);return 30;}
static VkResult vkBindImageMemory(VkDevice d,VkImage i,VkDeviceMemory m,VkDeviceSize o) {(void)d;assert(i==images&&m==30&&!o);return VK_SUCCESS;}
static VkResult vkCreateImageView(VkDevice d,const VkImageViewCreateInfo *p,const VkAllocationCallbacks *a,VkImageView *out) {
    (void)d;(void)a;views++;
    assert(p->sType==VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO&&p->image==views&&p->format==VK_FORMAT_R8G8B8A8_UNORM&&p->viewType==(views==1?VK_IMAGE_VIEW_TYPE_2D:VK_IMAGE_VIEW_TYPE_CUBE)&&p->subresourceRange.aspectMask==VK_IMAGE_ASPECT_COLOR_BIT&&!p->subresourceRange.baseMipLevel&&p->subresourceRange.levelCount==1&&!p->subresourceRange.baseArrayLayer&&p->subresourceRange.layerCount==(views==1?1:6));
    *out=10+views;return VK_SUCCESS;
}
static VkBuffer buf_new(VkDeviceSize bytes,VkBufferUsageFlags u,VkDeviceMemory *m,void **p) {
    assert(nbuf<2&&u==ALL_BUF_USAGE);buffers[nbuf]=malloc(bytes);assert(buffers[nbuf]);memset(buffers[nbuf],1,bytes);*p=buffers[nbuf++];*m=40;return 50;
}
static VkCommandBuffer once_begin(void) {assert(!clears&&!done);return 60;}
static void once_end(VkCommandBuffer cb) {assert(cb==60&&clears==2&&memory_barriers==1);done++;}
static void vkCmdPipelineBarrier(VkCommandBuffer cb,VkPipelineStageFlags src,VkPipelineStageFlags dst,VkDependencyFlags flags,uint32_t nm,const VkMemoryBarrier *m,uint32_t nb,const VkBufferMemoryBarrier *b,uint32_t ni,const VkImageMemoryBarrier *im) {
    (void)b;assert(cb==60&&!flags&&!nb&&!done);
    if(ni) {
        assert(ni==1&&!nm&&src==VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT&&dst==VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
        unsigned i=(unsigned)im->image;
        assert(i>=1&&i<=2&&!transitioned[i]&&im->sType==VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER&&im->oldLayout==VK_IMAGE_LAYOUT_UNDEFINED&&im->newLayout==VK_IMAGE_LAYOUT_GENERAL&&im->srcQueueFamilyIndex==VK_QUEUE_FAMILY_IGNORED&&im->dstQueueFamilyIndex==VK_QUEUE_FAMILY_IGNORED&&im->subresourceRange.aspectMask==VK_IMAGE_ASPECT_COLOR_BIT&&!im->subresourceRange.baseMipLevel&&im->subresourceRange.levelCount==VK_REMAINING_MIP_LEVELS&&!im->subresourceRange.baseArrayLayer&&im->subresourceRange.layerCount==VK_REMAINING_ARRAY_LAYERS);
        transitioned[i]=1;
    } else {
        assert(nm==1&&clears==2&&src==VK_PIPELINE_STAGE_ALL_COMMANDS_BIT&&dst==VK_PIPELINE_STAGE_ALL_COMMANDS_BIT&&m->sType==VK_STRUCTURE_TYPE_MEMORY_BARRIER&&(m->srcAccessMask&VK_ACCESS_MEMORY_WRITE_BIT)&&(m->dstAccessMask&VK_ACCESS_MEMORY_READ_BIT));memory_barriers++;
    }
}
static void vkCmdClearColorImage(VkCommandBuffer cb,VkImage image,VkImageLayout layout,const VkClearColorValue *c,uint32_t nr,const VkImageSubresourceRange *r) {
    assert(cb==60&&layout==VK_IMAGE_LAYOUT_GENERAL&&nr==1&&!memory_barriers&&!done);unsigned i=(unsigned)image;
    assert(i>=1&&i<=2&&transitioned[i]&&r->aspectMask==VK_IMAGE_ASPECT_COLOR_BIT&&!r->baseMipLevel&&r->levelCount==1&&!r->baseArrayLayer&&r->layerCount==(i==1?1:6));
    assert(c->float32[0]==0&&c->float32[1]==0&&c->float32[2]==0&&c->float32[3]==1);
    for(unsigned l=0;l<r->layerCount;l++)memcpy(pixels[i][l],c->float32,sizeof pixels[i][l]);clears++;
}
'''

INIT_CHECKS = r'''int main(void) {
    dummies();assert(images==2&&views==2&&clears==2&&done==1&&g_dummy_img!=g_dummy_cube_img&&g_dummy_view!=g_dummy_cube_view);
    for(unsigned l=0;l<6;l++)for(unsigned c=0;c<4;c++)assert(pixels[2][l][c]==(c==3?1:0));
    for(unsigned c=0;c<4;c++)assert(pixels[1][0][c]==(c==3?1:0));
    for(size_t b=0;b<65536;b++)assert(((uint8_t*)buffers[0])[b]==0);
    for(unsigned i=0;i<73;i++)assert(*(float*)((uint8_t*)buffers[1]+192+16*i)==1);
    for(unsigned i=0;i<nbuf;i++)free(buffers[i]);
    puts("null initialization: separate 2D/Cube images, all six black faces, full transitions, write visibility and completion ordering passed");
}
'''
