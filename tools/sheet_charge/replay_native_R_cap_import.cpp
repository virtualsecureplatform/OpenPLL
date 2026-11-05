#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <bit>
#include <cfloat>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <unordered_map>
#include <time.h>
#include "native_MagAtof.hpp"
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static std::string quoted(const std::string&s,size_t&p){auto a=s.find('"',p);require(a!=s.npos,"EXT quoted name");auto b=s.find('"',a+1);require(b!=s.npos,"EXT quoted end");p=b+1;return s.substr(a+1,b-a-1);}
struct Group{Json original;float imported=0;uint64_t terms=0;};
int main(int argc,char**argv){try{
 static_assert(sizeof(float)==4&&FLT_MANT_DIG==24&&FLT_RADIX==2&&FLT_EVAL_METHOD==0);require(std::fegetround()==FE_TONEAREST,"native import rounding mode");require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();std::vector<Group> groups;std::unordered_map<std::string,size_t> names;std::string line;
 std::ifstream input(cfg.at("groups").str());require(bool(input),"group inventory open");while(std::getline(input,line)){auto row=Json::parse(line);require(names.emplace(row.at("original_conductor").str(),groups.size()).second,"unique group names");groups.push_back({row,0,0});}require(input.eof()&&!groups.empty(),"complete group inventory");input.close();input.open(cfg.at("ext").str());require(bool(input),"native EXT open");uint64_t caps=0;
 while(std::getline(input,line)){if(caps%10000==0)require(now()<deadline,"ordered import replay deadline");if(!line.starts_with("cap "))continue;caps++;size_t pos=0;auto a=quoted(line,pos),b=quoted(line,pos);auto x=names.find(a),y=names.find(b);if(x==names.end()&&y==names.end())continue;std::istringstream tail(line.substr(pos));std::string token;require(bool(tail>>token),"C token");float cap=MagAtof(token.c_str());require(std::isfinite(cap),"finite native C token");if(x!=names.end()){auto&g=groups[x->second];g.imported+=cap;g.terms++;}if(y!=names.end()){auto&g=groups[y->second];g.imported+=cap;g.terms++;}}
 require(input.eof(),"complete ordered EXT replay");std::ofstream rows(cfg.at("group_output").str());sparse::Sum import_sum,error_sum,old_error_sum;long double max_absolute=0,max_relative=0;uint64_t within=0;
 for(auto&g:groups){long double imported=g.imported,exported=g.original.at("exported_R_node_C_sum_raw").num(),exact=g.original.at("incident_coupling_C_raw").num();long double difference=exported-imported,denom=std::max(std::fabs(exported),std::fabs(imported)),relative=denom?std::fabs(difference)/denom:0;import_sum.add(imported);error_sum.add(std::fabs(difference));old_error_sum.add(std::fabs(exported-exact));max_absolute=std::max(max_absolute,std::fabs(difference));max_relative=std::max(max_relative,relative);within+=relative<=1e-5L;Json r=g.original;r["native_float32_import_raw"]=double(imported);r["native_float32_import_bits"]=I(std::bit_cast<uint32_t>(g.imported));r["incident_coupling_token_additions"]=I(g.terms);r["exported_minus_native_float32_import_raw"]=double(difference);r["relative_native_float32_prediction_error_diagnostic"]=double(relative);rows<<r.dump()<<'\n';}rows.close();require(bool(rows),"group replay output close");
 Json report=Json::object();report["original_coupling_records_scanned"]=I(caps);report["selected_groups"]=I(groups.size());report["native_float32_import_sum_raw"]=double(import_sum.value());report["absolute_group_native_float32_prediction_error_sum_raw"]=double(error_sum.value());report["previous_absolute_group_exact_coupling_prediction_error_sum_raw"]=double(old_error_sum.value());report["maximum_group_native_float32_prediction_error_raw"]=double(max_absolute);report["maximum_group_relative_native_float32_prediction_error_diagnostic"]=double(max_relative);report["groups_with_relative_prediction_error_le_1e5_diagnostic"]=I(within);report["source_order_preserved"]=true;std::ofstream out(cfg.at("report").str());out<<report.dump()<<'\n';require(bool(out),"replay report write");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
