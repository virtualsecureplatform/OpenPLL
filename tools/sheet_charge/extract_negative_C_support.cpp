// Resolve target P1 basis support by scanning every pinned R triangle.
#include "../charge_compiler/json.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <memory>
#include <omp.h>
#include <set>
#include <unordered_map>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static uint64_t le(const char*p){uint64_t n=0;for(int k=0;k<8;k++)n|=uint64_t(static_cast<unsigned char>(p[k]))<<(8*k);return n;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);const auto&geometry=cfg.at("geometry");
 double deadline=cfg.at("deadline_uptime").num();I threads=cfg.at("threads").integer();require(threads>0&&threads<=8,"support thread bound");
 auto target=Json::read(cfg.at("targets").str());
 struct Target{I row,node;std::set<I>fields;};std::map<std::string,Target>requested;
 for(const auto&r:target.at("negative_nodes").arr())for(const auto&n:r.at("original_voltage_nodes").arr()){
  Target item{r.at("row").integer(),n.at("node").integer(),{}};
  for(const auto&f:n.at("candidate_global_fields").arr())item.fields.insert(f.integer());
  require(item.row>0&&item.node>0&&!item.fields.empty()&&requested.emplace(n.at("name").str(),item).second,"unique positive target identities");
 }
 require(!requested.empty()&&requested.size()<=100000,"bounded support targets");
 uint64_t fields=geometry.at("global_fields").integer();require(fields>0&&fields<=10000000,"bounded field index");
 std::ifstream index(geometry.at("R_index").str(),std::ios::binary);char header[16];index.read(header,16);
 require(bool(index)&&std::string(header,8)=="RBSIDX01"&&le(header+8)==fields,"support R index header");
 std::unordered_map<uint32_t,I>bundle_field;
 for(uint64_t field=0;field<fields;field++){
  char entry[16];index.read(entry,16);require(bool(index),"complete R index");if(le(entry)==UINT64_MAX)continue;
  uint32_t bundle;std::memcpy(&bundle,entry+12,4);
  require(field>0&&bundle_field.emplace(bundle,I(field)).second,"one field per R bundle");
 }
 char extra;require(!index.get(extra)&&index.eof(),"R index trailing bytes");
 struct Tile{I field;size_t slot;};std::unordered_map<I,Tile>tile_fields;
 std::ifstream bundles(geometry.at("R_bundles").str());require(bool(bundles),"support bundles input");std::string raw;uint64_t nb=0;
 while(std::getline(bundles,raw)){
  require(now()<deadline,"support bundle deadline");auto row=Json::parse(raw);auto id=row.at("bundle_id").integer();
  require(id==I(nb++)&&id>=0&&bundle_field.contains(uint32_t(id)),"ordered support bundles");
  for(const auto&ref:row.at("tile_references").arr()){
   auto serial=ref.at(3).integer();require(serial>0,"positive tile serial");
   require(tile_fields.emplace(serial,Tile{bundle_field.at(uint32_t(id)),tile_fields.size()}).second,"one R field per support tile");
  }
 }
 require(bundles.eof()&&!bundles.bad()&&nb==bundle_field.size(),"complete support bundles");
 require(tile_fields.size()==uint64_t(geometry.at("expected_R_tiles").integer()),"support tile reference count");
 auto seen=std::make_unique<std::atomic<uint8_t>[]>(tile_fields.size());for(size_t k=0;k<tile_fields.size();k++)seen[k]=0;
 const auto&parts=geometry.at("R_parts").arr();require(!parts.empty()&&parts.size()<=32,"bounded support partitions");
 std::vector<Json::Array>found(parts.size());std::vector<uint64_t>counts(parts.size());std::vector<std::exception_ptr>errors(parts.size());
 #pragma omp parallel for num_threads(threads) schedule(dynamic,1)
 for(I part=0;part<I(parts.size());part++){try{
  std::ifstream input(parts[part].str());require(bool(input),"support R partition open");std::string line;
  while(std::getline(input,line)){
   if(counts[part]++%1000==0)require(now()<deadline,"support triangle scan deadline");auto row=Json::parse(line);
   I serial=row.at("tile_serial").integer();auto f=tile_fields.find(serial);require(f!=tile_fields.end()&&seen[f->second.slot].exchange(1)==0,"unique complete runtime support tiles");
   const auto&names=row.at("point_nodes").arr();const auto&points=row.at("points").arr();require(names.size()==points.size(),"support point identities");
   std::map<size_t,const Target*>active;for(size_t k=0;k<names.size();k++){
    auto n=requested.find(names[k].str());if(n!=requested.end()){
     require(n->second.fields.contains(f->second.field),"selected basis support within field overapproximation");active.emplace(k,&n->second);
    }
   }
   if(active.empty())continue;size_t triangle=0;
   for(const auto&tri:row.at("triangles").arr()){
    require(tri.arr().size()==3,"support triangle width");Json ids=Json::array(),coordinates=Json::array(),affected=Json::array(),rows=Json::array();
    std::array<I,3>xs,ys;bool touches=false;
    for(int k=0;k<3;k++){
     I vertex=tri.at(k).integer();require(vertex>=0&&vertex<I(points.size()),"support triangle point bounds");
     xs[k]=points[vertex].at(0).integer();ys[k]=points[vertex].at(1).integer();coordinates.push(points[vertex]);ids.push(names[vertex]);
     auto n=active.find(size_t(vertex));if(n!=active.end()){touches=true;affected.push(names[vertex]);rows.push(n->second->row);}
    }
    if(touches){
     __int128 area=(__int128(xs[1])-xs[0])*(ys[2]-ys[0])-(__int128(ys[1])-ys[0])*(xs[2]-xs[0]);require(area>0,"positive selected P1 triangle");
     Json item=Json::object();item["tile_serial"]=serial;item["triangle_index"]=I(triangle);item["global_field"]=f->second.field;
     item["points"]=coordinates;item["point_nodes"]=ids;item["affected_names"]=affected;item["affected_constrained_rows"]=rows;
     item["box"]=Json::Array{*std::min_element(xs.begin(),xs.end()),*std::min_element(ys.begin(),ys.end()),*std::max_element(xs.begin(),xs.end()),*std::max_element(ys.begin(),ys.end())};
     found[part].push_back(item);
    }triangle++;
   }
  }require(input.eof()&&!input.bad(),"complete support partition scan");
 }catch(...){errors[part]=std::current_exception();}}
 for(const auto&e:errors)if(e)std::rethrow_exception(e);uint64_t total=0;for(auto n:counts)total+=n;
 require(total==tile_fields.size(),"every referenced R tile scanned");for(size_t k=0;k<tile_fields.size();k++)require(seen[k]==1,"no support tile omitted");
 std::map<std::string,I>incidence;for(const auto&[name,t]:requested)incidence[name]=0;
 std::ofstream triangles(cfg.at("triangles").str());require(bool(triangles),"support output open");uint64_t selected=0;
 for(const auto&part:found)for(const auto&tri:part){triangles<<tri.dump()<<'\n';selected++;for(const auto&n:tri.at("affected_names").arr())incidence.at(n.str())++;}
 triangles.close();require(bool(triangles),"support output close");Json nodes=Json::array();
 for(const auto&[name,count]:incidence){require(count>0,"every target has full nonempty P1 support");Json n=Json::object();n["name"]=name;n["support_triangles"]=count;nodes.push(n);}
 Json report=Json::object();report["all_R_tiles_scanned"]=I(total);report["selected_support_triangles"]=I(selected);report["target_nodes"]=I(incidence.size());
 report["node_support_incidence"]=nodes;report["all_target_P1_support_triangles_resolved"]=true;report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream out(cfg.at("report").str());out<<report.dump()<<'\n';out.close();require(bool(out),"support report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
