// Expand capacitor scalars into a conductor-level symmetric C matrix.
#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include "conductor_map.hpp"
#include <unordered_map>
#include <filesystem>
#include <iostream>
#include <omp.h>
#include <time.h>
namespace fs=std::filesystem;using I=long long;using Acc=std::unordered_map<uint64_t,sparse::Value>;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static void flush(Acc& values,const fs::path& out,const std::string& kind,I part,I run){std::vector<sparse::Record> rows;rows.reserve(values.size());for(auto&[key,value]:values)rows.push_back({key,value.signed_sum.value(),value.absolute_sum.value(),value.terms});std::sort(rows.begin(),rows.end(),[](auto a,auto b){return a.key<b.key;});sparse::write((out/(kind+"_part_"+std::to_string(part)+"_run_"+std::to_string(run)+".bin")).string(),rows);values.clear();}
static void edge(Acc& values,uint32_t a,uint32_t b,long double capacitance){if(a==b||capacitance==0)return;if(a>b)std::swap(a,b);values[(uint64_t(a)<<32)|a].add(capacitance);values[(uint64_t(b)<<32)|b].add(capacitance);values[(uint64_t(a)<<32)|b].add(-capacitance);}
static void whitespace(std::istream& in){while(in.peek()==' '||in.peek()=='\n'||in.peek()=='\r'||in.peek()=='\t')in.get();}
int main(int argc,char**argv){try{
 require(argc==2,"usage: collapse_native_cap_ledger CONFIG");auto cfg=Json::read(argv[1]);ConductorMap fields(cfg.at("field_map").str(),"CNETFLD1");I threads=cfg.at("threads").integer(),limit=cfg.at("max_accumulator_entries").integer();require(threads>0&&threads<=16&&limit>=16&&limit<=4000000,"bounded ledger reduction resources");double deadline=cfg.at("deadline_uptime").num();
 fs::path out=cfg.at("output").str();require(fs::create_directory(out),"fresh native conductor ledger directory");auto path=cfg.at("ledger").str();I size=I(fs::file_size(path));std::vector<std::exception_ptr> errors(threads);std::vector<I> counts(threads),self(threads),physical_runs(threads),native_runs(threads);
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{
  std::ifstream input(path,std::ios::binary);require(bool(input),"native capacitor ledger input");I start=size*part/threads,end=size*(part+1)/threads;input.seekg(start);char c=0;
  if(start==0){whitespace(input);require(input.get(c)&&c=='[',"native capacitor ledger root");whitespace(input);}
  else{while(input.peek()!=EOF&&input.peek()!='[')input.get();}
  Acc physical,native;physical.reserve(size_t(limit));native.reserve(size_t(limit));std::string raw;
  while(true){whitespace(input);I offset=I(input.tellg());if(offset<0||offset>=end||input.peek()==']'||input.peek()==EOF)break;require(now()<deadline,"native ledger collapse deadline");require(input.get(c)&&c=='[',"flat numeric capacitor ledger row");require(bool(std::getline(input,raw,']'))&&raw.size()<4096&&raw.find('[')==std::string::npos,"complete bounded capacitor ledger row");auto row=Json::parse("["+raw+"]");require(row.arr().size()==5,"native capacitor ledger width");I a=row.at(0).integer(),b=row.at(1).integer();require(a>=0&&a<=b&&b<I(fields.size()),"ordered native field edge");uint32_t x=fields.at(a),y=fields.at(b);counts[part]++;self[part]+=x==y;
   // Producer ledger columns are [field_a,field_b,native_delta,operator_integral,absolute_error].
   edge(physical,x,y,static_cast<long double>(row.at(3).num()));edge(native,x,y,static_cast<long double>(row.at(2).num()));require(row.at(4).num()>=0,"nonnegative native integration error");
   if(I(physical.size())>=limit)flush(physical,out,"physical",part,physical_runs[part]++);if(I(native.size())>=limit)flush(native,out,"native",part,native_runs[part]++);
   whitespace(input);require(bool(input.get(c))&&(c==','||c==']'),"native ledger row separator");if(c==']'){whitespace(input);require(input.peek()==EOF,"native ledger trailing bytes");break;}
  }require(!input.bad(),"native ledger read failure");if(!physical.empty())flush(physical,out,"physical",part,physical_runs[part]++);if(!native.empty())flush(native,out,"native",part,native_runs[part]++);
 }catch(...){errors[part]=std::current_exception();}}
 for(auto& error:errors)if(error)std::rethrow_exception(error);I total=0,ns=0,np=0,nn=0;for(I p=0;p<threads;p++){total+=counts[p];ns+=self[p];np+=physical_runs[p];nn+=native_runs[p];}require(total==cfg.at("expected_rows").integer(),"full native ledger row coverage");
 Json result=Json::object();result["ledger_rows"]=total;result["same_conductor_scalar_edges_ignored"]=ns;result["physical_runs"]=np;result["native_runs"]=nn;result["conductor_nets"]=I(fields.net_count());result["threads"]=threads;result["physical_RC_qualified"]=false;result["release_qualified"]=false;std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
