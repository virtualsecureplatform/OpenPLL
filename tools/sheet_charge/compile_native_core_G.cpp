#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <filesystem>
#include <unordered_map>
#include <iostream>
#include <omp.h>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==2,"usage: compile_native_core_G CONFIG");auto cfg=Json::read(argv[1]);auto path=cfg.at("branches").str();uint64_t bytes=std::filesystem::file_size(path),nodes=cfg.at("voltage_nodes").integer();I threads=cfg.at("threads").integer(),limit=cfg.at("max_accumulator_entries").integer();require(nodes>1&&nodes<100000000&&threads>0&&threads<=16&&limit>=16&&limit<=1000000,"bounded native G resources");double deadline=cfg.at("deadline_uptime").num();auto out=std::filesystem::path(cfg.at("output").str());require(std::filesystem::create_directory(out),"fresh native G run directory");std::vector<std::exception_ptr> errors(threads);std::vector<I> positive(threads),zero(threads),runs(threads);
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{
  std::ifstream input(path,std::ios::binary);require(bool(input),"native G branch input");uint64_t begin=bytes*part/threads,end=bytes*(part+1)/threads;std::string line;input.seekg(begin?begin-1:0);if(begin){char c;input.get(c);if(c!='\n')std::getline(input,line);}std::unordered_map<uint64_t,sparse::Value> acc;acc.reserve(limit);
  auto flush=[&](){if(acc.empty())return;std::vector<sparse::Record> records;records.reserve(acc.size());for(auto&[key,v]:acc)records.push_back({key,v.signed_sum.value(),v.absolute_sum.value(),v.terms});std::sort(records.begin(),records.end(),[](auto&a,auto&b){return a.key<b.key;});sparse::write((out/("part_"+std::to_string(part)+"_run_"+std::to_string(runs[part]++)+".bin")).string(),records);acc.clear();};
  while(input&&uint64_t(input.tellg())<end&&std::getline(input,line)){if((positive[part]+zero[part])%10000==0)require(now()<deadline,"native core G deadline");auto row=Json::parse(line);I a=row.at("global_voltage_ids").at(0).integer(),b=row.at("global_voltage_ids").at(1).integer();require(a>0&&b>0&&uint64_t(a)<nodes&&uint64_t(b)<nodes&&a!=b,"explicit native G endpoints");uint32_t bits=row.at("native_resistance_float_bits").integer();float rho=std::bit_cast<float>(bits);require(std::isfinite(rho)&&rho>=0&&std::bit_cast<uint32_t>(std::stof(row.at("native_resistance_milliohm_token").str()))==bits,"exact native float resistance identity");
   if(rho==0){require(row.at("branch_kind").str()=="exact_zero_voltage_constraint","native zero constraint type");zero[part]++;continue;}
   require(row.at("branch_kind").str()=="positive_native_resistor","positive native R type");long double g=1000.L/static_cast<long double>(rho);require(std::isfinite(g)&&g>0,"positive finite native conductance");if(a>b)std::swap(a,b);acc[(uint64_t(a)<<32)|uint64_t(a)].add(g);acc[(uint64_t(b)<<32)|uint64_t(b)].add(g);acc[(uint64_t(a)<<32)|uint64_t(b)].add(-g);positive[part]++;if(I(acc.size())>=limit)flush();
  }require(!input.bad(),"native G branch shard read");flush();
 }catch(...){errors[part]=std::current_exception();}}
 for(auto&e:errors)if(e)std::rethrow_exception(e);I np=0,nz=0,nr=0;for(I p=0;p<threads;p++){np+=positive[p];nz+=zero[p];nr+=runs[p];}require(np==cfg.at("expected_positive").integer()&&nz==cfg.at("expected_zero").integer(),"complete native R core coverage");Json report=Json::object();report["positive_native_resistors"]=np;report["exact_zero_branches_not_approximated"]=nz;report["source_upper_contributions"]=3*np;report["sparse_runs"]=nr;report["threads"]=threads;report["nominal_conductance_units"]="siemens from original native float32 milliohms";report["native_resistors_rewritten"]=false;report["physical_RC_qualified"]=false;report["release_qualified"]=false;std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
