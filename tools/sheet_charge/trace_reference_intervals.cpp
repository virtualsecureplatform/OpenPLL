// Independent scalar analytic reference and stable task/record provenance.
#include "fringe_interval.hpp"
#include "conductor_map.hpp"
#include "bounded_jsonl_range.hpp"
#include <filesystem>
#include <memory>
#include <set>
#include <omp.h>
#include <atomic>
#include <iostream>
#include <time.h>
namespace fs=std::filesystem;using I=long long;using Q=mpq_class;using V=fringe_interval::Interval;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static std::array<I,4> box(const Json&v){require(v.arr().size()==4,"box width");std::array<I,4>b;for(int k=0;k<4;k++)b[k]=v.at(k).integer();require(b[0]<=b[2]&&b[1]<=b[3],"ordered box");return b;}
static Q length(const std::array<I,4>&b){require(b[0]==b[2]||b[1]==b[3],"axis-aligned edge");return Q(long(b[2]-b[0]))+Q(long(b[3]-b[1]));}
static V integral(const Json&op){
 auto kind=op.at(0).str();auto a=box(op.at(4));
 if(kind=="A")return V(Q(long(a[2]-a[0]))*Q(long(a[3]-a[1]))*Q(op.at(5).num()));
 auto b=box(op.at(5));if(kind=="L"){require(length(a)==length(b),"matching line lengths");return V(length(a)*Q(op.at(6).num()));}
 require(kind=="F","supported analytic operator");int d=op.at(6).integer();I near=0,far=0,span=0;
 if(d==1){b[2]=std::min(b[2],a[0]);near=a[0]-b[2];far=a[0]-b[0];span=b[3]-b[1];}
 else if(d==2){b[1]=std::max(b[1],a[1]);near=b[1]-a[1];far=b[3]-a[1];span=b[2]-b[0];}
 else if(d==4){b[0]=std::max(b[0],a[0]);near=b[0]-a[0];far=b[2]-a[0];span=b[3]-b[1];}
 else{require(d==8,"fringe direction");b[3]=std::min(b[3],a[1]);near=a[1]-b[3];far=a[1]-b[1];span=b[2]-b[0];}
 Q m(op.at(8).num());require(near>=0&&far>=near&&span>=0&&m>=0,"fringe scalar geometry");
 if(m==0||near==far||span==0)return V();
 V lower(Q(long(near))*m),upper(Q(long(far))*m);
 return V(Q(op.at(7).num())*Q(long(span))*Q(double(.6366)))*(fringe_interval::atan(upper)-fringe_interval::atan(lower));
}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);auto bits=cfg.at("precision_bits").integer();require(bits>=128&&bits<=1024,"precision bound");
 auto threads=cfg.at("threads").integer();require(threads>0&&threads<=32,"thread bound");double deadline=cfg.at("deadline_uptime").num();
 ConductorMap fields(cfg.at("field_map").str(),"CNETFLD1");require(fields.net_count()>1,"reference conductor namespace");
 auto&tasks=cfg.at("shards").arr();require(!tasks.empty()&&tasks.size()<=16384,"bounded task count");
 struct Partition{uint64_t size;std::string map;std::vector<std::pair<uint64_t,uint64_t>>spans;};
 std::map<std::string,Partition>partitions;std::map<std::string,std::shared_ptr<const std::vector<I>>>maps;
 std::vector<std::shared_ptr<const std::vector<I>>>mapping;
 for(const auto&task:tasks){
  std::string path=fs::canonical(task.at("operators").str()),map=fs::canonical(task.at("field_map").str());
  auto lo=task.at("begin_byte").integer(),hi=task.at("end_byte").integer();auto size=fs::file_size(path);
  require(lo>=0&&hi>=lo&&uint64_t(hi)<=size,"task bounds");auto[it,fresh]=partitions.try_emplace(path,Partition{size,map,{}});
  require(it->second.map==map,"one field map per operator file");it->second.spans.emplace_back(lo,hi);
  if(!maps.contains(map)){auto json=Json::read(map);auto values=std::make_shared<std::vector<I>>();
   for(const auto&id:json.arr()){auto global=id.integer();require(global>=0&&uint64_t(global)<fields.size(),"global field map bounds");values->push_back(global);}
   require(!values->empty()&&values->at(0)==0,"shared explicit reference");maps.emplace(map,values);}
  mapping.push_back(maps.at(map));
 }
 for(auto&[path,p]:partitions){std::sort(p.spans.begin(),p.spans.end());uint64_t end=0;for(auto[lo,hi]:p.spans){require(lo==end,"disjoint gap-free task partition");end=hi;}require(end==p.size,"complete task file coverage");}
 fs::path output=cfg.at("output").str();require(fs::create_directory(output),"fresh reference trace output");
 fringe_interval::precision=bits;std::vector<V>diagonal(tasks.size()),edge(tasks.size());
 std::vector<uint64_t>counts(tasks.size()),selected(tasks.size()),edge_counts(tasks.size());std::vector<Json>summaries(tasks.size());
 std::vector<std::exception_ptr>errors(tasks.size());std::atomic<bool>cancelled{false};
 #pragma omp parallel for num_threads(threads) schedule(dynamic,1)
 for(I task=0;task<I(tasks.size());task++){if(cancelled.load())continue;try{
  fringe_interval::precision=bits;const auto&spec=tasks[task];const auto&map=*mapping[task];
  std::ofstream chosen(output/("task_"+std::to_string(task)+".operators.jsonl"));
  std::ofstream offsets(output/("task_"+std::to_string(task)+".offsets.bin"),std::ios::binary);
  require(bool(chosen)&&bool(offsets),"trace output open");bounded_jsonl::Range input(spec.at("operators").str(),spec.at("begin_byte").integer(),spec.at("end_byte").integer());
  std::string raw;uint64_t offset;
  while(input.next(raw,offset)){
   if(counts[task]++%1000==0){require(now()<deadline,"reference trace deadline");Json status=Json::object();status["operators"]=I(counts[task]);status["selected"]=I(selected[task]);
    std::ofstream progress(output/("task_"+std::to_string(task)+".status.json"));progress<<status.dump()<<'\n';require(bool(progress),"trace progress write");}
   auto op=Json::parse(raw);auto a=op.at(1).integer(),b=op.at(2).integer();require(a>=0&&b>=0&&a<I(map.size())&&b<I(map.size()),"local field bounds");
   uint32_t x=fields.at(map[a]),y=fields.at(map[b]);if(x==y||(x!=0&&y!=0))continue;
   chosen<<raw<<'\n';char bytes[8];for(int k=0;k<8;k++)bytes[k]=char(offset>>(8*k));offsets.write(bytes,8);selected[task]++;
   auto value=integral(op);diagonal[task]=diagonal[task]+value;
   if(x==1||y==1){edge[task]=edge[task]-value;edge_counts[task]++;}
  }
  chosen.close();offsets.close();require(bool(chosen)&&bool(offsets),"trace output close");
  Json summary=Json::object();summary["task"]=task;summary["operators"]=I(counts[task]);summary["selected_reference_operators"]=I(selected[task]);
  summary["selected_reference_edge_operators"]=I(edge_counts[task]);summary["diagonal_0_interval"]=fringe_interval::json(diagonal[task]);
  summary["edge_0_1_interval"]=fringe_interval::json(edge[task]);summaries[task]=summary;
  std::ofstream report(output/("task_"+std::to_string(task)+".summary.json"));report<<summary.dump()<<'\n';require(bool(report),"trace task summary close");
 }catch(...){errors[task]=std::current_exception();cancelled=true;}}
 for(const auto&e:errors)if(e)std::rethrow_exception(e);V diagonal_sum,edge_sum;uint64_t total=0,nselected=0,affected=0;Json parts=Json::array();
 for(size_t i=0;i<tasks.size();i++){diagonal_sum=diagonal_sum+diagonal[i];edge_sum=edge_sum+edge[i];total+=counts[i];nselected+=selected[i];affected+=selected[i]>0;parts.push(summaries[i]);}
 require(total==uint64_t(cfg.at("expected_operators").integer()),"full operator coverage");
 Json report=Json::object();report["operators"]=I(total);report["selected_reference_operators"]=I(nselected);report["affected_tasks"]=I(affected);
 report["tasks"]=parts;report["diagonal_0_interval"]=fringe_interval::json(diagonal_sum);report["edge_0_1_interval"]=fringe_interval::json(edge_sum);
 report["disjoint_gap_free_byte_partitions_validated"]=true;report["full_operator_coverage"]=true;
 report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream result(cfg.at("report").str());result<<report.dump()<<'\n';result.close();require(bool(result),"trace report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
