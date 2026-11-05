#include "../charge_compiler/json.hpp"
#include "sparse_run_slice.hpp"
#include "charge_rows.hpp"
#include <filesystem>
#include <unordered_map>
#include <omp.h>
#include <iostream>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();I threads=cfg.at("threads").integer(),limit=cfg.at("max_accumulator_entries").integer();require(threads>0&&threads<=16&&limit>=16&&limit<=1000000,"bounded charge projection resources");
 std::ifstream roles_file(cfg.at("roles").str(),std::ios::binary);require(bool(roles_file),"roles open");char h[24];roles_file.read(h,24);require(bool(roles_file)&&std::string(h,8)=="GROLE001"&&sparse::load(h+16)==4,"role format");uint64_t conductors=sparse::load(h+8);require(conductors>0&&conductors<=UINT32_MAX,"component count");std::vector<uint8_t> roles(conductors);roles_file.read((char*)roles.data(),conductors);require(bool(roles_file),"all roles");char extra;require(!roles_file.get(extra)&&roles_file.eof(),"role end");
 std::vector<uint32_t> row(conductors,UINT32_MAX),row_components;for(uint32_t i=0;i<conductors;i++){require(roles[i]<=3,"role code");if(roles[i]>=2){row[i]=row_components.size();row_components.push_back(i);}}require(!row_components.empty()&&roles[0]==0,"unattached nonreference components required");
 std::ifstream map_file(cfg.at("components").str(),std::ios::binary);require(bool(map_file),"component map open");map_file.read(h,24);require(bool(map_file)&&std::string(h,8)=="CNETDOF1"&&sparse::load(h+16)==conductors,"component map format");uint64_t nodes=sparse::load(h+8);require(nodes>0&&nodes<=UINT32_MAX,"voltage count");std::vector<uint32_t> component(nodes);map_file.read((char*)component.data(),nodes*4);require(bool(map_file),"component entries");require(!map_file.get(extra)&&map_file.eof(),"component end");for(auto c:component)require(c<conductors,"component bound");
 auto directory=cfg.at("output").str();require(std::filesystem::create_directory(directory),"fresh charge run directory");std::ofstream row_map(directory+"/row_components.bin",std::ios::binary);row_map.write("QROWNET1",8);sparse::store(h,row_components.size());sparse::store(h+8,conductors);row_map.write(h,16);row_map.write((char*)row_components.data(),row_components.size()*4);row_map.close();require(bool(row_map),"charge row registry close");
 std::string matrix=cfg.at("matrix").str();sparse::SliceReader header(matrix,0,0);uint64_t total=header.total;std::vector<std::exception_ptr> errors(threads);std::vector<uint64_t> runs(threads),read(threads),contributions(threads);
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{
  std::unordered_map<uint64_t,sparse::Value> acc;acc.reserve(limit);auto flush=[&](){std::vector<sparse::Record> values;values.reserve(acc.size());for(auto&[key,v]:acc)values.push_back({key,v.signed_sum.value(),v.absolute_sum.value(),v.terms});std::sort(values.begin(),values.end(),[](auto&a,auto&b){return a.key<b.key;});charge::write(directory+"/part_"+std::to_string(part)+"_run_"+std::to_string(runs[part]++)+".bin",row_components.size(),nodes,values);acc.clear();};
  auto add=[&](uint32_t voltage,uint32_t column,const sparse::Record&r){uint32_t target=row[component[voltage]];if(target==UINT32_MAX)return;uint64_t key=(uint64_t(target)<<32)|column;acc[key].merge(r.value,r.absolute,r.terms);contributions[part]++;};
  sparse::SliceReader input(matrix,total*part/threads,total*(part+1)/threads);sparse::Record r;while(input.next(r)){if(read[part]++%10000==0)require(now()<deadline,"charge projection deadline");uint32_t i=r.key>>32,j=r.key&UINT32_MAX;require(i<=j&&j<nodes,"source C voltage bounds");add(i,j,r);if(i!=j)add(j,i,r);if(acc.size()>=uint64_t(limit))flush();}if(!acc.empty()||runs[part]==0)flush();
 }catch(...){errors[part]=std::current_exception();}}
 for(auto&e:errors)if(e)std::rethrow_exception(e);auto sum=[](auto&v){uint64_t n=0;for(auto x:v)n+=x;return n;};require(sum(read)==total,"full source C record coverage");Json report=Json::object();report["source_upper_entries"]=I(total);report["source_entries_scanned"]=I(sum(read));report["rectangular_contributions"]=I(sum(contributions));report["charge_rows"]=I(row_components.size());report["voltage_columns"]=I(nodes);report["sparse_runs"]=I(sum(runs));std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
