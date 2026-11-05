#include "../charge_compiler/json.hpp"
#include "sparse_runs.hpp"
#include <memory>
#include <queue>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <time.h>
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static std::string number(long double value){std::ostringstream out;out<<std::setprecision(std::numeric_limits<long double>::max_digits10)<<value;return out.str();}
int main(int argc,char**argv){try{
 require(argc==2,"usage: merge_sparse_runs CONFIG");auto cfg=Json::read(argv[1]);auto& inputs=cfg.at("inputs").arr();require(inputs.size()>0&&inputs.size()<=128,"bounded merge fan-in");
 struct Item{sparse::Record record;size_t source;bool operator<(const Item& b)const{return std::pair{record.key,source}>std::pair{b.record.key,b.source};}};
 std::vector<std::unique_ptr<sparse::Reader>> readers;std::priority_queue<Item> heap;for(auto& path:inputs){readers.push_back(std::make_unique<sparse::Reader>(path.str()));sparse::Record r;if(readers.back()->next(r))heap.push({r,readers.size()-1});}
 std::ofstream out(cfg.at("output").str(),std::ios::binary);require(bool(out),"merged sparse output");sparse::header(out,0);std::ofstream json;if(cfg.obj().count("json_output")){json.open(cfg.at("json_output").str());require(bool(json),"merge JSON output");}
 uint64_t count=0,total_terms=0;while(!heap.empty()){
  require(now()<cfg.at("deadline_uptime").num(),"sparse merge deadline");uint64_t key=heap.top().record.key;sparse::Value value;
  do{auto item=heap.top();heap.pop();value.merge(item.record.value,item.record.absolute,item.record.terms);sparse::Record next;if(readers[item.source]->next(next))heap.push({next,item.source});}while(!heap.empty()&&heap.top().record.key==key);
  sparse::Record merged{key,value.signed_sum.value(),value.absolute_sum.value(),value.terms};sparse::write_record(out,merged);require(total_terms<=UINT64_MAX-merged.terms,"merged term overflow");total_terms+=merged.terms;count++;
  if(json.is_open()){Json row=Json::Array{static_cast<long long>(key>>32),static_cast<long long>(key&UINT32_MAX),number(merged.value),number(merged.absolute),static_cast<long long>(merged.terms)};json<<row.dump()<<'\n';}
 }out.seekp(8);char bytes[8];sparse::store(bytes,count);out.write(bytes,8);out.close();require(bool(out),"sparse merge close");if(json.is_open()){json.close();require(bool(json),"merge JSON close");}
 Json report=Json::object();report["matrix_upper_entries"]=static_cast<long long>(count);report["contributing_terms"]=static_cast<long long>(total_terms);report["input_runs"]=static_cast<long long>(inputs.size());report["physical_RC_qualified"]=false;report["release_qualified"]=false;std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
