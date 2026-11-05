// Independent first-encounter reconstruction of all local/global field IDs.
#include "json.hpp"
#include <array>
#include <filesystem>
#include <iostream>
#include <unordered_map>
#include <time.h>
using I=long long;using Field=std::array<std::string,3>;
struct Hash{size_t operator()(const Field& f)const{size_t h=0;for(auto& s:f)h^=std::hash<std::string>{}(s)+size_t(0x9e3779b9)+(h<<6)+(h>>2);return h;}};
static Field field(const Json& row){require(row.arr().size()==3,"field tuple width");return {row.at(0).str(),row.at(1).str(),row.at(2).str()};}
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==5,"usage: audit_field_maps COMPILED OUTPUT DEADLINE WORKERS");
 std::filesystem::path root=argv[1];double deadline=std::stod(argv[3]);I workers=std::stoll(argv[4]);
 require(workers>0&&workers<=64,"worker count");
 auto manifest=Json::read((root/"operators_manifest.json").string());
 require(I(manifest.at("shards").arr().size())==workers,"manifest shard count");
 auto rows=Json::read((root/"fields.json").string());std::vector<Field> global;global.reserve(rows.arr().size());
 for(auto& r:rows.arr())global.push_back(field(r));rows=Json();
 require(!global.empty()&&global[0]==Field{"@SUBSTRATE_REFERENCE","reference","reference"},"explicit substrate reference field");
 std::unordered_map<Field,I,Hash> reconstructed;reconstructed.reserve(global.size());I local_count=0;
 for(I i=0;i<workers;++i){
  require(now()<deadline,"field audit deadline");auto suffix="worker_"+std::to_string(i);
  auto local=Json::read((root/suffix/"fields.json").string());
  auto map_path=root/(suffix+"_field_map.json");auto mapping=Json::read(map_path.string());
  require(local.arr().size()==mapping.arr().size()&&!local.arr().empty(),"complete local field map");
  auto& shard=manifest.at("shards").at(i);
  require(std::filesystem::path(shard.at("field_map").str())==map_path,"manifest field-map path");
  require(std::filesystem::path(shard.at("operators").str())==root/suffix/"operators.jsonl","manifest operator path");
  for(size_t j=0;j<local.arr().size();++j){
   if(j%10000==0)require(now()<deadline,"field audit deadline");auto key=field(local.at(j));I actual=mapping.at(j).integer();
   auto[it,added]=reconstructed.emplace(key,I(reconstructed.size()));
   require(actual==it->second&&actual>=0&&actual<I(global.size()),"field ID differs from independent first encounter");
   require(global[actual]==key,"mapped global field identity differs");
   require(j!=0||actual==0,"local substrate reference differs");++local_count;
  }
 }
 require(reconstructed.size()==global.size(),"unused or duplicate global fields");
 Json report=Json::object();report["status"]="pass";report["shards"]=workers;
 report["global_fields"]=I(global.size());report["local_field_references_checked"]=local_count;
 report["all_field_maps_independently_reconstructed"]=true;
 report["explicit_substrate_reference_preserved"]=true;
 report["operator_payloads_checked"]=false;report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream out(argv[2]);out<<report.dump()<<'\n';require(bool(out),"field audit output");
 std::cout<<report.dump()<<'\n';
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
