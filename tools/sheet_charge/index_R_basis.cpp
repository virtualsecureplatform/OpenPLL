#include "../charge_compiler/json.hpp"
#include <cstdint>
#include <iostream>
#include <time.h>
struct Entry{uint64_t offset=UINT64_MAX;uint32_t length=0,bundle=0;};
static void write_int(std::ostream& o,uint64_t n,int bytes){for(int k=0;k<bytes;k++)o.put(char(n>>(8*k)));}
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==2,"usage: index_R_basis CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();
 std::vector<Entry> bundles;std::ifstream input(cfg.at("bundles").str(),std::ios::binary);require(bool(input),"bundles open");
 std::string raw;uint64_t offset=0;
 while(std::getline(input,raw)){require(now()<deadline&&!input.eof(),"bundle deadline/terminator");auto row=Json::parse(raw);
  require(row.at("bundle_id").integer()==static_cast<long long>(bundles.size()),"contiguous bundle ID");
  require(raw.size()<UINT32_MAX,"bundle length");bundles.push_back({offset,uint32_t(raw.size()),uint32_t(bundles.size())});offset+=raw.size()+1;
 }require(input.eof()&&!input.bad(),"bundle read");
 std::ifstream fields(cfg.at("fields").str(),std::ios::binary);require(bool(fields),"field map open");std::vector<Entry> entries;std::vector<bool> used(bundles.size());long long selected=0;
 while(std::getline(fields,raw)){require(now()<deadline&&!fields.eof(),"field deadline/terminator");auto row=Json::parse(raw);
  require(row.at("field_id").integer()==static_cast<long long>(entries.size()),"contiguous field ID");Entry e;
  if(row.at("support_state").str()=="exact_native_R_tile_candidates"){
   auto id=row.at("R_tile_bundle_id").integer();require(id>=0&&id<static_cast<long long>(bundles.size())&&!used[id],"unique valid bundle");
   e=bundles[id];used[id]=true;++selected;
  }entries.push_back(e);
 }require(fields.eof()&&!fields.bad(),"field map read");require(selected==static_cast<long long>(bundles.size()),"all bundles bound");
 std::ofstream output(cfg.at("index").str(),std::ios::binary);require(bool(output),"index output");output.write("RBSIDX01",8);write_int(output,entries.size(),8);
 for(auto e:entries){write_int(output,e.offset,8);write_int(output,e.length,4);write_int(output,e.bundle,4);}output.close();require(bool(output),"index close");
 Json result=Json::object();result["global_fields"]=static_cast<long long>(entries.size());result["R_fields"]=selected;result["release_qualified"]=false;std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
