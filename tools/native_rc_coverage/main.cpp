// Inventory only: exact conductor labels and raw plane/material identities.
// No lifetime selection, ideal-conductor collapse, node mapping or qualification.
#include "../charge_compiler/json.hpp"
#include <array>
#include <filesystem>
#include <set>
#include <time.h>
#include <iostream>
using I=long long;namespace fs=std::filesystem;
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char** argv){try{
 require(argc==2,"usage: native_rc_coverage CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();
 auto check=[&](){require(uptime()<deadline,"coverage deadline");};check();
 fs::path out=cfg.at("output").str();require(fs::create_directory(out),"fresh native output required");
 std::map<std::string,std::set<std::string>> groups;
 std::map<std::string,std::set<std::array<std::string,2>>> signatures;
 std::set<std::string> group_ids;I group_rows=0,tile_rows=0;
 auto lines=[&](const std::string& path,auto consume){std::ifstream f(path);require(bool(f),"input open");std::string line;I n=0;while(std::getline(f,line)){if(++n%10000==0)check();require(!line.empty(),"empty JSON line");consume(Json::parse(line));}require(f.eof()&&!f.bad(),"input read");};
 lines(cfg.at("groups").str(),[&](const Json& r){auto id=r.at("native_group_id").str();require(group_ids.insert(id).second,"duplicate native snapshot");groups[r.at("original_conductor").str()].insert(id);++group_rows;});
 lines(cfg.at("tiles").str(),[&](const Json& r){auto label=r.at("original_conductor").str(),id=r.at("native_group_id").str();require(groups.count(label)&&groups.at(label).count(id),"tile snapshot absent from native group inventory");signatures[label].insert({r.at("native_working_plane").str(),r.at("raw_material").str()});++tile_rows;});
 check();auto fields=Json::read(cfg.at("fields").str());I n=0;std::set<std::array<std::string,3>> seen;
 std::map<std::string,I> counts;std::map<std::array<std::string,3>,I> breakdown;
 std::ofstream rows(out/"fields.jsonl");require(bool(rows),"field inventory output");
 for(const auto& f:fields.arr()){
  if(n%10000==0)check();require(f.arr().size()==3,"field key width");std::array<std::string,3> key{f.at(0).str(),f.at(1).str(),f.at(2).str()};require(seen.insert(key).second,"duplicate capacitance field");
  std::string state;I snapshots=0;bool exact=false;
  if(key[0]=="@SUBSTRATE_REFERENCE"){require(n==0&&key[1]=="reference"&&key[2]=="reference","invalid substrate reference");state="explicit_reference";}
  else if(!groups.count(key[0]))state="no_exact_native_conductor_label";
  else {snapshots=I(groups.at(key[0]).size());state=snapshots==1?"one_native_snapshot":"multiple_native_snapshots";auto it=signatures.find(key[0]);exact=it!=signatures.end()&&it->second.count({key[1],key[2]});}
  ++counts[state];++breakdown[{state,key[1],key[2]}];if(exact)++counts["raw_plane_material_signature_present"];
  Json row=Json::object();row["field_id"]=n++;row["field"]=f;row["conductor_inventory_state"]=state;row["native_snapshot_count"]=snapshots;row["raw_plane_material_signature_present"]=exact;rows<<row.dump()<<'\n';require(bool(rows),"inventory write");
 }
 require(n>0&&counts["explicit_reference"]==1,"missing reference");rows.close();require(bool(rows),"inventory close");
 Json result=Json::object(),c=Json::object(),b=Json::array();for(const auto& [k,v]:counts)c[k]=v;
 for(const auto& [key,v]:breakdown){Json r=Json::object();r["state"]=key[0];r["capacitance_plane"]=key[1];r["capacitance_material"]=key[2];r["fields"]=v;b.push(r);}
 result["fields"]=n;result["native_snapshots"]=group_rows;result["native_conductor_labels"]=I(groups.size());result["native_tiles"]=tile_rows;result["counts"]=c;result["by_state_plane_material"]=b;result["physical_domain_complete"]=false;result["runtime_model_eligible"]=false;result["release_qualified"]=false;
 result["scope"]="exact-label/raw-signature inventory across all snapshots; no electrical ownership, spatial coverage, lifetime, reference, alias, finite-R basis or passivity qualification";
 check();std::ofstream summary(out/"summary.json");summary<<result.dump()<<'\n';summary.close();require(bool(summary),"summary write");return 0;
}catch(const std::exception& e){std::cerr<<"native_rc_coverage: "<<e.what()<<'\n';return 1;}}
