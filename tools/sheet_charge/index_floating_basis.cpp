// Compact field-to-instance offsets. Meshes stay shared and are resolved lazily.
#include "../charge_compiler/json.hpp"
#include <atomic>
#include <cstdint>
#include <iostream>
#include <memory>
#include <omp.h>
#include <time.h>
struct Entry { uint64_t offset=UINT64_MAX; uint32_t length=0, partition=0; };
static_assert(sizeof(Entry)==16);
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static void u64(std::ostream& o,uint64_t n,int bytes){for(int k=0;k<bytes;k++)o.put(char(n>>(8*k)));}
int main(int argc,char** argv){try{
 require(argc==2,"usage: index_floating_basis CONFIG");auto cfg=Json::read(argv[1]);
 auto count=cfg.at("global_fields").integer();require(count>0&&count<100000000,"field count bounds");
 double deadline=cfg.at("deadline_uptime").num();std::vector<Entry> entries(count);
 auto seen=std::make_unique<std::atomic<bool>[]>(count);for(long long i=0;i<count;i++)seen[i]=false;
 auto& parts=cfg.at("partitions").arr();require(parts.size()==7,"seven material partitions required");
 std::vector<std::exception_ptr> errors(parts.size());std::vector<long long> counts(parts.size());
 #pragma omp parallel for num_threads(7)
 for(int part=0;part<int(parts.size());part++){try{
  std::ifstream input(parts[part].at("path").str(),std::ios::binary);require(bool(input),"instance input");
  uint64_t offset=0;std::string line;
  while(std::getline(input,line)){
   require(now()<deadline,"index deadline");require(!input.eof(),"unterminated instance row");
   auto row=Json::parse(line);auto id=row.at("physical_field_id").integer();
   require(id>0&&id<count,"physical field range");require(!seen[id].exchange(true),"duplicate physical field");
   require(row.at("native_type").str()==parts[part].at("native_type").str(),"partition material");
   require(row.at("voltage_namespace").str()=="_fmesh_"+std::to_string(id),"field namespace");
   require(line.size()<UINT32_MAX,"instance length");entries[id]={offset,uint32_t(line.size()),uint32_t(part)};
   offset+=line.size()+1;counts[part]++;
  }require(input.eof(),"instance read failure");
 }catch(...){errors[part]=std::current_exception();}}
 for(auto& error:errors)if(error)std::rethrow_exception(error);
 long long total=0;for(auto n:counts)total+=n;require(total==cfg.at("expected_instances").integer(),"instance count");
 std::ofstream output(cfg.at("index").str(),std::ios::binary);require(bool(output),"index output");
 output.write("FBSIDX01",8);u64(output,count,8);
 for(auto e:entries){u64(output,e.offset,8);u64(output,e.length,4);u64(output,e.partition,4);}
 output.close();require(bool(output),"index close");
 Json result=Json::object();result["indexed_instances"]=total;result["global_fields"]=count;
 result["entry_bytes"]=16;result["threads"]=7;result["release_qualified"]=false;
 std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
