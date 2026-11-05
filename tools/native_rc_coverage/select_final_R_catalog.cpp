// Partition an audited catalog by proven final-export membership; copy rows
// verbatim so all original geometry, private IDs, offsets and flags survive.
#include "../charge_compiler/json.hpp"
#include <array>
#include <filesystem>
#include <iostream>
#include <map>
#include <time.h>
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==2,"usage: select_final_R_catalog CONFIG");auto cfg=Json::read(argv[1]);
 double deadline=cfg.at("deadline_uptime").num();auto selection=Json::read(cfg.at("selection").str());
 require(selection.at("status").str()=="pass"&&selection.at("final_res_ext_node_and_resistor_multisets_match").boolean(),"unverified snapshot selection");
 long long prefix=selection.at("obsolete_prefix_groups").num();std::map<std::string,std::string> chosen;
 for(auto& r:selection.at("selected_groups").arr()){
  long long id=r.at("group").num();require(id>prefix&&double(id)==r.at("group").num(),"invalid selected group");
  require(chosen.emplace(std::to_string(id),r.at("original").str()).second,"duplicate selected group");
 }
 require(!chosen.empty()&&double(chosen.size())==selection.at("selected_group_count").num(),"selected group count");
 std::filesystem::path out=cfg.at("output").str();require(std::filesystem::create_directory(out),"fresh output directory required");
 std::array<char,1048576> ib{},sb{},ob{};std::ifstream input;input.rdbuf()->pubsetbuf(ib.data(),ib.size());input.open(cfg.at("catalog").str(),std::ios::binary);
 std::ofstream selected,superseded;selected.rdbuf()->pubsetbuf(sb.data(),sb.size());superseded.rdbuf()->pubsetbuf(ob.data(),ob.size());
 selected.open(out/"tile_catalog.jsonl",std::ios::binary);superseded.open(out/"superseded_tile_catalog.jsonl",std::ios::binary);
 require(bool(input)&&bool(selected)&&bool(superseded),"catalog streams");
 std::string line;long long rows=0,kept=0,removed=0;std::map<std::string,long long> states,old_states;std::map<std::string,bool> seen;
 while(std::getline(input,line)){
  require(now()<deadline,"catalog selection deadline");auto r=Json::parse(line);++rows;
  auto group=r.at("native_group_id").str();auto state=r.at("catalog_state").str();auto match=chosen.find(group);
  for(auto flag:{"physical_RC_qualified","runtime_model_eligible","release_qualified"})require(!r.at(flag).boolean(),"source catalog has unexpected qualification");
  if(match!=chosen.end()){
   require(match->second==r.at("original_conductor").str(),"selected conductor identity mismatch");
   for(auto& n:r.at("private_voltage_nodes").arr())require(n.str().rfind("_rmesh_"+group+"_",0)==0,"cross-snapshot voltage");
   selected<<line<<'\n';++kept;++states[state];seen[group]=true;
  }else{
   size_t end=0;auto id=std::stoll(group,&end);require(end==group.size()&&id>=1&&id<=prefix,"catalog group absent from selection and superseded prefix");
   superseded<<line<<'\n';++removed;++old_states[state];
  }
  require(bool(selected)&&bool(superseded),"catalog output write");
 }
 require(input.eof()&&!input.bad()&&rows==kept+removed&&kept>0,"complete catalog partition");
 selected.close();superseded.close();require(bool(selected)&&bool(superseded),"catalog close");
 Json result=Json::object(),a=Json::object(),b=Json::object();for(auto&[k,v]:states)a[k]=v;for(auto&[k,v]:old_states)b[k]=v;
 result["source_rows"]=rows;result["selected_rows"]=kept;result["superseded_rows"]=removed;
 result["selected_groups_with_tiles"]=static_cast<long long>(seen.size());result["selected_catalog_state_counts"]=a;result["superseded_catalog_state_counts"]=b;
 result["original_rows_copied_verbatim"]=true;result["native_final_R_export_membership_applied"]=true;
 for(auto flag:{"full_C_attachment_qualified","physical_RC_qualified","runtime_model_eligible","release_qualified"})result[flag]=false;
 std::ofstream summary(out/"summary.json");summary<<result.dump()<<'\n';require(bool(summary),"summary write");
 std::cout<<"selected "<<kept<<", retained superseded "<<removed<<" of "<<rows<<" tile rows\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
