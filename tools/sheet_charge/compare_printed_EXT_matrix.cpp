#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <iostream>
#include <time.h>
using Real=long double;using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==2,"usage: compare_printed_EXT_matrix CONFIG");auto cfg=Json::read(argv[1]);sparse::Reader actual(cfg.at("actual").str()),printed(cfg.at("printed").str()),bounds(cfg.at("serialization_bounds").str());
 Real atol=cfg.at("absolute_tolerance").num(),rtol=cfg.at("relative_tolerance").num();require(atol>=0&&atol<=1e-8L&&rtol>=0&&rtol<=2e-12L,"bounded matrix numerical tolerance");uint64_t nodes=cfg.at("node_count").integer();double deadline=cfg.at("deadline_uptime").num();
 sparse::Record a,p,e;bool ha=actual.next(a),hp=printed.next(p),he=bounds.next(e);uint64_t entries=0,bad=0,only_actual=0,only_printed=0;Real maximum=0,maximum_excess=0;Json examples=Json::array();
 while(ha||hp||he){if(entries%10000==0)require(now()<deadline,"printed EXT comparison deadline");require(hp==he&&(!hp||p.key==e.key),"printed coefficient/error key coverage");uint64_t key=ha?a.key:p.key;if(hp)key=std::min(key,p.key);require((key&UINT32_MAX)<nodes,"printed comparison node bound");bool aa=ha&&a.key==key,pp=hp&&p.key==key;Real av=aa?a.value:0,pv=pp?p.value:0,eb=pp?e.value:0;require(eb>=0,"nonnegative serialization bound");Real delta=std::fabs(av-pv),round=256*std::numeric_limits<Real>::epsilon()*((aa?a.absolute:0)+(pp?p.absolute:0));Real tolerance=eb+atol+rtol*std::max(std::fabs(av),std::fabs(pv))+round;
  maximum=std::max(maximum,delta);maximum_excess=std::max(maximum_excess,delta-tolerance);if(delta>tolerance){bad++;if(examples.arr().size()<32)examples.push(Json::Array{I(key>>32),I(key&UINT32_MAX),double(av),double(pv),double(eb),double(delta),double(tolerance)});}only_actual+=aa&&!pp;only_printed+=pp&&!aa;entries++;if(aa)ha=actual.next(a);if(pp){hp=printed.next(p);he=bounds.next(e);}
 }
 Json report=Json::object();report["union_upper_entries"]=I(entries);report["outside_serialization_and_numerical_bounds"]=I(bad);report["within_bounds"]=bad==0;report["maximum_absolute_delta"]=double(maximum);report["maximum_excess_over_bounds"]=double(maximum_excess);report["only_actual_entries"]=I(only_actual);report["only_printed_entries"]=I(only_printed);report["examples"]=examples;report["physical_RC_qualified"]=false;report["release_qualified"]=false;std::ofstream out(cfg.at("report").str());out<<report.dump()<<'\n';out.close();require(bool(out),"printed comparison report close");std::cout<<report.dump()<<'\n';require(!cfg.at("require_match").boolean()||bad==0,"native printed matrix comparison differs");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
