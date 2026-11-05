// P^T C P for the independently audited voltage-to-original-conductor map.
#include "../charge_compiler/json.hpp"
#include "sparse_run_slice.hpp"
#include "conductor_map.hpp"
#include <unordered_map>
#include <iostream>
#include <omp.h>
#include <time.h>
namespace fs=std::filesystem;using I=long long;using Acc=std::unordered_map<uint64_t,sparse::Value>;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static void flush(Acc& values,const fs::path& out,I part,I run){std::vector<sparse::Record> rows;rows.reserve(values.size());for(auto&[key,value]:values)rows.push_back({key,value.signed_sum.value(),value.absolute_sum.value(),value.terms});std::sort(rows.begin(),rows.end(),[](auto a,auto b){return a.key<b.key;});sparse::write((out/("part_"+std::to_string(part)+"_run_"+std::to_string(run)+".bin")).string(),rows);values.clear();}
int main(int argc,char**argv){try{
 require(argc==2,"usage: collapse_spatial_matrix CONFIG");auto cfg=Json::read(argv[1]);auto path=cfg.at("matrix").str();sparse::SliceReader header(path,0,0);uint64_t total=header.total;
 ConductorMap nets(cfg.at("voltage_map").str(),"CNETDOF1");I threads=cfg.at("threads").integer(),limit=cfg.at("max_accumulator_entries").integer();require(threads>0&&threads<=16&&limit>=16&&limit<=4000000,"bounded spatial collapse resources");double deadline=cfg.at("deadline_uptime").num();
 fs::path out=cfg.at("output").str();require(fs::create_directory(out),"fresh spatial collapse output");std::vector<std::exception_ptr> errors(threads);std::vector<uint64_t> counts(threads),first(threads),last(threads),terms(threads),doubled(threads);std::vector<I> runs(threads);
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{sparse::SliceReader input(path,total*part/threads,total*(part+1)/threads);sparse::Record row;Acc values;values.reserve(size_t(limit));
  while(input.next(row)){require(now()<deadline,"spatial collapse deadline");uint64_t i=row.key>>32,j=row.key&UINT32_MAX;uint32_t a=nets.at(i),b=nets.at(j);if(a>b)std::swap(a,b);long double factor=(a==b&&i!=j)?2.L:1.L;
   values[(uint64_t(a)<<32)|b].merge(row.value*factor,row.absolute*factor,row.terms);if(!counts[part])first[part]=row.key;last[part]=row.key;counts[part]++;doubled[part]+=factor==2;require(terms[part]<=UINT64_MAX-row.terms,"collapse source term overflow");terms[part]+=row.terms;
   if(I(values.size())>=limit)flush(values,out,part,runs[part]++);
  }if(!values.empty())flush(values,out,part,runs[part]++);
 }catch(...){errors[part]=std::current_exception();}}
 for(auto& error:errors)if(error)std::rethrow_exception(error);uint64_t n=0,nt=0,nd=0,prior=0;I nr=0;bool have=false;
 for(I part=0;part<threads;part++){if(counts[part]){require(!have||prior<first[part],"global sorted slice boundaries");prior=last[part];have=true;}n+=counts[part];require(nt<=UINT64_MAX-terms[part],"global term count overflow");nt+=terms[part];nd+=doubled[part];nr+=runs[part];}require(n==total,"complete spatial matrix entry coverage");
 Json report=Json::object();report["source_upper_entries"]=I(total);report["source_terms"]=I(nt);report["symmetry_doubled_entries"]=I(nd);report["sparse_runs"]=nr;report["conductor_nets"]=I(nets.net_count());report["threads"]=threads;report["physical_RC_qualified"]=false;report["release_qualified"]=false;std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
