"""Isolate native shielding arithmetic with synthetic contact/residue tables.

This is a source-level regression probe, not a layout extraction or a qualified
Magic patch. The frozen native source and instrumented builds remain unchanged.
"""
import argparse,json,subprocess
from pathlib import Path
from runtime_common import save,sha

PREAMBLE=r'''
#include <math.h>
#include <stdio.h>
typedef int TileType;
typedef struct {int r_xbot,r_ybot,r_xtop,r_ytop;} Rect;
typedef struct {Rect r;int type;} Tile;
typedef struct {Tile *b_inside;Rect b_segment;int b_direction;} Boundary;
typedef struct {Boundary *bp;int plane_of_boundary,plane_checked;} Edge;
struct sideoverlap {Rect so_clip;Edge *so_esws;int so_ctype,so_length;double so_coupfrac,so_subfrac;};
struct Style {double exts_overlapMult[32][32];};
static struct Style style,*ExtCurStyle=&style;
enum {BD_LEFT,BD_RIGHT,BD_BOTTOM,BD_TOP};
#define TITORECT(t,rp) (*(rp)=(t)->r)
#define TiGetType(t) ((t)->type)
#define GEOCLIP(rp,cp) do { \
 if((rp)->r_xbot<(cp)->r_xbot)(rp)->r_xbot=(cp)->r_xbot; \
 if((rp)->r_ybot<(cp)->r_ybot)(rp)->r_ybot=(cp)->r_ybot; \
 if((rp)->r_xtop>(cp)->r_xtop)(rp)->r_xtop=(cp)->r_xtop; \
 if((rp)->r_ytop>(cp)->r_ytop)(rp)->r_ytop=(cp)->r_ytop; } while(0)
#define DBIsContact(t) ((t)==20)
static int DBPlaneToResidue(int type,int plane) {return type==20?(plane==7?3:4):type;}
#define openpllFringeSupport(...) ((void)0)
'''

MAIN=r'''
int main(void) {
 int direction,contact,unequal;
 for(direction=0;direction<4;direction++)for(contact=0;contact<2;contact++)for(unequal=0;unequal<2;unequal++) {
  style=(struct Style){0};
  style.exts_overlapMult[3][0]=.125;
  style.exts_overlapMult[3][1]=unequal?.25:.125;
  // Contact table intentionally differs from its residue table.
  style.exts_overlapMult[20][0]=.5;
  style.exts_overlapMult[20][1]=unequal?.75:.5;
  Tile source={.type=contact?20:3};
  Boundary boundary={.b_inside=&source,.b_direction=direction};
  Tile shield;
  if(direction==BD_LEFT) {boundary.b_segment=(Rect){0,0,0,20};shield.r=(Rect){-4,2,-2,12};}
  if(direction==BD_RIGHT){boundary.b_segment=(Rect){0,0,0,20};shield.r=(Rect){2,2,4,12};}
  if(direction==BD_BOTTOM){boundary.b_segment=(Rect){0,0,20,0};shield.r=(Rect){2,-4,12,-2};}
  if(direction==BD_TOP){boundary.b_segment=(Rect){0,0,20,0};shield.r=(Rect){2,2,12,4};}
  Edge edge={.bp=&boundary,.plane_of_boundary=7,.plane_checked=9};
  struct sideoverlap sov={.so_clip=shield.r,.so_esws=&edge,.so_ctype=1,.so_length=20};
  extSubtractSideOverlap(&shield,0,&sov);
  double mc=style.exts_overlapMult[3][1],ms=style.exts_overlapMult[3][0];
  double ec=.6366*(atan(mc*4)-atan(mc*2))*.5;
  double es=.6366*(atan(ms*4)-atan(ms*2))*.5;
  int agrees=fabs(sov.so_coupfrac-ec)<1e-14 && fabs(sov.so_subfrac-es)<1e-14;
  printf("{\"direction\":%d,\"contact\":%s,\"unequal_substrate_and_coupling\":%s,\"matches_normalized_begin_kernel\":%s,\"actual_coupling\":%.17g,\"expected_coupling\":%.17g,\"actual_substrate\":%.17g,\"expected_substrate\":%.17g}\n",direction,contact?"true":"false",unequal?"true":"false",agrees?"true":"false",sov.so_coupfrac,ec,sov.so_subfrac,es);
 }
 return 0;
}
'''

def run(source,output):
    output.mkdir(exist_ok=False)
    text=source.read_text()
    start=text.index('int\nextSubtractSideOverlap(tile, dinfo, sov)')
    end=text.index('/* Recursive shielding side overlap check.',start)
    native=text[start:end]
    needle='    ta = TiGetType(bp->b_inside);'
    if native.count(needle)!=1:raise ValueError('unique native type lookup required')
    candidate=native.replace(needle,needle+'\n    if (DBIsContact(ta))\n        ta = DBPlaneToResidue(ta, sov->so_esws->plane_of_boundary);')
    results={};artifacts={}
    for name,body in [('native',native),('candidate',candidate)]:
        code=output/(name+'.c');binary=output/name;log=output/(name+'.jsonl')
        code.write_text(PREAMBLE+body+MAIN)
        subprocess.run(['gcc','-std=gnu99','-O2',str(code),'-lm','-o',str(binary)],check=True,timeout=30)
        run=subprocess.run([str(binary.resolve())],capture_output=True,text=True,check=True,timeout=5)
        log.write_text(run.stdout)
        rows=[json.loads(line) for line in run.stdout.splitlines()]
        if len(rows)!=16:raise ValueError('all direction/type/kernel controls required')
        for row in rows:
            expected=(name=='candidate' or not row['contact'])
            if row['matches_normalized_begin_kernel']!=expected:raise ValueError('unexpected native/candidate behavior')
        results[name]=dict(cases=len(rows),matching=sum(r['matches_normalized_begin_kernel'] for r in rows))
        artifacts.update({str(p.resolve()):sha(p) for p in [code,binary,log]})
    save(output/'assessment.json',dict(input_sha256={str(source.resolve()):sha(source),str(Path(__file__).resolve()):sha(Path(__file__).resolve())},
         artifacts=artifacts,results=results,synthetic_contact_tables=True,exact_native_function_extracted=True,
         trace_hook_suppressed_only=True,full_layout_failure_explained=False,native_layout_control_completed=False,
         extractor_fix_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.source,args.output)
