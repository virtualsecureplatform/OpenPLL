#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <array>
#include <queue>
#include <iostream>
#include <time.h>
using Real=long double;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Stats{uint64_t entries=0,different=0,outside=0;sparse::Sum signed_delta,absolute_delta;Real maximum=0;};
struct Difference{uint64_t key;Real left,right,delta;bool operator<(const Difference& b)const{return delta>b.delta;}};
int main(int argc,char**argv){try{
 require(argc==2,"usage: compare_sparse_matrices CONFIG");auto cfg=Json::read(argv[1]);sparse::Reader left(cfg.at("left").str()),right(cfg.at("right").str());Real absolute=cfg.at("absolute_tolerance").num(),relative=cfg.at("relative_tolerance").num();require(absolute>0&&relative>=0,"positive absolute and nonnegative relative tolerances");uint64_t nets=uint64_t(cfg.at("node_count").integer());require(nets>0&&nets<=UINT32_MAX,"matrix node count");double deadline=cfg.at("deadline_uptime").num();
 sparse::Record a,b;bool have_a=left.next(a),have_b=right.next(b);std::array<Stats,3> stats;uint64_t count=0,outside=0;Real maximum=0,maximum_ratio=0,left_norm=0,right_norm=0;std::priority_queue<Difference> largest;
 while(have_a||have_b){if(count%10000==0)require(now()<deadline,"matrix comparison deadline");uint64_t key=!have_b||(have_a&&a.key<b.key)?a.key:b.key;Real x=0,y=0;if(have_a&&a.key==key){x=a.value;have_a=left.next(a);}if(have_b&&b.key==key){y=b.value;have_b=right.next(b);}uint64_t i=key>>32,j=key&UINT32_MAX;require(i<=j&&j<nets,"matrix comparison index bounds");Real delta=y-x,error=std::fabs(delta),bound=absolute+relative*std::max(std::fabs(x),std::fabs(y));int kind=i==j?0:i==0?1:2;auto& s=stats[kind];s.entries++;s.different+=error!=0;s.outside+=error>bound;s.signed_delta.add(delta);s.absolute_delta.add(error);s.maximum=std::max(s.maximum,error);
  count++;outside+=error>bound;maximum=std::max(maximum,error);maximum_ratio=std::max(maximum_ratio,error/bound);left_norm=std::max(left_norm,std::fabs(x));right_norm=std::max(right_norm,std::fabs(y));
  if(error>0&&(largest.size()<32||error>largest.top().delta)){largest.push({key,x,y,error});if(largest.size()>32)largest.pop();}
 }
 Json result=Json::object(),categories=Json::object(),top=Json::array();const std::array<const char*,3> names{"diagonal","reference_edge","conductor_coupling"};
 for(int k=0;k<3;k++){auto&s=stats[k];Json r=Json::object();r["entries"]=static_cast<long long>(s.entries);r["different_entries"]=static_cast<long long>(s.different);r["outside_tolerance_entries"]=static_cast<long long>(s.outside);r["signed_delta_sum"]=double(s.signed_delta.value());r["absolute_delta_sum"]=double(s.absolute_delta.value());r["maximum_absolute_delta"]=double(s.maximum);categories[names[k]]=r;}
 std::vector<Difference> differences;while(!largest.empty()){differences.push_back(largest.top());largest.pop();}std::reverse(differences.begin(),differences.end());for(auto d:differences)top.push(Json::Array{static_cast<long long>(d.key>>32),static_cast<long long>(d.key&UINT32_MAX),double(d.left),double(d.right),double(d.delta)});
 result["union_upper_entries"]=static_cast<long long>(count);result["outside_tolerance_entries"]=static_cast<long long>(outside);result["maximum_absolute_delta"]=double(maximum);result["maximum_error_over_tolerance"]=double(maximum_ratio);result["left_maximum_absolute_entry"]=double(left_norm);result["right_maximum_absolute_entry"]=double(right_norm);result["categories"]=categories;result["largest_differences"]=top;result["within_tolerance"]=outside==0;result["physical_RC_qualified"]=false;result["release_qualified"]=false;
 std::ofstream out(cfg.at("report").str());out<<result.dump()<<'\n';out.close();require(bool(out),"matrix comparison report close");std::cout<<result.dump()<<'\n';if(cfg.at("require_match").boolean())require(outside==0,"sparse matrices differ beyond the declared tolerances");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
