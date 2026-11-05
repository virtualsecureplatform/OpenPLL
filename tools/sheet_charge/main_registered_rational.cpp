// Exact GMP geometry/P1 uniform moments; positive-panel fringe quadrature.
// A control candidate, not a qualified full-layout physical RC model.
#include "../charge_compiler/json.hpp"
#include <gmpxx.h>
#include <array>
#include <algorithm>
#include <iostream>
#include <set>
#include <omp.h>
#include <atomic>
#include <exception>
#include <unordered_map>
#include <time.h>
using Q=mpq_class;using I=long long;using LD=long double;
static Q exact_coordinate(const Json& v){
 if(std::holds_alternative<Json::Array>(v.value)){
  require(v.arr().size()==2,"rational coordinate width");
  mpz_class n(v.at(0).str()),d(v.at(1).str());require(d>0,"positive coordinate denominator");
  Q result(n,d);result.canonicalize();return result;
 }return Q(v.num());
}
struct P{Q x,y;bool operator==(const P& b)const{return x==b.x&&y==b.y;}};
using Poly=std::vector<P>;using Aff=std::array<Q,3>;using Vec=std::map<int,Aff>;using Matrix=std::map<std::pair<int,int>,Q>;using FloatMatrix=std::map<std::pair<int,int>,LD>;
static Q q(long x){return Q(x);}static Q cross(P a,P b,P p){return (b.x-a.x)*(p.y-a.y)-(b.y-a.y)*(p.x-a.x);}
static Q coord(P p,int i){return i?p.y:p.x;}static LD ld(const Q& v){return std::strtold(v.get_num().get_str().c_str(),nullptr)/std::strtold(v.get_den().get_str().c_str(),nullptr);}
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static Poly clip(Poly result,const Poly& triangle){
 for(size_t e=0;e<triangle.size();++e){if(result.empty())break;P a=triangle[e],b=triangle[(e+1)%triangle.size()];Poly part;
  for(size_t i=0;i<result.size();++i){P p=result[i],r=result[(i+1)%result.size()];Q vp=cross(a,b,p),vr=cross(a,b,r);bool ip=vp>=0,ir=vr>=0;if(ip)part.push_back(p);if(ip!=ir){Q t=vp/(vp-vr);part.push_back({p.x+t*(r.x-p.x),p.y+t*(r.y-p.y)});}}
  result.clear();for(const P& p:part)if(result.empty()||!(p==result.back()))result.push_back(p);if(result.size()>1&&result.front()==result.back())result.pop_back();
 }return result;
}
static std::array<Q,6> moments(const Poly& polygon){std::array<Q,6> m{};for(size_t k=1;k+1<polygon.size();++k){std::array<P,3> p{polygon[0],polygon[k],polygon[k+1]};Q area=cross(p[0],p[1],p[2])/2;require(area>=0,"negative polygon orientation");Q sx=0,sy=0,xx=0,yy=0,xy=0;for(auto v:p){sx+=v.x;sy+=v.y;xx+=v.x*v.x;yy+=v.y*v.y;xy+=v.x*v.y;}for(int i=0;i<3;++i)for(int j=i+1;j<3;++j){xx+=p[i].x*p[j].x;yy+=p[i].y*p[j].y;}m[0]+=area;m[1]+=area*sx/3;m[2]+=area*sy/3;m[3]+=area*xx/6;m[4]+=area*(sx*sy+xy)/12;m[5]+=area*yy/6;}return m;}
struct Patch{Poly triangle;Vec values;};struct Basis{int constant=-1;std::vector<Patch> patches;};
struct Nodes{std::map<std::string,int> ids;std::vector<std::string> names;int get(const std::string& s){auto [it,added]=ids.emplace(s,int(names.size()));if(added)names.push_back(s);return it->second;}};
static Basis basis(const Json& in,Nodes& nodes,P shift){Basis b;if(in.obj().count("constant")){b.constant=nodes.get(in.at("constant").str());return b;}std::vector<P> points;for(const auto& p:in.at("points").arr())points.push_back({exact_coordinate(p.at(0))-shift.x,exact_coordinate(p.at(1))-shift.y});bool named=in.obj().count("point_nodes");if(named)require(in.at("point_nodes").arr().size()==points.size(),"point/node identity count");auto prefix=in.obj().count("prefix")?in.at("prefix").str():std::string{};
 for(const auto& row:in.at("triangles").arr()){require(row.arr().size()==3,"triangle width");std::array<int,3> ids{};Poly pp;for(int i=0;i<3;++i){I n=row.at(i).integer();require(n>=0&&n<I(points.size()),"triangle node index");ids[i]=nodes.get(named?in.at("point_nodes").at(size_t(n)).str():prefix+std::to_string(n));pp.push_back(points[n]);}Q det=cross(pp[0],pp[1],pp[2]);require(det>0,"positive basis orientation");Vec v;for(int i=0;i<3;++i){P a=pp[(i+1)%3],c=pp[(i+2)%3];Aff coefficients{(a.x*c.y-c.x*a.y)/det,(a.y-c.y)/det,(c.x-a.x)/det};for(int j=0;j<3;++j)v[ids[i]][j]+=coefficients[j];}b.patches.push_back({pp,v});}require(!b.patches.empty(),"empty spatial basis");return b;
}
static Vec difference(const Vec& a,const Vec& b){Vec v=a;for(auto& [n,x]:b)for(int i=0;i<3;++i)v[n][i]-=x[i];for(auto it=v.begin();it!=v.end();)if(it->second==Aff{})it=v.erase(it);else ++it;return v;}
static std::vector<std::pair<Poly,Vec>> patches(const Basis& b,const Poly& polygon){if(b.constant>=0)return {{polygon,{{b.constant,{1,0,0}}}}};std::vector<std::pair<Poly,Vec>> out;for(auto& p:b.patches){auto r=clip(polygon,p.triangle);if(moments(r)[0]>0)out.push_back({r,p.values});}return out;}
static std::array<Q,4> box(const Json& in,P shift){require(in.arr().size()==4,"box width");return {exact_coordinate(in.at(0))-shift.x,exact_coordinate(in.at(1))-shift.y,exact_coordinate(in.at(2))-shift.x,exact_coordinate(in.at(3))-shift.y};}
static Poly rectangle(std::array<Q,4> b){require(b[0]<=b[2]&&b[1]<=b[3],"ordered support box");return {{b[0],b[1]},{b[2],b[1]},{b[2],b[3]},{b[0],b[3]}};}
static Matrix area(const Basis& source,const Basis& target,std::array<Q,4> rect,Q density){Matrix matrix;Q covered=0;for(auto& [polygon,sv]:patches(source,rectangle(rect)))for(auto& [part,tv]:patches(target,polygon)){auto m=moments(part);covered+=m[0];auto v=difference(sv,tv);for(auto& [a,x]:v)for(auto& [b,y]:v)matrix[{a,b}]+=density*(x[0]*y[0]*m[0]+(x[0]*y[1]+x[1]*y[0])*m[1]+(x[0]*y[2]+x[2]*y[0])*m[2]+x[1]*y[1]*m[3]+(x[1]*y[2]+x[2]*y[1])*m[4]+x[2]*y[2]*m[5]);}require(covered==(rect[2]-rect[0])*(rect[3]-rect[1]),"area outside or overlapping basis support");return matrix;}
struct Edge{P origin,delta;Q length;};static Edge edge(std::array<Q,4> a){require(a[0]<=a[2]&&a[1]<=a[3]&&(a[0]==a[2]||a[1]==a[3]),"axis-aligned ordered edge");return {{a[0],a[1]},{a[2]-a[0],a[3]-a[1]},a[2]-a[0]+a[3]-a[1]};}
struct LinePart{Q lo,hi;std::map<int,std::array<Q,2>> values;};
static std::vector<LinePart> line_parts(const Basis& b,const Edge& e){if(b.constant>=0)return {{0,1,{{b.constant,{1,0}}}}};std::vector<LinePart> result;
 for(auto& p:b.patches){Q lo=0,hi=1;for(size_t i=0;i<3;++i){P a=p.triangle[i],d=p.triangle[(i+1)%3];Q at=cross(a,d,e.origin),slope=(d.x-a.x)*e.delta.y-(d.y-a.y)*e.delta.x;if(slope>0){Q cut=-at/slope;if(cut>lo)lo=cut;}else if(slope<0){Q cut=-at/slope;if(cut<hi)hi=cut;}else if(at<0)hi=lo;}if(lo>=hi)continue;LinePart r{lo,hi,{}};for(auto& [n,v]:p.values){std::array<Q,2> vv{v[0]+v[1]*e.origin.x+v[2]*e.origin.y,v[1]*e.delta.x+v[2]*e.delta.y};if(vv!=std::array<Q,2>{})r.values[n]=vv;}result.push_back(r);}return result;
}
static std::map<int,std::array<Q,2>> restricted(const std::vector<LinePart>& parts,Q at){bool found=false;std::map<int,std::array<Q,2>> result;for(auto& p:parts)if(p.lo<at&&at<p.hi){if(found)require(result==p.values,"inconsistent shared-edge P1 basis");else{found=true;result=p.values;}}require(found,"line outside basis support");return result;}
static Matrix line(const Basis& source,const Basis& target,Edge a,Edge b,Q density){require(a.length==b.length,"unequal line lengths");Matrix matrix;if(a.length==0)return matrix;auto sp=line_parts(source,a),tp=line_parts(target,b);std::set<Q> cuts{0,1};for(auto* parts:{&sp,&tp})for(auto& p:*parts){cuts.insert(p.lo);cuts.insert(p.hi);}for(auto it=cuts.begin(),next=std::next(it);next!=cuts.end();++it,++next){Q lo=*it,hi=*next;auto sv=restricted(sp,(lo+hi)/2),tv=restricted(tp,(lo+hi)/2);std::map<int,std::array<Q,2>> v=sv;for(auto& [n,x]:tv)for(int i=0;i<2;++i)v[n][i]-=x[i];Q m0=hi-lo,m1=(hi*hi-lo*lo)/2,m2=(hi*hi*hi-lo*lo*lo)/3;for(auto& [i,x]:v)for(auto& [j,y]:v)matrix[{i,j}]+=density*a.length*(x[0]*y[0]*m0+(x[0]*y[1]+x[1]*y[0])*m1+x[1]*y[1]*m2);}return matrix;}
static constexpr LD GAUSS[4][2]={{.18343464249564980493947614L,.36268378337836198296515045L},{.52553240991632898581773905L,.31370664587788728733796220L},{.79666647741362673959155394L,.22238103445337447054435599L},{.96028985649753623168356087L,.10122853629037625915253135L}};
struct Bound{Q c,s;};struct Slice{Q lo,hi;Bound lower,upper;};
static std::vector<Slice> slices(const Poly& polygon,int normal,Q origin,int sign){Poly poly;std::set<Q> cuts;for(P p:polygon){Q d=sign*(coord(p,normal)-origin);poly.push_back({d,coord(p,1-normal)});cuts.insert(d);}std::vector<Slice> result;
 for(auto it=cuts.begin(),next=std::next(it);next!=cuts.end();++it,++next){Q lo=*it,hi=*next,mid=(lo+hi)/2;require(lo>=0,"negative fringe distance");std::vector<Bound> bounds;for(size_t i=0;i<poly.size();++i){P a=poly[i],b=poly[(i+1)%poly.size()];if(std::min(a.x,b.x)<mid&&mid<std::max(a.x,b.x)){Q slope=(b.y-a.y)/(b.x-a.x);bounds.push_back({a.y-slope*a.x,slope});}}require(bounds.size()==2,"convex fringe slice boundaries");if(bounds[0].c+bounds[0].s*mid>bounds[1].c+bounds[1].s*mid)std::swap(bounds[0],bounds[1]);result.push_back({lo,hi,bounds[0],bounds[1]});}return result;
}
static FloatMatrix fringe(const Basis& source,const Basis& target,Edge e,std::array<Q,4> rect,int direction,Q density,Q multiplier,LD panel_fraction){
 require(direction==1||direction==2||direction==4||direction==8,"fringe direction");int normal=(direction==1||direction==4)?0:1,along=1-normal,sign=(direction==1||direction==8)?-1:1;Q origin=coord(e.origin,normal),span=coord(e.delta,along);require(coord(e.delta,normal)==0&&span>0&&multiplier>=0,"fringe edge/multiplier");if(sign>0){if(rect[normal]<origin)rect[normal]=origin;}else if(rect[normal+2]>origin)rect[normal+2]=origin;rectangle(rect);FloatMatrix matrix;if(rect[0]==rect[2]||rect[1]==rect[3])return matrix;
 auto parts=line_parts(source,e);std::set<Q> cuts{0,1};for(auto& p:parts){cuts.insert(p.lo);cuts.insert(p.hi);}Q covered=0;LD m=ld(multiplier),factor=ld(density)*LD(double(.6366));
 for(auto it=cuts.begin(),next=std::next(it);next!=cuts.end();++it,++next){Q lo=*it,hi=*next;auto strip=rect;Q l=coord(e.origin,along)+lo*span,h=coord(e.origin,along)+hi*span;if(strip[along]<l)strip[along]=l;if(strip[along+2]>h)strip[along+2]=h;if(strip[along]>=strip[along+2])continue;auto lv=restricted(parts,(lo+hi)/2);Vec sv;for(auto& [n,v]:lv){Q gradient=v[1]/span;sv[n][0]=v[0]-gradient*coord(e.origin,along);sv[n][along+1]=gradient;}
  for(auto& [polygon,tv]:patches(target,rectangle(strip))){covered+=moments(polygon)[0];auto vector=difference(sv,tv);std::vector<std::pair<int,std::array<LD,3>>> values;for(auto& [n,v]:vector)values.push_back({n,{ld(Q(v[0]+v[normal+1]*origin)),ld(Q(sign*v[normal+1])),ld(v[along+1])}});
   for(auto& slice:slices(polygon,normal,origin,sign)){LD near=ld(slice.lo),far=ld(slice.hi),lower_c=ld(slice.lower.c),lower_s=ld(slice.lower.s),upper_c=ld(slice.upper.c),upper_s=ld(slice.upper.s);if(m==0)continue;
    while(near<far){LD hi2=std::min(far,near+panel_fraction*std::hypotl(1.L,m*near)/m);require(hi2>near,"fringe panel progress");LD middle=(near+hi2)/2,half=(hi2-near)/2;
     for(auto& nw:GAUSS)for(int ns:{-1,1}){LD d=middle+ns*half*nw[0],lower=lower_c+lower_s*d,upper=upper_c+upper_s*d,tangent_mid=(lower+upper)/2,tangent_half=(upper-lower)/2;require(tangent_half>=0,"fringe tangent orientation");LD weight=factor*half*nw[1]*m/(1+(m*d)*(m*d))*tangent_half;
      for(int ts:{-1,1}){LD u=tangent_mid+ts*tangent_half/std::sqrt(3.L);std::vector<std::pair<int,LD>> evaluated;for(auto& [n,v]:values)evaluated.push_back({n,v[0]+v[1]*d+v[2]*u});for(auto& [a,va]:evaluated)for(auto& [b,vb]:evaluated)matrix[{a,b}]+=weight*(va*vb);}
     }near=hi2;
    }
   }
  }
 }require(covered==(rect[2]-rect[0])*(rect[3]-rect[1]),"fringe outside or overlapping support");return matrix;
}

