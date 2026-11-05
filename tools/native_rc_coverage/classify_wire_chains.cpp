// Full snapshot-preserving axis-chain inventory; never a voltage-basis waiver.
#include "../charge_compiler/json.hpp"
#include <array>
#include <algorithm>
#include <filesystem>
#include <iostream>
#include <set>
#include <tuple>
#include <time.h>
using I=long long;using Box=std::array<I,4>;
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Segment{I lo,hi;std::string a,b,branch,resistance;bool split;I width,center;double value;};
using Key=std::tuple<I,std::string,std::string,Box,I>;
int main(int argc,char** argv){try{
 require(argc==2,"usage: classify_wire_chains CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(uptime()<deadline,"chain inventory deadline");};check();
 std::filesystem::path out=cfg.at("output").str();require(std::filesystem::create_directory(out),"fresh native output");std::ifstream input(cfg.at("wires").str());std::ofstream output(out/"chains.jsonl");require(bool(input)&&bool(output),"open chain streams");
 std::string group,label,line;std::map<Key,std::vector<Segment>> chains;I groups=0,chain_count=0,rows=0,emitted=0;std::map<std::string,I> states,reasons,materials;
 auto finish=[&](){if(group.empty())return;++groups;
  for(auto& [key,segments]:chains){check();auto& [plane,material,type,box,axis]=key;std::sort(segments.begin(),segments.end(),[](const Segment& a,const Segment& b){return std::tie(a.lo,a.hi,a.a,a.b,a.branch)<std::tie(b.lo,b.hi,b.a,b.b,b.branch);});std::set<std::string> why;bool zero=false;
   if(axis<0||axis>1)why.insert("unsupported_flow_axis");
   for(const auto& s:segments){if(s.split)why.insert("split_tile_requires_polygon_basis");if(s.lo>=s.hi)why.insert("nonincreasing_creation_axis");if(axis>=0&&axis<=1){if(s.lo<box[axis]||s.hi>box[axis+2])why.insert("creation_axis_outside_tile");if(s.width<=0||s.width!=box[3-axis]-box[1-axis]||s.center<box[1-axis]||s.center>box[3-axis])why.insert("wire_width_or_centerline_mismatch");}zero|=s.value==0;}
   for(size_t i=1;i<segments.size();++i){auto& a=segments[i-1];auto& b=segments[i];if(a.hi<b.lo)why.insert("axis_gap");if(a.hi>b.lo)why.insert("axis_overlap");if(a.hi==b.lo&&a.b!=b.a)why.insert("private_node_discontinuity");}
   I lower=0,upper=0;
   if(axis>=0&&axis<=1){lower=std::max(I(0),segments.front().lo-box[axis]);upper=std::max(I(0),box[axis+2]-segments.back().hi);if(lower||upper)why.insert("uncovered_tile_ends");}
   if(zero)why.insert("zero_resistance_requires_constraint_model");
   bool unsupported=why.count("unsupported_flow_axis")||why.count("split_tile_requires_polygon_basis")||why.count("nonincreasing_creation_axis")||why.count("creation_axis_outside_tile")||why.count("wire_width_or_centerline_mismatch");
   std::string state=unsupported?"unsupported_creation_geometry":(why.count("axis_gap")||why.count("axis_overlap")||why.count("private_node_discontinuity"))?"not_one_continuous_axis_chain":why.count("uncovered_tile_ends")?"uncovered_tile_ends":zero?"full_tile_chain_with_zero_R":"full_tile_chain_positive_R";
   ++states[state];++materials[material];for(const auto& reason:why)++reasons[reason];++chain_count;Json row=Json::object(),ss=Json::array(),ww=Json::array();
   for(const auto& s:segments){ss.push(Json::Array{s.lo,s.hi,s.a,s.b,s.resistance,s.branch});++emitted;}for(const auto& w:why)ww.push(w);
   row["native_group_id"]=group;row["original_conductor"]=label;row["native_working_plane_id"]=plane;row["raw_material"]=material;row["raw_type_id"]=type;row["tile_box_internal"]=Json::Array{box[0],box[1],box[2],box[3]};row["flow_axis"]=axis;row["segments"]=ss;row["state"]=state;row["reasons"]=ww;row["uncovered_axis_ends_internal"]=Json::Array{lower,upper};row["snapshot_selection_qualified"]=false;row["voltage_basis_qualified"]=false;output<<row.dump()<<'\n';require(bool(output),"chain write");
  }chains.clear();
 };
 while(std::getline(input,line)){
  if(++rows%10000==0)check();auto r=Json::parse(line);std::string gid=r.at("native_group_id").str(),name=r.at("original_conductor").str();
  if(group!=gid){if(!group.empty()){require(std::stoll(gid)>std::stoll(group),"group order");finish();}group=gid;label=name;}require(label==name,"group conductor changed");
  I axis=r.at("flow_axis").integer();Box box;for(int i=0;i<4;++i)box[i]=r.at("creation_tile_internal").at(i).integer();require(box[0]<box[2]&&box[1]<box[3],"positive tile box");auto& p=r.at("creation_points_internal");auto& ids=r.at("creation_private_ids");require(ids.arr().size()==2&&p.arr().size()==2,"endpoint width");int coordinate=axis==1?1:0;
  std::string a=ids.at(0).str(),b=ids.at(1).str();for(auto& id:{a,b})require(id.rfind("_rmesh_"+gid+"_",0)==0,"private node snapshot namespace");
  double value=r.at("native_resistance_value").num();require(value>=0,"nonnegative native resistance");chains[{r.at("native_working_plane_id").integer(),r.at("raw_material").str(),r.at("raw_type_id").str(),box,axis}].push_back({p.at(0).at(coordinate).integer(),p.at(1).at(coordinate).integer(),a,b,r.at("native_branch_pointer").str(),r.at("native_resistance_text").str(),r.at("split_tile").boolean(),r.at("width_internal").integer(),r.at("centerline_internal").integer(),value});
 }
 require(input.eof()&&!input.bad(),"wire input read");finish();require(rows>0&&rows==emitted,"every wire segment must be retained");output.close();require(bool(output),"chain close");Json result=Json::object(),st=Json::object(),rs=Json::object(),mt=Json::object();for(auto& [k,v]:states)st[k]=v;for(auto& [k,v]:reasons)rs[k]=v;for(auto& [k,v]:materials)mt[k]=v;
 result["wire_segments"]=rows;result["emitted_wire_segments"]=emitted;result["groups_with_wire_records"]=groups;result["tile_axis_chains"]=chain_count;result["chains_by_state"]=st;result["chains_by_reason"]=rs;result["chains_by_material"]=mt;result["all_wire_segments_preserved"]=true;result["native_snapshot_selection_qualified"]=false;result["complete_voltage_basis_qualified"]=false;result["contact_impedance_qualified"]=false;result["physical_domain_complete"]=false;result["runtime_model_eligible"]=false;result["release_qualified"]=false;check();std::ofstream summary(out/"summary.json");summary<<result.dump()<<'\n';summary.close();require(bool(summary),"summary close");return 0;
}catch(const std::exception& e){std::cerr<<"classify_wire_chains: "<<e.what()<<'\n';return 1;}}
