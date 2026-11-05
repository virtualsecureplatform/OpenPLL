// Join C field triples to final R tile candidates using observed plane residues.
// This creates spatial-support references, not charge projection or a circuit.
#include "../charge_compiler/json.hpp"
#include <array>
#include <filesystem>
#include <iostream>
#include <set>
#include <unordered_map>
#include <omp.h>
#include <time.h>
using I=long long;using Key=std::array<std::string,3>;
struct Hash{size_t operator()(const Key& k)const{size_t h=0;for(auto&s:k)h^=std::hash<std::string>{}(s)+size_t(0x9e3779b9)+(h<<6)+(h>>2);return h;}};
struct Ref{I offset,row,serial,raw,effective;std::string group;};
struct Bundle{Key key;std::vector<Ref> refs;};
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static Json key_json(const Key& k){return Json::Array{k[0],k[1],k[2]};}
int main(int argc,char**argv){try{
 require(argc==2,"usage: map_charge_fields_to_R CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();
 I threads=cfg.at("threads").integer();require(threads>=1&&threads<=32,"thread bound");omp_set_dynamic(0);omp_set_num_threads(int(threads));
 auto meta=Json::read(cfg.at("metadata").str());std::map<std::pair<I,I>,I> residues;
 for(auto&r:meta.at("residues").arr()){auto key=std::pair{r.at(0).integer(),r.at(1).integer()};I value=r.at(2).integer();auto[it,added]=residues.emplace(key,value);require(added||it->second==value,"conflicting observed residue");}
 std::unordered_map<Key,I,Hash> lookup;std::vector<Bundle> bundles;std::set<std::string> conductors;
 std::ifstream in(cfg.at("catalog").str(),std::ios::binary);require(bool(in),"catalog open");std::string line;I rows=0;
 while(true){I offset=I(in.tellg());if(!std::getline(in,line))break;auto r=Json::parse(line);++rows;if(rows%10000==0)require(now()<deadline,"domain join deadline");
  auto conductor=r.at("original_conductor").str();I plane=r.at("native_working_plane_id").integer();auto raw_text=r.at("raw_type_id").str();I raw=std::stoll(raw_text);
  require(meta.at("types").at(raw_text).str()==r.at("raw_material").str(),"R/C raw type namespace differs");
  auto it=residues.find({plane,raw});I effective=it==residues.end()?raw:it->second;
  Key key{conductor,meta.at("planes").at(std::to_string(plane)).str(),meta.at("types").at(std::to_string(effective)).str()};
  auto[found,added]=lookup.emplace(key,I(bundles.size()));if(added)bundles.push_back(Bundle{key,{}});
  bundles[found->second].refs.push_back(Ref{offset,rows,r.at("tile_serial").integer(),raw,effective,r.at("native_group_id").str()});conductors.insert(conductor);
 }
 require(in.eof()&&!in.bad()&&rows>0,"complete catalog read");
 auto fields=Json::read(cfg.at("fields").str());require(!fields.arr().empty(),"nonempty fields");
 std::filesystem::path out=cfg.at("output").str();require(std::filesystem::create_directory(out),"fresh domain-map output");
 std::ofstream refs(out/"R_tile_bundles.jsonl"),output(out/"field_domains.jsonl");require(bool(refs)&&bool(output),"domain output streams");
 for(size_t i=0;i<bundles.size();++i){Json r=Json::object(),tiles=Json::array();r["bundle_id"]=I(i);r["field_key"]=key_json(bundles[i].key);
  for(auto&t:bundles[i].refs)tiles.push(Json::Array{t.offset,t.row,t.group,t.serial,t.raw,t.effective});
  r["tile_references"]=tiles;refs<<r.dump()<<'\n';require(bool(refs),"bundle write");}
 refs.close();require(bool(refs),"bundle close");
 const std::array<std::string,5> names{"explicit_reference","exact_native_R_tile_candidates","native_R_conductor_material_unmatched","no_native_R_snapshot_for_conductor","unlocated_native_field"};
 std::array<I,5> counts{};std::vector<bool> used(bundles.size());I matched_tiles=0;const I block=32768;
 for(I start=0;start<I(fields.arr().size());start+=block){
  require(now()<deadline,"field join deadline");I size=std::min(block,I(fields.arr().size())-start);
  std::vector<std::string> encoded(size),errors(size);std::vector<int> states(size);std::vector<I> selected(size,-1);
  #pragma omp parallel for schedule(static)
  for(I j=0;j<size;++j){try{
   I id=start+j;auto& field=fields.at(id);require(field.arr().size()==3,"field width");Key key{field.at(0).str(),field.at(1).str(),field.at(2).str()};int state;I bundle=-1;
   if(id==0){require(key==Key{"@SUBSTRATE_REFERENCE","reference","reference"},"explicit reference identity");state=0;}
   else if(key[1]=="arithmetic"&&key[2]=="unlocated")state=4;
   else if(auto it=lookup.find(key);it!=lookup.end()){state=1;bundle=it->second;}
   else state=conductors.count(key[0])?2:3;
   Json r=Json::object();r["field_id"]=id;r["field_key"]=key_json(key);r["support_state"]=names[state];
   if(bundle>=0){r["R_tile_bundle_id"]=bundle;r["candidate_tiles"]=I(bundles[bundle].refs.size());}
   r["spatial_projection_qualified"]=false;encoded[j]=r.dump();states[j]=state;selected[j]=bundle;
  }catch(const std::exception&e){errors[j]=e.what();}}
  for(I j=0;j<size;++j){require(errors[j].empty(),"parallel field join: "+errors[j]);++counts[states[j]];
   if(selected[j]>=0){I id=selected[j];require(!used[id],"duplicate global field identity matches same bundle");used[id]=true;matched_tiles+=I(bundles[id].refs.size());}
   output<<encoded[j]<<'\n';require(bool(output),"field domain write");}
 }
 output.close();require(bool(output),"field domain close");Json report=Json::object(),states=Json::object();
 for(size_t i=0;i<names.size();++i)states[names[i]]=counts[i];report["field_support_states"]=states;
 report["global_fields"]=I(fields.arr().size());report["native_R_tiles"]=rows;report["R_tile_bundles"]=I(bundles.size());report["matched_R_tile_candidates"]=matched_tiles;
 report["all_global_fields_accounted"]=true;report["all_R_tiles_referenced_once"]=true;
 for(auto flag:{"spatial_projection_qualified","full_C_energy_matrix_assembled","physical_RC_qualified","runtime_model_eligible","release_qualified"})report[flag]=false;
 std::ofstream summary(out/"summary.json");summary<<report.dump()<<'\n';require(bool(summary),"domain summary write");std::cout<<report.dump()<<'\n';
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
