#define main registered_projection_control_main
#include "main_registered_rational.cpp"
#undef main
#include "runtime_geometry_v2.hpp"
#include "sparse_runs_v2.hpp"
#include "bounded_jsonl_range.hpp"
#include <memory>
namespace fs=std::filesystem;
using Accumulator=std::unordered_map<uint64_t,sparse::Value>;
static void flush(Accumulator& values,const fs::path& output,I shard,I run){
 std::vector<sparse::Record> rows;rows.reserve(values.size());for(auto&[key,v]:values)rows.push_back({key,v.signed_sum.value(),v.absolute_sum.value(),v.terms});
 std::sort(rows.begin(),rows.end(),[](auto a,auto b){return a.key<b.key;});sparse::write((output/("shard_"+std::to_string(shard)+"_run_"+std::to_string(run)+".bin")).string(),rows);values.clear();
}
static bool zero_measure(const Json& op){auto kind=op.at(0).str();auto& a=op.at(4);double density=op.at(kind=="A"?5:kind=="L"?6:7).num();if(density==0)return true;
 if(kind=="A")return a.at(0).integer()==a.at(2).integer()||a.at(1).integer()==a.at(3).integer();
 if(kind=="L")return a.at(0).integer()==a.at(2).integer()&&a.at(1).integer()==a.at(3).integer();
 require(kind=="F","native operator kind");if(op.at(8).num()==0)return true;auto b=op.at(5);int direction=int(op.at(6).integer()),normal=(direction==1||direction==4)?0:1,sign=(direction==1||direction==8)?-1:1;I origin=a.at(normal).integer();
 I lo=b.at(normal).integer(),hi=b.at(normal+2).integer();if(sign>0)lo=std::max(lo,origin);else hi=std::min(hi,origin);
 return lo==hi||b.at(1-normal).integer()==b.at(3-normal).integer();
}
int main(int argc,char**argv){try{
 require(argc==2,"usage: stream_project_charge CONFIG");auto cfg=Json::read(argv[1]);double start=uptime(),deadline=cfg.at("deadline_uptime").num();
 fs::path output=cfg.at("output").str();require(fs::create_directory(output),"fresh sparse projection output");
 auto& shards=cfg.at("shards").arr();I threads=cfg.at("threads").integer(),limit=cfg.at("max_accumulator_entries").integer(),cache_limit=cfg.at("cache_limit_bytes_per_thread").integer();require(threads>0&&threads<=32&&limit>=16&&limit<=8000000&&cache_limit>=0&&cache_limit<=134217728,"bounded projection resources");
 // Validate a full, disjoint byte partition per canonical input, with one field map.
 std::vector<std::shared_ptr<const std::vector<I>>> mappings;std::map<std::string,std::shared_ptr<const std::vector<I>>> shared_maps;
 struct Partition{uint64_t size;std::string map;std::vector<std::pair<uint64_t,uint64_t>> spans;};std::map<std::string,Partition> partitions;
 for(auto&spec:shards){std::string path=fs::canonical(spec.at("operators").str()).string(),map=fs::canonical(spec.at("field_map").str()).string();I lo=spec.at("begin_byte").integer(),hi=spec.at("end_byte").integer();uint64_t size=fs::file_size(path);require(lo>=0&&hi>=lo&&uint64_t(hi)<=size,"task byte bounds");auto [it,fresh]=partitions.try_emplace(path,Partition{size,map,{}});require(it->second.map==map,"one field map per operator file");it->second.spans.emplace_back(lo,hi);
  if(!shared_maps.contains(map)){auto json=Json::read(map);auto values=std::make_shared<std::vector<I>>();for(auto&id:json.arr())values->push_back(id.integer());require(!values->empty()&&values->at(0)==0,"explicit shared shard reference");shared_maps.emplace(map,values);}mappings.push_back(shared_maps.at(map));
 }
 for(auto&[path,p]:partitions){std::sort(p.spans.begin(),p.spans.end());uint64_t cursor=0;for(auto [lo,hi]:p.spans){require(lo==cursor,"disjoint gap-free operator byte partition");cursor=hi;}require(cursor==p.size,"full operator file byte partition");}
 RuntimeGeometry geometry(cfg.at("geometry"));require(geometry.node_count()<=UINT32_MAX,"packed global voltage bound");geometry.write_node_map(output.string());
 I cap=cfg.at("max_records_per_shard").integer();require(cap>=0,"nonnegative record bound");std::vector<std::exception_ptr> errors(shards.size());std::vector<I> counts(shards.size()),zeros(shards.size()),runs(shards.size());std::atomic<bool> cancelled{false};
 #pragma omp parallel for num_threads(threads) schedule(dynamic,1)
 for(I si=0;si<I(shards.size());si++){I offset=0;try{
  auto& spec=shards[si];auto&mapping=*mappings[si];bounded_jsonl::Range input(spec.at("operators").str(),spec.at("begin_byte").integer(),spec.at("end_byte").integer());std::string raw;Accumulator accumulator;accumulator.reserve(size_t(limit));
  while(!cancelled.load()){
   if(cap&&counts[si]>=cap)break;uint64_t start_byte;if(!input.next(raw,start_byte))break;offset=I(start_byte);
   if(counts[si]%1000==0){require(uptime()<deadline,"whole projection deadline");Json progress=Json::object();progress["operators"]=counts[si];progress["runs"]=runs[si];progress["byte_offset"]=offset;std::ofstream status(output/("shard_"+std::to_string(si)+".status.json"));status<<progress.dump()<<'\n';require(bool(status),"projection status write");}
   auto op=Json::parse(raw);I a=op.at(1).integer(),b=op.at(2).integer();require(a>=0&&b>=0&&a<I(mapping.size())&&b<I(mapping.size()),"operator local fields");a=mapping[a];b=mapping[b];require(geometry.physical(a)&&geometry.physical(b),"physical global operator fields required");counts[si]++;
   if(zero_measure(op)){zeros[si]++;continue;}
   std::array<I,4> support;for(int d=0;d<4;d++)support[d]=op.at(4).at(d).integer();P shift{Q(long(support[0])),Q(long(support[1]))};LocalRuntimeNodes nodes;
   auto source=geometry.resolve(a,support,shift,nodes);auto target_support=support;std::string kind=op.at(0).str();if(kind!="A")for(int d=0;d<4;d++)target_support[d]=op.at(5).at(d).integer();auto target=geometry.resolve(b,target_support,shift,nodes);auto rectangle=box(op.at(4),shift);
   Cached computed;const Cached* value=nullptr;std::string key;
   if(cache_limit){key=cache_key(source,target,op,rectangle,shift,.25L);auto found=local_cache.entries.find(key);if(found!=local_cache.entries.end()){value=&found->second;++cache_hits;}}
   if(!value){++cache_misses;if(kind=="A")computed.exact=area(source,target,rectangle,Q(op.at(5).num()));else if(kind=="L")computed.exact=line(source,target,edge(rectangle),edge(box(op.at(5),shift)),Q(op.at(6).num()));else computed.floating=fringe(source,target,edge(rectangle),box(op.at(5),shift),int(op.at(6).integer()),Q(op.at(7).num()),Q(op.at(8).num()),.25L);
    value=&computed;if(cache_limit){computed.estimate=cache_estimate(key,computed);if(computed.estimate<=size_t(cache_limit)){if(local_cache.used+computed.estimate>size_t(cache_limit)){local_cache.entries.clear();local_cache.used=0;++cache_clears;}local_cache.used+=computed.estimate;auto inserted=local_cache.entries.emplace(std::move(key),std::move(computed));require(inserted.second,"new cache entry");value=&inserted.first->second;}}}
   auto add=[&](int i,int j,LD coefficient){if(coefficient==0)return;uint64_t row=nodes.global.at(size_t(i)),col=nodes.global.at(size_t(j));if(row>col)return;accumulator[(row<<32)|col].add(coefficient);};
   for(auto&[ij,v]:value->exact){auto reverse=value->exact.find({ij.second,ij.first});require(reverse!=value->exact.end()&&reverse->second==v,"exact operator matrix symmetry");add(ij.first,ij.second,ld(v));}
   for(auto&[ij,v]:value->floating){auto reverse=value->floating.find({ij.second,ij.first});require(reverse!=value->floating.end()&&reverse->second==v,"fringe operator matrix symmetry");add(ij.first,ij.second,v);}
   if(I(accumulator.size())>=limit){flush(accumulator,output,si,runs[si]++);}
  }if(!accumulator.empty())flush(accumulator,output,si,runs[si]++);
 }catch(...){cancelled=true;errors[si]=std::current_exception();std::ofstream failure(output/("shard_"+std::to_string(si)+".failure.json"));Json r=Json::object();r["byte_offset"]=offset;r["operators"]=counts[si];r["release_qualified"]=false;failure<<r.dump()<<'\n';}}
 for(auto& error:errors)if(error)std::rethrow_exception(error);I total=0,nzero=0,nruns=0;for(size_t i=0;i<shards.size();i++){total+=counts[i];nzero+=zeros[i];nruns+=runs[i];}
 if(!cap)require(total==cfg.at("expected_operators").integer(),"full native operator coverage");Json result=Json::object();result["operators"]=total;result["zero_measure_or_density_operators"]=nzero;result["sparse_runs"]=nruns;result["full_operator_coverage"]=cap==0;result["global_voltage_nodes"]=I(geometry.node_count());result["elapsed_s"]=uptime()-start;result["cache_hits"]=cache_hits.load();result["cache_misses"]=cache_misses.load();result["cache_clears"]=cache_clears.load();result["threads"]=threads;result["byte_range_tasks"]=I(shards.size());result["distinct_shared_field_maps"]=I(shared_maps.size());result["disjoint_gap_free_byte_partitions_validated"]=true;result["physical_RC_qualified"]=false;result["release_qualified"]=false;std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
