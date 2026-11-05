// Exact record ownership; inclusive support boxes conservatively select all target terms.
#include "target_support_index.hpp"
#include "bounded_jsonl_range.hpp"
#include <atomic>
#include <filesystem>
#include <memory>
#include <omp.h>
#include <iostream>
#include <time.h>
namespace fs=std::filesystem;using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();
 I threads=cfg.at("threads").integer();require(threads>0&&threads<=32,"selector thread bound");target_support::Index support(cfg.at("support_triangles").str());
 const auto&tasks=cfg.at("shards").arr();require(!tasks.empty()&&tasks.size()<=16384,"bounded selector tasks");
 struct Partition{uint64_t size;std::string map;std::vector<std::pair<uint64_t,uint64_t>>spans;};
 std::map<std::string,Partition>partitions;std::map<std::string,std::shared_ptr<const std::vector<I>>>maps;
 std::vector<std::shared_ptr<const std::vector<I>>>mapping;
 for(const auto&task:tasks){
  std::string path=fs::canonical(task.at("operators").str()),map=fs::canonical(task.at("field_map").str());auto size=fs::file_size(path);
  auto lo=task.at("begin_byte").integer(),hi=task.at("end_byte").integer();require(lo>=0&&hi>=lo&&uint64_t(hi)<=size,"selector task bounds");
  auto[it,fresh]=partitions.try_emplace(path,Partition{size,map,{}});require(it->second.map==map,"one field map per source");it->second.spans.emplace_back(lo,hi);
  if(!maps.contains(map)){auto json=Json::read(map);auto values=std::make_shared<std::vector<I>>();
   for(const auto&id:json.arr()){auto global=id.integer();require(global>=0&&global<cfg.at("global_fields").integer(),"selector global field bounds");values->push_back(global);}
   require(!values->empty()&&values->at(0)==0,"shared explicit reference field");maps.emplace(map,values);}
  mapping.push_back(maps.at(map));
 }
 for(auto&[path,p]:partitions){std::sort(p.spans.begin(),p.spans.end());uint64_t end=0;for(auto[lo,hi]:p.spans){require(lo==end,"disjoint gap-free selector partition");end=hi;}require(end==p.size,"complete selector file coverage");}
 fs::path output=cfg.at("output").str();require(fs::create_directory(output),"fresh selector output");
 std::vector<uint64_t>counts(tasks.size()),selected(tasks.size());std::vector<std::exception_ptr>errors(tasks.size());std::atomic<bool>cancelled{false};
 #pragma omp parallel for num_threads(threads) schedule(dynamic,1)
 for(I task=0;task<I(tasks.size());task++){if(cancelled.load())continue;try{
  const auto&spec=tasks[task];const auto&map=*mapping[task];
  std::ofstream records(output/("task_"+std::to_string(task)+".operators.jsonl")),offsets(output/("task_"+std::to_string(task)+".offsets.bin"),std::ios::binary);
  require(bool(records)&&bool(offsets),"selector record output");bounded_jsonl::Range input(spec.at("operators").str(),spec.at("begin_byte").integer(),spec.at("end_byte").integer());
  std::string raw;uint64_t offset;
  while(input.next(raw,offset)){
   if(counts[task]++%10000==0){require(now()<deadline,"selector full scan deadline");Json p=Json::object();p["operators"]=I(counts[task]);p["selected"]=I(selected[task]);
    std::ofstream status(output/("task_"+std::to_string(task)+".status.json"));status<<p.dump()<<'\n';require(bool(status),"selector status write");}
   auto op=Json::parse(raw);I a=op.at(1).integer(),b=op.at(2).integer();require(a>=0&&b>=0&&a<I(map.size())&&b<I(map.size()),"selector local field bounds");
   auto kind=op.at(0).str();require(kind=="A"||kind=="L"||kind=="F","selector supported operator");
   auto first=target_support::box(op.at(4)),second=kind=="A"?first:target_support::box(op.at(5));
   if(!support.contains(map[a],first)&&!support.contains(map[b],second))continue;
   records<<raw<<'\n';char bytes[8];for(int k=0;k<8;k++)bytes[k]=char(offset>>(8*k));offsets.write(bytes,8);selected[task]++;
  }
  records.close();offsets.close();require(bool(records)&&bool(offsets),"selector output close");
  Json summary=Json::object();summary["task"]=task;summary["operators"]=I(counts[task]);summary["selected_operators"]=I(selected[task]);
  std::ofstream report(output/("task_"+std::to_string(task)+".summary.json"));report<<summary.dump()<<'\n';require(bool(report),"selector task report close");
 }catch(...){errors[task]=std::current_exception();cancelled=true;}}
 for(const auto&e:errors)if(e)std::rethrow_exception(e);uint64_t total=0,nselected=0;Json affected=Json::array(),summaries=Json::array();
 for(size_t k=0;k<tasks.size();k++){total+=counts[k];nselected+=selected[k];if(selected[k])affected.push(I(k));
  Json row=Json::object();row["task"]=I(k);row["operators"]=I(counts[k]);row["selected_operators"]=I(selected[k]);summaries.push(row);}
 require(total==uint64_t(cfg.at("expected_operators").integer()),"selector full operator count");Json report=Json::object();
 report["operators"]=I(total);report["selected_operators"]=I(nselected);report["affected_tasks"]=affected;report["task_counts"]=summaries;
 report["full_operator_coverage"]=true;report["disjoint_gap_free_byte_partitions_validated"]=true;
 report["selection"]=std::string("conservative inclusive boxes of every affected P1 triangle; false positives retained");
 report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream out(cfg.at("report").str());out<<report.dump()<<'\n';out.close();require(bool(out),"selector report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
