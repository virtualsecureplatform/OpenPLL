// Join every native tile to its axis reference or an anchored sheet descriptor.
// This catalog preserves snapshots and deferred cases; it does not qualify RC.
#include "../charge_compiler/json.hpp"
#include <algorithm>
#include <array>
#include <filesystem>
#include <iostream>
#include <set>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static std::string key(const Json& r,bool axis){
    Json k=Json::Array{r.at("native_group_id"),r.at("native_working_plane_id"),r.at("raw_type_id"),r.at("raw_material"),r.at(axis?"tile_box_internal":"box_internal")};return k.dump();
}
struct Axis{I row,offset;std::string state,label;std::set<std::string> nodes;bool prepared,numeric,used=false;};
int main(int argc,char** argv){try{
 require(argc==2,"usage: catalog_native_tiles CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"native tile catalog deadline");};check();
 std::map<std::string,Axis> axes;std::string line;I axis_rows=0;
 std::ifstream input(cfg.at("axes").str(),std::ios::binary);require(bool(input),"axis input open");
 while(true){I offset=I(input.tellg());if(!std::getline(input,line))break;auto r=Json::parse(line);Axis a{};a.row=++axis_rows;a.offset=offset;a.state=r.at("preparation_state").str();a.label=r.at("original_conductor").str();a.prepared=r.at("geometric_axis_prepared").boolean();a.numeric=r.at("numeric_end_resistors_complete").boolean();for(auto& k:r.at("native_voltage_knots").arr())a.nodes.insert(k.at(1).str());require(!r.at("runtime_model_eligible").boolean()&&!r.at("release_qualified").boolean(),"unqualified source axis required");require(axes.emplace(key(r,true),std::move(a)).second,"ambiguous axis tile identity: "+key(r,true));if(axis_rows%10000==0)check();}
 require(input.eof()&&!input.bad()&&axis_rows>0,"complete nonempty axis input");input.close();
 std::filesystem::path out=cfg.at("output").str();require(std::filesystem::create_directory(out),"fresh catalog output required");
 std::array<char,1048576> ib{},ob{};input.rdbuf()->pubsetbuf(ib.data(),ib.size());input.open(cfg.at("tiles").str(),std::ios::binary);std::ofstream output;output.rdbuf()->pubsetbuf(ob.data(),ob.size());output.open(out/"tile_catalog.jsonl");require(bool(input)&&bool(output),"tile catalog streams");
 I rows=0,axis_matches=0,single=0,prepared=0;std::map<std::string,I> counts;std::set<std::string> tile_ids;
 while(true){I offset=I(input.tellg());if(!std::getline(input,line))break;auto r=Json::parse(line);++rows;if(rows%10000==0)check();Json item=Json::object();item["source_tile_row"]=rows;item["source_tile_byte_offset"]=offset;
  for(const std::string f:{"native_group_id","tile_serial","native_working_plane_id","raw_type_id","raw_material","original_conductor","box_internal","split","private_voltage_nodes"})item[f]=r.at(f);
  auto id=Json(Json::Array{r.at("native_group_id"),r.at("tile_serial")}).dump();require(tile_ids.insert(id).second,"duplicate native tile serial: "+id);
  std::set<std::string> nodes;for(auto& v:r.at("private_voltage_nodes").arr())nodes.insert(v.str());require(!nodes.empty()&&nodes.size()==r.at("private_voltage_nodes").arr().size(),"unique nonempty native voltage identities");for(auto& n:nodes)require(n.rfind("_rmesh_"+r.at("native_group_id").str()+"_",0)==0,"cross-snapshot native node");
  std::string state;bool ready=false;
  if(nodes.size()>1){auto it=axes.find(key(r,false));require(it!=axes.end(),"multi-voltage tile lacks axis: "+key(r,false));auto& a=it->second;require(!a.used,"axis used by multiple native tiles");require(a.nodes==nodes&&a.label==r.at("original_conductor").str(),"axis/native tile voltage identity mismatch: "+key(r,false));a.used=true;++axis_matches;item["axis_registry_row"]=a.row;item["axis_registry_byte_offset"]=a.offset;item["axis_preparation_state"]=a.state;ready=a.prepared&&a.numeric;state=ready?"native_axis_candidate":"deferred_native_axis";
  }else{++single;auto& b=r.at("box_internal");I x0=b.at(0).integer(),y0=b.at(1).integer(),x1=b.at(2).integer(),y1=b.at(3).integer();bool inside=x0<x1&&y0<y1;std::map<std::pair<I,I>,std::string> anchors;std::set<I> xs{x0,x1},ys{y0,y1};for(auto& p:r.at("breakpoints").arr()){auto& point=p.at("point_internal");I x=point.at(0).integer(),y=point.at(1).integer();auto name=p.at("private_id").str();require(nodes.count(name),"breakpoint absent from sole native voltage");auto [it,ok]=anchors.emplace(std::make_pair(x,y),name);require(ok||it->second==name,"conflicting coincident anchors");inside&=x>=x0&&x<=x1&&y>=y0&&y<=y1;xs.insert(x);ys.insert(y);}require(!anchors.empty(),"single-voltage tile has no anchor");
   if(r.at("split").integer()!=0||x0>=x1||y0>=y1)state="deferred_anchor_shape";else if(!inside)state="deferred_outside_anchor";else if(!cfg.at("nominal_sheet_values").obj().count(r.at("raw_material").str()))state="deferred_anchor_material";
   else{state="anchored_sheet_candidate";ready=true;Json points=Json::array(),x=Json::array(),y=Json::array();for(auto& [p,n]:anchors)points.push(Json::Array{Json::Array{p.first,p.second},n});for(I v:xs)x.push(v);for(I v:ys)y.push(v);item["native_anchor_points"]=points;item["base_x_cuts_internal"]=x;item["base_y_cuts_internal"]=y;item["latent_node_namespace"]="_rmesh_sheet_"+r.at("native_group_id").str()+"_"+std::to_string(r.at("tile_serial").integer());item["nominal_sheet_milliohms_per_square"]=cfg.at("nominal_sheet_values").at(r.at("raw_material").str());item["mesh_family"]="Cartesian_P1_exact_anchor_cuts_LL_UR_diagonal";}
  }
  item["catalog_state"]=state;item["parameterized_basis_prepared"]=ready;for(const std::string flag:{"native_snapshot_selection_qualified","full_C_attachment_qualified","material_device_interface_qualified","resistance_PVT_qualified","physical_RC_qualified","runtime_model_eligible","release_qualified"})item[flag]=false;
  ++counts[state];prepared+=ready;output<<item.dump()<<'\n';require(bool(output),"catalog write");
 }
 require(input.eof()&&!input.bad()&&rows>0,"complete tile input");require(axis_matches==axis_rows,"unconsumed native axis records");for(auto& [k,a]:axes)require(a.used,"unconsumed native axis identity");output.close();require(bool(output),"catalog close");check();Json result=Json::object(),states=Json::object();for(auto& [s,n]:counts)states[s]=n;result["native_tiles"]=rows;result["axis_records_matched_once"]=axis_matches;result["single_voltage_tiles"]=single;result["parameterized_bases_prepared"]=prepared;result["catalog_state_counts"]=states;result["all_native_tiles_accounted"]=true;result["all_axis_records_consumed_once"]=true;for(const std::string f:{"native_snapshot_selection_qualified","full_C_attachment_qualified","material_device_interface_qualified","resistance_PVT_qualified","physical_RC_qualified","runtime_model_eligible","release_qualified"})result[f]=false;std::ofstream summary(out/"summary.json");summary<<result.dump()<<'\n';summary.close();require(bool(summary),"catalog summary write");return 0;
}catch(const std::exception& e){std::cerr<<"catalog_native_tiles: "<<e.what()<<'\n';return 1;}}
