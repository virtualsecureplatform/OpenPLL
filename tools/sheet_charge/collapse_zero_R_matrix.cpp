// For a verified compacting zero-R map, only entries touching removed IDs
// require sorting. The injective complement preserves strict sparse key order.
#include "../charge_compiler/json.hpp"
#include "sparse_run_slice.hpp"
#include "conductor_map.hpp"
#include <unordered_map>
#include <array>
#include <iostream>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==2,"usage: collapse_zero_R_matrix CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();ConductorMap map(cfg.at("voltage_map").str(),"CNETDOF1");std::vector<uint8_t> removed(map.size());std::vector<std::array<uint32_t,3>> aliases;std::ifstream alias_input(cfg.at("aliases").str());require(bool(alias_input),"zero-R aliases input");std::string line;uint32_t prior=0;
 while(std::getline(alias_input,line)){auto row=Json::parse(line);require(row.arr().size()==3,"zero-R alias tuple");I a=row.at(0).integer(),root=row.at(1).integer(),target=row.at(2).integer();require(a>I(prior)&&a<I(map.size())&&root>0&&root<a&&target>=0&&target<I(map.net_count()),"canonical positive zero-R alias");removed[a]=1;aliases.push_back({uint32_t(a),uint32_t(root),uint32_t(target)});prior=a;}
 require(alias_input.eof(),"complete alias ledger");uint32_t next=0;for(uint64_t i=0;i<map.size();i++){if(i%100000==0)require(now()<deadline,"compacting map validation deadline");if(!removed[i])require(map.at(i)==next++,"map complement must be strictly compacting identity");}require(next==map.net_count()&&map.at(0)==0,"complete compacted namespace and preserved reference");for(auto[a,root,target]:aliases)require(!removed[root]&&map.at(a)==map.at(root)&&map.at(a)==target,"zero-R alias root consistency");
 auto out=std::filesystem::path(cfg.at("output").str());require(std::filesystem::create_directory(out),"fresh zero-R collapse output");I limit=cfg.at("max_accumulator_entries").integer();require(limit>=16&&limit<=1000000,"bounded exceptional accumulator");std::unordered_map<uint64_t,sparse::Value> acc;acc.reserve(limit);I runs=0;
 auto flush=[&](){if(acc.empty())return;std::vector<sparse::Record> records;records.reserve(acc.size());for(auto&[key,v]:acc)records.push_back({key,v.signed_sum.value(),v.absolute_sum.value(),v.terms});std::sort(records.begin(),records.end(),[](auto&a,auto&b){return a.key<b.key;});sparse::write((out/("exception_"+std::to_string(runs++)+".bin")).string(),records);acc.clear();};
 std::ofstream ordered(out/"ordered.bin",std::ios::binary);require(bool(ordered),"ordered complement output");sparse::header(ordered,0);auto path=cfg.at("matrix").str();sparse::SliceReader header(path,0,0),input(path,0,header.total);sparse::Record row;uint64_t direct=0,exceptional=0,terms=0,doubled=0,last=0;bool have=false;
 while(input.next(row)){if((direct+exceptional)%10000==0)require(now()<deadline,"zero-R sparse transform deadline");uint64_t i=row.key>>32,j=row.key&UINT32_MAX;uint32_t a=map.at(i),b=map.at(j);require(terms<=UINT64_MAX-row.terms,"zero-R source term overflow");terms+=row.terms;
  if(!removed[i]&&!removed[j]){require(a<=b,"ordered complement upper keys");row.key=(uint64_t(a)<<32)|b;require(!have||last<row.key,"ordered complement strictly increasing");last=row.key;have=true;sparse::write_record(ordered,row);direct++;}
  else{if(a>b)std::swap(a,b);long double factor=(a==b&&i!=j)?2.L:1.L;acc[(uint64_t(a)<<32)|b].merge(row.value*factor,row.absolute*factor,row.terms);exceptional++;doubled+=factor==2;if(I(acc.size())>=limit)flush();}
 }flush();require(direct+exceptional==header.total,"complete zero-R source coverage");ordered.seekp(0);sparse::header(ordered,direct);ordered.close();require(bool(ordered),"ordered complement close");Json report=Json::object();report["source_upper_entries"]=I(header.total);report["source_terms"]=I(terms);report["ordered_entries_without_sort"]=I(direct);report["exceptional_entries_sorted"]=I(exceptional);report["symmetry_doubled_entries"]=I(doubled);report["sparse_runs"]=runs+1;report["original_voltage_nodes"]=I(map.size());report["constrained_voltage_nodes"]=I(map.net_count());report["all_compacting_map_slots_validated"]=true;report["physical_RC_qualified"]=false;report["release_qualified"]=false;std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
