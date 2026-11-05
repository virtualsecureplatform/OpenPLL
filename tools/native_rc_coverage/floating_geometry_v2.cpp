// Retain native EXT geometry and area/perimeter classes for unmatched fields.
#include "../charge_compiler/json.hpp"
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <set>
#include <sstream>
#include <unordered_map>
#include <time.h>
using I=long long;namespace fs=std::filesystem;
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char** argv){try{
 require(argc==2,"usage: floating_geometry CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(uptime()<deadline,"geometry inventory deadline");};check();
 fs::path out=cfg.at("output").str();require(fs::create_directory(out),"fresh output required");
 struct Fields {std::vector<I> ids,physical_ids,arithmetic_ids;std::set<std::pair<std::string,std::string>> spatial;I arithmetic=0;bool found=false;};
 std::unordered_map<std::string,Fields> floating;I field_count=0;
 std::ifstream inventory(cfg.at("inventory").str());require(bool(inventory),"inventory open");std::string line;I records=0;
 while(std::getline(inventory,line)){
  if(++records%10000==0)check();auto r=Json::parse(line);if(r.at("EXT_inventory_state").str()!="declared_component_without_port_device_or_native_R")continue;
  const auto& f=r.at("field");auto& target=floating[f.at(0).str()];target.ids.push_back(r.at("field_id").integer());++field_count;
  I id=r.at("field_id").integer();
  if(f.at(1).str()=="arithmetic"){
   require(f.at(2).str()=="unlocated"&&id>=cfg.at("arithmetic_field_begin").integer()&&id<cfg.at("arithmetic_field_end").integer(),"arithmetic field role mismatch");
   ++target.arithmetic;target.arithmetic_ids.push_back(id);
  }else{
   require(id>=0&&id<cfg.at("arithmetic_field_begin").integer(),"physical field role mismatch");
   target.spatial.insert({f.at(1).str(),f.at(2).str()});target.physical_ids.push_back(id);
  }
 }
 require(inventory.eof()&&!inventory.bad(),"inventory read");
 std::ifstream ext(cfg.at("ext").str());require(bool(ext),"EXT open");std::vector<I> classes;I node_count=0,multi_class=0,multi_spatial=0,only_arithmetic=0;
 std::map<std::string,I> materials;std::map<std::string,std::ofstream> outputs;
 while(std::getline(ext,line)){
  if(++records%10000==0)check();if(line.rfind("resistclasses ",0)==0){require(classes.empty(),"duplicate resistance class table");std::istringstream in(line);std::string token;in>>token;I n;while(in>>n){require(n>=0,"negative sheet class");classes.push_back(n);}require(in.eof()&&!classes.empty(),"resistance class table");continue;}
  if(line.rfind("node ",0)!=0)continue;
  std::istringstream in(line);std::string kind,name;require(bool(in>>kind>>std::quoted(name)),"node name");auto it=floating.find(name);if(it==floating.end())continue;
  auto& fields=it->second;require(!fields.found,"duplicate floating node");fields.found=true;
  std::string resistance,capacitance,type;I x,y;require(bool(in>>resistance>>capacitance>>x>>y>>type),"floating node geometry");
  require(!type.empty()&&type.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_")==std::string::npos,"unsafe native material name");
  Json row=Json::object(),nonzero=Json::array(),ids=Json::array(),spatial=Json::array(),physical=Json::array(),arithmetic=Json::array();I count=0;
  for(size_t i=0;i<classes.size();++i){I area,perimeter;require(bool(in>>area>>perimeter)&&area>=0&&perimeter>=0,"node area/perimeter class");if(area||perimeter){Json c=Json::object();c["class_index"]=I(i);c["native_sheet_class_value"]=classes[i];c["area_internal_squared"]=area;c["perimeter_internal"]=perimeter;nonzero.push(c);++count;}}
  in>>std::ws;require(in.eof(),"unexpected floating node suffix");if(count!=1)++multi_class;if(fields.spatial.size()>1)++multi_spatial;if(fields.spatial.empty())++only_arithmetic;
  for(I id:fields.ids)ids.push(id);for(I id:fields.physical_ids)physical.push(id);for(I id:fields.arithmetic_ids)arithmetic.push(id);for(const auto& p:fields.spatial)spatial.push(Json::Array{p.first,p.second});
  row["original_conductor"]=name;row["point_internal"]=Json::Array{x,y};row["native_type"]=type;row["native_lumped_resistance_text"]=resistance;row["native_lumped_capacitance_text"]=capacitance;row["native_classes"]=nonzero;row["field_ids"]=ids;row["physical_field_ids"]=physical;row["arithmetic_bookkeeping_field_ids"]=arithmetic;row["spatial_field_keys"]=spatial;row["unlocated_arithmetic_fields"]=fields.arithmetic;
  if(!outputs.count(type)){outputs[type].open(out/("nodes_"+type+".jsonl"));require(bool(outputs[type]),"partition output open");}
  outputs[type]<<row.dump()<<'\n';require(bool(outputs[type]),"partition write");++materials[type];++node_count;
 }
 require(ext.eof()&&!ext.bad(),"EXT read");require(size_t(node_count)==floating.size(),"unmatched field conductor missing EXT node");for(auto& [type,f]:outputs){f.close();require(bool(f),"partition close");}
 Json result=Json::object(),m=Json::object();for(auto& [k,v]:materials)m[k]=v;result["unmatched_fields"]=field_count;result["unique_native_conductors"]=node_count;result["native_types"]=m;result["nodes_without_exactly_one_nonzero_resistance_class"]=multi_class;result["nodes_with_multiple_spatial_field_keys"]=multi_spatial;result["nodes_with_only_unlocated_arithmetic_fields"]=only_arithmetic;result["physical_geometry_correspondence_qualified"]=false;result["finite_R_basis_qualified"]=false;result["release_qualified"]=false;
 result["scope"]="native EXT declaration inventory only; GDS geometry, units, sheet resistance and finite-R attachment remain unqualified";check();std::ofstream summary(out/"summary.json");summary<<result.dump()<<'\n';summary.close();require(bool(summary),"summary write");return 0;
}catch(const std::exception& e){std::cerr<<"floating_geometry: "<<e.what()<<'\n';return 1;}}
