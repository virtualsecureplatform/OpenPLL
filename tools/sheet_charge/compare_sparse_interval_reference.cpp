// Full comparison against an immutable scalar matrix plus two exact reference intervals.
#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <gmpxx.h>
#include <array>
#include <iostream>
#include <set>
#include <time.h>
using I=long long;using Q=mpq_class;using Real=long double;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static Q dyadic(const mpz_class&n,int exponent){Q q(n);if(exponent>=0)mpq_mul_2exp(q.get_mpq_t(),q.get_mpq_t(),exponent);else mpq_div_2exp(q.get_mpq_t(),q.get_mpq_t(),-exponent);return q;}
static Q exact(Real value){char b[10];std::memcpy(b,&value,10);uint16_t e;std::memcpy(&e,b+8,2);uint64_t sig=sparse::load(b);mpz_class n;mpz_import(n.get_mpz_t(),1,-1,sizeof(sig),0,0,&sig);if(e&0x8000)n=-n;return dyadic(n,((e&0x7fff)?int(e&0x7fff)-16383:1-16383)-63);}
static Q endpoint(const Json&v){require(v.arr().size()==2,"interval endpoint width");I exponent=v.at(1).integer();require(exponent>=-100000&&exponent<=100000,"bounded interval exponent");return dyadic(mpz_class(v.at(0).str()),int(exponent));}
struct Reference{Q lo,hi;};
struct Stats{uint64_t entries=0,outside=0;};
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();
 Real absolute=cfg.at("absolute_tolerance").num(),relative=cfg.at("relative_tolerance").num();require(absolute>0&&relative>=0,"comparison tolerances");
 Q qa(cfg.at("absolute_tolerance").num()),qr(cfg.at("relative_tolerance").num());
 uint64_t nodes=cfg.at("node_count").integer();require(nodes>1&&nodes<=UINT32_MAX,"comparison voltage namespace");
 auto scalar=Json::read(cfg.at("interval_reference_report").str());std::map<uint64_t,Reference>overrides;
 for(auto[key,name]:{std::pair<uint64_t,const char*>{0,"diagonal_0_interval"},{1,"edge_0_1_interval"}}){
  const auto&row=scalar.at(name);Reference r{endpoint(row.at("lower_dyadic")),endpoint(row.at("upper_dyadic"))};require(r.lo<=r.hi,"ordered reference interval");overrides.emplace(key,r);
 }
 sparse::Reader left(cfg.at("left").str()),right(cfg.at("right").str());sparse::Record a,b;bool have_a=left.next(a),have_b=right.next(b);
 uint64_t count=0,outside=0,fallbacks=0;std::array<Stats,3>stats;std::set<uint64_t>seen;bool narrow=true;Json overridden=Json::array();
 while(have_a||have_b){
  if(count%10000==0)require(now()<deadline,"full interval comparison deadline");uint64_t key=!have_b||(have_a&&a.key<b.key)?a.key:b.key;Real x=0,y=0;
  if(have_a&&a.key==key){x=a.value;have_a=left.next(a);}if(have_b&&b.key==key){y=b.value;have_b=right.next(b);}
  uint64_t i=key>>32,j=key&UINT32_MAX;require(i<=j&&j<nodes,"full comparison matrix bounds");bool pass=false;
  auto replacement=overrides.find(key);
  if(replacement!=overrides.end()){
   seen.insert(key);const auto&r=replacement->second;Q actual=exact(y),dl=abs(actual-r.lo),dh=abs(actual-r.hi),error=dl>dh?dl:dh;
   Q magnitude=(r.lo<=0&&r.hi>=0)?Q(0):std::min(Q(abs(r.lo)),Q(abs(r.hi)));
   Q actual_magnitude=abs(actual),bound=qa+qr*(actual_magnitude>magnitude?actual_magnitude:magnitude);
   pass=error<=bound;bool small=r.hi-r.lo<=bound/8;narrow&=small;
   Json row=Json::object();row["row"]=I(i);row["column"]=I(j);row["reference_lower_exact"]=r.lo.get_str();row["reference_upper_exact"]=r.hi.get_str();
   row["projected_coefficient_exact"]=actual.get_str();row["maximum_error_exact"]=error.get_str();row["minimum_tolerance_exact"]=bound.get_str();
   row["whole_interval_within_tolerance"]=pass;row["interval_width_within_one_eighth_tolerance"]=small;overridden.push(row);
  }else{
   // Adjacent representable values enclose each rounded operation. Only borderline
   // comparisons need GMP; the ordinary path still proves the exact criterion.
   Real error=std::fabs(y-x),magnitude=std::max(std::fabs(x),std::fabs(y)),product=relative*magnitude;
   require(std::isfinite(error)&&std::isfinite(product),"finite comparison arithmetic");
   Real error_low=std::max(Real(0),std::nextafterl(error,-INFINITY)),error_high=std::nextafterl(error,INFINITY);
   Real bound_low=std::nextafterl(absolute+std::nextafterl(product,-INFINITY),-INFINITY);
   Real bound_high=std::nextafterl(absolute+std::nextafterl(product,INFINITY),INFINITY);
   if(error_high<=bound_low)pass=true;
   else if(error_low>bound_high)pass=false;
   else{fallbacks++;Q qx=exact(x),qy=exact(y);Q delta=abs(qy-qx),mx=abs(qx),my=abs(qy);pass=delta<=qa+qr*(mx>my?mx:my);}
  }
  int kind=i==j?0:i==0?1:2;stats[kind].entries++;stats[kind].outside+=!pass;outside+=!pass;count++;
 }
 require(seen.size()==2,"both explicit reference entries must remain in the compared namespace");
 Json report=Json::object(),categories=Json::object();std::array<const char*,3>names{"diagonal","reference_edge","conductor_coupling"};
 for(int k=0;k<3;k++){Json row=Json::object();row["entries"]=I(stats[k].entries);row["outside_tolerance_entries"]=I(stats[k].outside);categories[names[k]]=row;}
 report["union_upper_entries"]=I(count);report["outside_tolerance_entries"]=I(outside);report["categories"]=categories;report["reference_overrides"]=overridden;
 report["exact_GMP_boundary_fallbacks"]=I(fallbacks);report["all_stored_entry_comparisons_certified"]=true;
 report["all_reference_intervals_narrow_enough"]=narrow;report["within_tolerance"]=outside==0&&narrow;
 report["reference_zero_retained"]=true;report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream out(cfg.at("report").str());out<<report.dump()<<'\n';out.close();require(bool(out),"full interval comparison report close");
 if(cfg.at("require_match").boolean())require(outside==0&&narrow,"full interval reference comparison nonpass");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