struct Cached {Matrix exact;FloatMatrix floating;size_t estimate=0;};
struct Cache {std::unordered_map<std::string,Cached> entries;size_t used=0;};
static thread_local Cache local_cache;
static std::atomic<I> cache_hits{0},cache_misses{0},cache_clears{0};
static void token(std::string& out,const std::string& value){out+=std::to_string(value.size());out+=':';out+=value;out+=';';}
static void number_key(std::string& out,const Q& value){token(out,value.get_str());}
static void basis_key(std::string& out,const Basis& b){
 token(out,std::to_string(b.constant));token(out,std::to_string(b.patches.size()));
 for(const auto& p:b.patches){token(out,std::to_string(p.triangle.size()));for(const auto& v:p.triangle){number_key(out,v.x);number_key(out,v.y);}token(out,std::to_string(p.values.size()));for(const auto& [node,v]:p.values){token(out,std::to_string(node));for(const auto& q:v)number_key(out,q);}}
}
static std::string cache_key(const Basis& a,const Basis& b,const Json& op,const std::array<Q,4>& first,P shift,LD panel){
 std::string key;key.reserve(4096);auto kind=op.at(0).str();token(key,kind);basis_key(key,a);basis_key(key,b);for(const auto& v:first)number_key(key,v);
 if(kind=="A")number_key(key,Q(op.at(5).num()));
 else{for(const auto& v:box(op.at(5),shift))number_key(key,v);if(kind=="L")number_key(key,Q(op.at(6).num()));else{token(key,std::to_string(op.at(6).integer()));number_key(key,Q(op.at(7).num()));number_key(key,Q(op.at(8).num()));number_key(key,Q(double(panel)));}}
 return key;
}
static size_t cache_estimate(const std::string& key,const Cached& value){
 size_t bytes=key.capacity()+512;
 for(const auto& [ij,q]:value.exact)bytes+=256+2*sizeof(mp_limb_t)*(mpz_size(mpq_numref(q.get_mpq_t()))+mpz_size(mpq_denref(q.get_mpq_t())));
 bytes+=value.floating.size()*256;return bytes;
}
int main(int argc,char** argv){try{
 require(argc==2,"usage: sheet_charge CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto cases=Json::read(cfg.at("cases").str());LD panel=cfg.obj().count("panel_fraction")?cfg.at("panel_fraction").num():.25L;require(panel>0&&panel<=.5L,"bounded normal panel fraction");bool emit_exact=cfg.obj().count("emit_exact")&&cfg.at("emit_exact").boolean();std::ofstream output(cfg.at("output").str());require(bool(output),"output open");I repeat=cfg.obj().count("repeat")?cfg.at("repeat").integer():1;require(repeat>=1&&repeat<=100000,"repeat bounds");double start=uptime();I integrated=0;
 I cache_limit=cfg.obj().count("cache_limit_bytes_per_thread")?cfg.at("cache_limit_bytes_per_thread").integer():16777216;require(cache_limit>=0&&cache_limit<=134217728,"cache estimate limit");
 I threads=cfg.obj().count("threads")?cfg.at("threads").integer():1;require(threads>=1&&threads<=32,"thread limit");omp_set_dynamic(0);omp_set_num_threads(int(threads));std::vector<Json> results(cases.arr().size());
 for(I rep=0;rep<repeat;++rep){std::vector<std::exception_ptr> errors(cases.arr().size());std::atomic<bool> cancelled{false};
  #pragma omp parallel for schedule(dynamic,1)
  for(I ci=0;ci<I(cases.arr().size());++ci){if(cancelled.load())continue;try{const auto& row=cases.at(size_t(ci));
  require(uptime()<deadline,"whole integration deadline");auto& op=row.at("operator");P shift{exact_coordinate(op.at(4).at(0)),exact_coordinate(op.at(4).at(1))};Nodes nodes;Basis source=basis(row.at("source_basis"),nodes,shift),target=basis(row.at("target_basis"),nodes,shift);auto a=box(op.at(4),shift);std::string kind=op.at(0).str();Json matrix=Json::array(),exact=Json::array();
  Cached computed;const Cached* value=nullptr;std::string key;
  if(cache_limit){key=cache_key(source,target,op,a,shift,panel);auto found=local_cache.entries.find(key);if(found!=local_cache.entries.end()){value=&found->second;++cache_hits;}}
  if(!value){++cache_misses;
   if(kind=="A"||kind=="L")computed.exact=kind=="A"?area(source,target,a,Q(op.at(5).num())):line(source,target,edge(a),edge(box(op.at(5),shift)),Q(op.at(6).num()));
   else{require(kind=="F","unsupported kernel");computed.floating=fringe(source,target,edge(a),box(op.at(5),shift),int(op.at(6).integer()),Q(op.at(7).num()),Q(op.at(8).num()),panel);}
   value=&computed;
   if(cache_limit){computed.estimate=cache_estimate(key,computed);if(computed.estimate<=size_t(cache_limit)){if(local_cache.used+computed.estimate>size_t(cache_limit)){local_cache.entries.clear();local_cache.used=0;++cache_clears;}local_cache.used+=computed.estimate;auto inserted=local_cache.entries.emplace(std::move(key),std::move(computed));require(inserted.second,"fresh canonical cache key");value=&inserted.first->second;}}
  }
  if(kind=="A"||kind=="L"){for(const auto& [ij,v]:value->exact)if(v!=0){matrix.push(Json::Array{ij.first,ij.second,v.get_d()});if(emit_exact)exact.push(Json::Array{ij.first,ij.second,v.get_num().get_str(),v.get_den().get_str()});}}
  else for(const auto& [ij,v]:value->floating)if(v!=0){require(std::isfinite(v),"nonfinite fringe coefficient");matrix.push(Json::Array{ij.first,ij.second,double(v)});}

  if(rep==0){Json result=Json::object(),names=Json::array();for(auto& s:nodes.names)names.push(s);result["id"]=row.at("id");result["nodes"]=names;result["matrix"]=matrix;if(emit_exact&&kind!="F")result["exact_matrix"]=exact;results[size_t(ci)]=result;}
 }catch(...){errors[size_t(ci)]=std::current_exception();cancelled.store(true);}}
  for(const auto& error:errors)if(error)std::rethrow_exception(error);
  integrated+=I(cases.arr().size());
 }
 for(const auto& r:results){output<<r.dump()<<'\n';require(bool(output),"matrix output");}
 output.close();require(bool(output),"output close");Json result=Json::object();result["integrated_cases"]=integrated;result["elapsed_s"]=uptime()-start;result["gmp_version"]=gmp_version;result["threads"]=threads;result["cache_hits"]=cache_hits.load();result["cache_misses"]=cache_misses.load();result["cache_clears"]=cache_clears.load();result["cache_estimate_limit_bytes_per_thread"]=cache_limit;result["exact_geometry"]=true;result["physical_domain_complete"]=false;result["release_qualified"]=false;std::cout<<result.dump()<<'\n';return 0;
}catch(const std::exception& e){std::cerr<<"sheet_charge: "<<e.what()<<'\n';return 1;}}
