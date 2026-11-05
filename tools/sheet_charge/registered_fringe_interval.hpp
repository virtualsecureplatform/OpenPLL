#pragma once
// Reuse audited exact geometry; replace fringe quadrature with analytic intervals.
#define main rational_control_main
#include "main_registered_rational.cpp"
#undef main
#include "fringe_interval.hpp"
using Polynomial=std::array<Q,4>;
using IntervalMatrix=std::map<std::pair<int,int>,fringe_interval::Interval>;
static Polynomial multiply(const Polynomial&a,const Polynomial&b){
 Polynomial out{};for(int i=0;i<4;i++)for(int j=0;j<4;j++)if(a[i]!=0&&b[j]!=0){require(i+j<4,"cubic fringe polynomial bound");out[i+j]+=a[i]*b[j];}return out;
}
static Polynomial subtract(Polynomial a,const Polynomial&b){for(int k=0;k<4;k++)a[k]-=b[k];return a;}
static Polynomial tangent_product(const std::array<Q,3>&x,const std::array<Q,3>&y,const Slice&s){
 Polynomial ax{x[0],x[1],0,0},ay{y[0],y[1],0,0};
 Polynomial lower{s.lower.c,s.lower.s,0,0},upper{s.upper.c,s.upper.s,0,0};
 auto width=subtract(upper,lower),lower2=multiply(lower,lower),upper2=multiply(upper,upper);
 auto first=multiply(multiply(ax,ay),width);
 auto second=multiply(Polynomial{x[0]*y[2]+y[0]*x[2],x[1]*y[2]+y[1]*x[2],0,0},subtract(upper2,lower2));
 auto third=subtract(multiply(upper2,upper),multiply(lower2,lower));
 for(int k=0;k<4;k++)first[k]+=second[k]/2+x[2]*y[2]*third[k]/3;return first;
}
static IntervalMatrix fringe_certified(const Basis&source,const Basis&target,Edge e,std::array<Q,4>rect,
                                      int direction,Q density,Q multiplier){
 require(direction==1||direction==2||direction==4||direction==8,"fringe direction");
 int normal=(direction==1||direction==4)?0:1,along=1-normal,sign=(direction==1||direction==8)?-1:1;
 Q origin=coord(e.origin,normal),span=coord(e.delta,along);
 require(coord(e.delta,normal)==0&&span>0&&multiplier>=0,"fringe edge/multiplier");
 if(sign>0){if(rect[normal]<origin)rect[normal]=origin;}else if(rect[normal+2]>origin)rect[normal+2]=origin;
 rectangle(rect);IntervalMatrix matrix;if(rect[0]==rect[2]||rect[1]==rect[3])return matrix;
 auto parts=line_parts(source,e);std::set<Q>cuts{0,1};for(const auto&p:parts){cuts.insert(p.lo);cuts.insert(p.hi);}Q covered=0;
 const Q factor=density*Q(double(.6366)); // Preserve the original binary64 technology constant.
 for(auto it=cuts.begin(),next=std::next(it);next!=cuts.end();++it,++next){
  Q lo=*it,hi=*next;auto strip=rect;Q low=coord(e.origin,along)+lo*span,high=coord(e.origin,along)+hi*span;
  if(strip[along]<low)strip[along]=low;if(strip[along+2]>high)strip[along+2]=high;if(strip[along]>=strip[along+2])continue;
  auto lv=restricted(parts,(lo+hi)/2);Vec sv;for(const auto&[n,v]:lv){Q slope=v[1]/span;sv[n][0]=v[0]-slope*coord(e.origin,along);sv[n][along+1]=slope;}
  for(const auto&[polygon,tv]:patches(target,rectangle(strip))){
   covered+=moments(polygon)[0];auto vector=difference(sv,tv);Aff unity{};
   for(const auto&[n,v]:vector)for(int k=0;k<3;k++)unity[k]+=v[k];
   require(unity==Aff{},"exact affine partition of unity for every fringe patch");
   std::map<int,std::array<Q,3>> values;
   for(const auto&[n,v]:vector)values[n]={v[0]+v[normal+1]*origin,sign*v[normal+1],v[along+1]};
   for(const auto&s:slices(polygon,normal,origin,sign))for(const auto&[i,x]:values)for(const auto&[j,y]:values){
    if(i>j)continue;auto polynomial=tangent_product(x,y,s);for(auto&v:polynomial)v*=factor;
    auto integral=fringe_interval::integrate(polynomial,s.lo,s.hi,multiplier);
    auto key=std::pair{i,j};matrix[key]=matrix[key]+integral;
   }
  }
 }
 require(covered==(rect[2]-rect[0])*(rect[3]-rect[1]),"exact fringe support coverage");return matrix;
}
