"""Exercise texture initialization and attachment formats from the shipped patch."""
import sandbox  # noqa: F401
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def shipped_source():
    patch = (ROOT / 'frame/nxnative/android-frame.patch').read_text()
    sections = [s for s in patch.split('diff --git ')
                if s.startswith('a/dm/android/src_vk/nvn_vk.c ')]
    if len(sections) != 1:
        raise AssertionError('shipped patch must contain one Vulkan backend section')
    return '\n'.join(line[1:] for line in sections[0].splitlines()
                     if line.startswith((' ', '+')) and not line.startswith('+++'))


def block(source, marker):
    """Extract one complete C block present in the shipped patch hunks."""
    start = source.index(marker)
    brace = source.index('{', start)
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if depth == 0:
                return source[start:end + 1]
    raise AssertionError('incomplete shipped C block: ' + marker)


@unittest.skipUnless(shutil.which('cc'), 'native C compiler unavailable')
class VulkanTextureTests(unittest.TestCase):
    def compile_and_run(self, program):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            (temporary / 'check.c').write_text(program)
            binary = temporary / 'check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-missing-field-initializers', '-Wno-misleading-indentation',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            str(temporary / 'check.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_new_color_render_targets_clear_all_faces_and_mips(self):
        source = shipped_source()
        start = source.index('    int packaged = ')
        end = source.index('    return v;', start)
        # Execute the actual initialization policy with mocked upload commands.
        policy = source[start:end]
        program = INIT_MOCKS + '\nstatic void initialize(vtex *v, const tex_t *t, int for_rt, fmt_t f, unsigned sc) {\n' + policy + '\n}\n' + INIT_CHECKS
        self.compile_and_run(program)

    def test_view_format_agrees_with_pass_and_pipeline(self):
        source = shipped_source()
        helper = block(source, 'static fmt_t tex_view_format(')
        self.assertIn('fmt_t f = tex_view_format(v, t, vw, has_vw);', source)
        color_select = re.search(r'P\.cf\[i\] = tex_view_format\([^;]+;', source).group()
        depth_select = re.search(r'P\.df = tex_view_format\([^;]+;', source).group()
        pass_color = next(line for line in source.splitlines()
                          if 'd.cv[i] = P.cv[i]; d.cf[i]' in line)
        pass_depth = block(source, 'if (P.dt) { d.dv = P.dv;')
        pipeline_color = next(line for line in source.splitlines()
                              if 'k.nc = P.n; for' in line)
        pipeline_depth = block(source, 'if (P.dt) { k.df = P.df;')
        # Execute actual format selection and both consumers, including missing
        # views and decoded-format fallbacks, without compiling the entire GPU.
        program = FORMAT_MOCKS + helper + '\nstatic void select_color(vtex *v, const p_set_rt *r) {\nint i=0;\n' + color_select + '\n}\nstatic void select_depth(vtex *v, const p_set_rt *r) {\n' + depth_select + '\n}\nstatic void consume(void) {\n' + pass_color + '\n' + pass_depth + '\n' + pipeline_color + '\n' + pipeline_depth + '\n}\n' + FORMAT_CHECKS
        self.compile_and_run(program)


INIT_MOCKS = r'''#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef uintptr_t VkImage,VkCommandBuffer;
typedef union {float float32[4];uint32_t uint32[4];} VkClearColorValue;
typedef struct {uint32_t aspectMask,baseMipLevel,levelCount,baseArrayLayer,layerCount;} VkImageSubresourceRange;
enum {VK_IMAGE_ASPECT_COLOR_BIT=1,VK_IMAGE_LAYOUT_GENERAL=1,VK_SAMPLE_COUNT_1_BIT=1};
#define VK_REMAINING_MIP_LEVELS UINT32_MAX
#define VK_REMAINING_ARRAY_LAYERS UINT32_MAX
typedef struct {int depth;} fmt_t;
typedef struct {VkImage img;unsigned linrow;} vtex;
typedef struct {unsigned serial;int has_layout;const uint8_t *mem;} tex_t;
static struct {VkCommandBuffer up;} context={17},*C=&context;
static uint32_t pixels[5][12];static unsigned clear_calls,upload_calls;static int written,initial_fill;
static int cpu_written(unsigned serial) {(void)serial;return written;}
static int init_fill(const tex_t *t,const fmt_t *f) {(void)t;(void)f;return initial_fill;}
static void tex_upload(vtex *v,const tex_t *t) {(void)v;assert(t->mem);upload_calls++;}
static void vkCmdClearColorImage(VkCommandBuffer cb,VkImage image,unsigned layout,const VkClearColorValue *value,unsigned count,const VkImageSubresourceRange *range) {
 assert(cb==C->up&&image==1&&layout==VK_IMAGE_LAYOUT_GENERAL&&count==1);
 assert(range->aspectMask==VK_IMAGE_ASPECT_COLOR_BIT&&range->baseMipLevel==0&&range->levelCount==VK_REMAINING_MIP_LEVELS&&range->baseArrayLayer==0&&range->layerCount==VK_REMAINING_ARRAY_LAYERS);
 for(unsigned i=0;i<4;i++)assert(value->uint32[i]==0);
 for(unsigned lv=0;lv<5;lv++)for(unsigned layer=0;layer<12;layer++)pixels[lv][layer]=value->uint32[0];clear_calls++;
}
static void poison(void) {memset(pixels,0xa5,sizeof pixels);}
'''

INIT_CHECKS = r'''
int main(void) {
 vtex v={.img=1};uint8_t guest[64],before[64];memset(guest,0x5a,sizeof guest);memcpy(before,guest,sizeof guest);tex_t t={.serial=1,.mem=guest};fmt_t color={0},depth={1};
 poison();initialize(&v,&t,1,color,1);assert(clear_calls==1&&upload_calls==0);
 for(unsigned lv=0;lv<5;lv++)for(unsigned l=0;l<12;l++)assert(pixels[lv][l]==0);assert(!memcmp(guest,before,sizeof guest));
 poison();initialize(&v,&t,0,color,1);assert(clear_calls==2&&pixels[4][11]==0);
 poison();t.has_layout=1;initialize(&v,&t,0,color,1);assert(upload_calls==1&&clear_calls==2&&pixels[4][11]==0xa5a5a5a5);
 t.has_layout=0;written=1;initialize(&v,&t,0,color,1);assert(upload_calls==2&&clear_calls==2);written=0;v.linrow=64;initialize(&v,&t,0,color,1);assert(upload_calls==3);v.linrow=0;initial_fill=1;initialize(&v,&t,0,color,1);assert(upload_calls==4);initial_fill=0;
 poison();initialize(&v,&t,1,depth,1);initialize(&v,&t,1,color,4);assert(clear_calls==2&&upload_calls==4&&pixels[0][0]==0xa5a5a5a5);assert(!memcmp(guest,before,sizeof guest));
 puts("texture initialization: new color RT faces/mips cleared in upload command buffer, packaged/CPU/linear uploads preserved, depth/MS excluded and guest storage untouched");
}
'''

FORMAT_MOCKS = r'''#include <stdint.h>
#include <stdio.h>
#include <assert.h>
typedef unsigned VkFormat;
typedef struct {float depth;unsigned stencil;} VkClearDepthStencilValue;
enum {VK_FORMAT_UNDEFINED=0,VK_ATTACHMENT_LOAD_OP_CLEAR=1,VK_ATTACHMENT_LOAD_OP_LOAD=2};
typedef struct {VkFormat f;unsigned noalpha,dec,depth,stencil;} fmt_t;
typedef struct {fmt_t f;} vtex;
typedef struct {struct {int format;} d;} tex_t;
typedef struct {int set_format,format;} view_t;
typedef struct {const tex_t *color[8],*depth;view_t cview[8],dview;int has_cview[8],has_dview;} p_set_rt;
static fmt_t fmt_of(int n) {
 switch(n) {
 case 0x25:return (fmt_t){.f=37};case 0x38:return (fmt_t){.f=43};
 case 0x44:return (fmt_t){.f=37,.dec=3};case 0x48:return (fmt_t){.f=43,.dec=3};
 case 0x34:return (fmt_t){.f=126,.depth=1};case 0x36:return (fmt_t){.f=130,.depth=1,.stencil=1};
 default:return (fmt_t){0};
 }
}
static struct {int n;vtex *ct[8],*dt;unsigned cv[8],dv;VkFormat cf[8],df;unsigned clr_c[8],cdrawn[8],clr_d,clr_s,cc[8],cs;float cd;} P;
static struct {unsigned cv[8],dv;VkFormat cf[8],df;unsigned cl[8],cc[8],dl,sl,stencil;VkClearDepthStencilValue dc;} d;
static struct {int nc;VkFormat cf[8],df;unsigned blend[8],stencil,ds;} k;
static struct {unsigned blend[8],ds;} S;
'''

FORMAT_CHECKS = r'''
int main(void) {
 vtex color={.f={.f=37}},depth={.f={.f=130,.depth=1,.stencil=1}};tex_t t={.d={0x25}};
 p_set_rt rt={.color={&t},.depth=&t,.cview={{.set_format=1,.format=0x38}},.dview={.set_format=1,.format=0x36},.has_cview={1},.has_dview=1};
 select_color(&color,&rt);select_depth(&depth,&rt);assert(P.cf[0]==43&&P.df==130);P.n=1;P.ct[0]=&color;P.cv[0]=7;P.dt=&depth;P.dv=8;P.df=130;P.clr_c[0]=1;S.blend[0]=9;S.ds=11;consume();
 assert(d.cf[0]==43&&k.cf[0]==43&&color.f.f==37&&d.df==130&&k.df==130&&d.stencil==1&&k.stencil==1&&k.blend[0]==9&&k.ds==11);
 P.cv[0]=0;consume();assert(d.cf[0]==VK_FORMAT_UNDEFINED&&k.cf[0]==VK_FORMAT_UNDEFINED);
 rt.has_cview[0]=0;select_color(&color,&rt);assert(P.cf[0]==37);rt.has_cview[0]=1;rt.cview[0].format=0x999;select_color(&color,&rt);assert(P.cf[0]==37);
 vtex decoded={.f={.f=37,.dec=3}};rt.cview[0].format=0x48;select_color(&decoded,&rt);assert(P.cf[0]==37);rt.cview[0].format=0x44;select_color(&decoded,&rt);assert(P.cf[0]==37);rt.cview[0].format=0x25;select_color(&decoded,&rt);assert(P.cf[0]==37);
 rt.dview.format=0x34;rt.depth=&t;select_depth(&depth,&rt);assert(P.df==126);P.df=126;P.dt->f.stencil=0;consume();assert(d.df==126&&k.df==126&&!d.stencil&&!k.stencil);
 puts("attachment formats: selected sRGB/depth views reach render pass and pipeline, absent views disabled, unknown/decoded fallback preserved");
}
'''
