
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
int
extSubtractSideOverlap(tile, dinfo, sov)
    Tile *tile;
    TileType dinfo;			/* (unused) */
    struct sideoverlap *sov;
{
    Rect r;
    int area, dnear, dfar, length;
    double mult, snear, sfar;
    TileType ta, tb;
    Boundary *bp = sov->so_esws->bp;

    TITORECT(tile, &r);
    GEOCLIP(&r, &sov->so_clip);
    area = (r.r_xtop - r.r_xbot) * (r.r_ytop - r.r_ybot);
    if (area <= 0) return 0;

    ta = TiGetType(bp->b_inside);
    tb = sov->so_ctype;

    if (bp->b_segment.r_xtop == bp->b_segment.r_xbot)
	length = r.r_ytop - r.r_ybot;
    else
	length = r.r_xtop - r.r_xbot;

    switch (bp->b_direction)
    {
	case BD_LEFT:	/* Tile tp is to the left of the boundary */
	    dnear = bp->b_segment.r_xbot - r.r_xtop;
	    dfar = bp->b_segment.r_xbot - r.r_xbot;
	    break;
	case BD_RIGHT:	/* Tile tp is to the right of the boundary */
	    dnear = r.r_xbot - bp->b_segment.r_xtop;
	    dfar = r.r_xtop - bp->b_segment.r_xtop;
	    break;
	case BD_BOTTOM:	/* Tile tp is below the boundary */
	    dnear = bp->b_segment.r_ybot - r.r_ytop;
	    dfar = bp->b_segment.r_ybot - r.r_ybot;
	    break;
	case BD_TOP:	/* Tile tp is above the boundary */
	    dnear = r.r_ybot - bp->b_segment.r_ytop;
	    dfar = r.r_ytop - bp->b_segment.r_ytop;
	    break;
    }

    if (dnear < 0) dnear = 0;	/* Don't count underlap */
    mult = ExtCurStyle->exts_overlapMult[ta][0];
    snear = 0.6366 * atan(mult * dnear);
    sfar = 0.6366 * atan(mult * dfar);

    /* "sfar - snear" is the fractional portion of the fringe cap	*/
    /* seen by the substrate in the direction perpendicular to the edge	*/
    /* generating the fringe cap.  This is multiplied by the fraction	*/
    /* of the total edge length to get the total fraction of the entire	*/
    /* fringe capacitance being shielded.				*/

    sov->so_subfrac += (sfar - snear) * ((double)length / (double)sov->so_length);

    /* Do the same calculation but the the overlap multiplier for the	*/
    /* coupling layer, since the fringe capacitance has a different	*/
    /* halo than for the substrate.					*/

    if (ExtCurStyle->exts_overlapMult[ta][tb] != mult)
    {
	mult = ExtCurStyle->exts_overlapMult[ta][tb];
	snear = 0.6366 * atan(mult * dnear);
	sfar = 0.6366 * atan(mult * dfar);
    }
    sov->so_coupfrac += (sfar - snear) * ((double)length / (double)sov->so_length);
    openpllFringeSupport("fringe_shield_leaf", NULL, NULL, bp, &r,
        sov->so_length, length, sov->so_esws->plane_of_boundary,
        sov->so_esws->plane_checked,
        (double)ExtCurStyle->exts_overlapMult[ta][tb],
        (double)ExtCurStyle->exts_overlapMult[ta][0],
        0.0, 0.0, sov->so_coupfrac, sov->so_subfrac, 0.0, IsSplit(tile));


    return (0);
}


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
