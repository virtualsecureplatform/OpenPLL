#pragma once
#include "registered_fringe_interval.hpp"
namespace symbolic_fringe {
// Exact linear combinations of rational constants, atan(q), and log1p(q).
// Equal atoms cancel algebraically; no floating threshold or eigenvalue clipping.
struct Expression{
 Q rational=0;std::map<std::pair<char,Q>,Q>atoms;
 void atom(char kind,Q argument,Q coefficient){
  require(argument>=0&&(kind=='a'||kind=='l'),"symbolic fringe atom domain");
  if(argument==0||coefficient==0)return;auto key=std::pair{kind,argument};atoms[key]+=coefficient;
  if(atoms[key]==0)atoms.erase(key);
 }
 Expression&operator+=(const Expression&b){rational+=b.rational;for(const auto&[key,value]:b.atoms)atom(key.first,key.second,value);return *this;}
 bool zero()const{return rational==0&&atoms.empty();}
 Json json()const{Json row=Json::object(),terms=Json::array();row["rational"]=rational.get_str();
  for(const auto&[key,value]:atoms)terms.push(Json::Array{key.first=='a'?"atan":"log1p",key.second.get_str(),value.get_str()});row["atoms"]=terms;return row;}
};
inline Expression operator+(Expression a,const Expression&b){a+=b;return a;}
inline Expression operator*(const Expression&a,const Q&factor){Expression b;b.rational=a.rational*factor;for(const auto&[key,value]:a.atoms)b.atom(key.first,key.second,value*factor);return b;}
inline Expression primitive(const Polynomial&p,Q d,Q m){
 Expression result;result.rational=p[2]*d/m+p[3]*d*d/(2*m);
 result.atom('a',m*d,p[0]-p[2]/(m*m));result.atom('l',m*m*d*d,p[1]/(2*m)-p[3]/(2*m*m*m));return result;
}
inline Expression integrate(const Polynomial&p,Q lower,Q upper,Q multiplier){
 require(lower>=0&&upper>=lower&&multiplier>=0,"symbolic integral domain");
 if(multiplier==0||lower==upper)return {};
 return primitive(p,upper,multiplier)+primitive(p,lower,multiplier)*Q(-1);
}
inline fringe_interval::Interval evaluate(const Expression&e){
 fringe_interval::Interval result(e.rational);
 for(const auto&[key,value]:e.atoms){fringe_interval::Interval argument(key.second),coefficient(value);
  auto term=key.first=='a'?fringe_interval::atan(argument):fringe_interval::log1p(argument);result=result+coefficient*term;
 }return result;
}
}

using SymbolicMatrix=std::map<std::pair<int,int>,symbolic_fringe::Expression>;
static SymbolicMatrix fringe_symbolic(const Basis&source,const Basis&target,Edge e,std::array<Q,4>rect,
                                      int direction,Q density,Q multiplier){
 require(direction==1||direction==2||direction==4||direction==8,"fringe direction");
 int normal=(direction==1||direction==4)?0:1,along=1-normal,sign=(direction==1||direction==8)?-1:1;
 Q origin=coord(e.origin,normal),span=coord(e.delta,along);
 require(coord(e.delta,normal)==0&&span>0&&multiplier>=0,"fringe edge/multiplier");
 if(sign>0){if(rect[normal]<origin)rect[normal]=origin;}else if(rect[normal+2]>origin)rect[normal+2]=origin;
 rectangle(rect);SymbolicMatrix matrix;if(rect[0]==rect[2]||rect[1]==rect[3])return matrix;
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
    auto integral=symbolic_fringe::integrate(polynomial,s.lo,s.hi,multiplier);
    auto key=std::pair{i,j};matrix[key]=matrix[key]+integral;
   }
  }
 }
 require(covered==(rect[2]-rect[0])*(rect[3]-rect[1]),"exact fringe support coverage");return matrix;
}
