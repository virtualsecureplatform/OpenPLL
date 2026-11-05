// Parameterized axis registry: native core references plus finite/symbolic ends.
// This stages geometry; it never selects a physical snapshot or qualifies RC.
#include "../charge_compiler/json.hpp"
#include <gmpxx.h>
#include <array>
#include <filesystem>
#include <iostream>
#include <set>
#include <time.h>
using I=long long;using Q=mpq_class;
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static Q qi(I n){return Q(std::to_string(n));}
static double native_number(const std::string& s){size_t used=0;double v=std::stod(s,&used);require(used==s.size()&&std::isfinite(v)&&v>=0,"nonnegative native R text");return v;}
static Json ratio(const Q& q){return Json::Array{q.get_num().get_str(),q.get_den().get_str()};}
int main(int argc,char** argv){try{
 require(argc==2,"usage: prepare_axis_registry CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(uptime()<deadline,"axis registry deadline");};check();
 std::filesystem::path out=cfg.at("output").str();require(std::filesystem::create_directory(out),"fresh output required");std::array<char,1048576> ib{},ob{};std::ifstream input;input.rdbuf()->pubsetbuf(ib.data(),ib.size());input.open(cfg.at("chains").str(),std::ios::binary);std::ofstream output;output.rdbuf()->pubsetbuf(ob.data(),ob.size());output.open(out/"axis_registry.jsonl");require(bool(input)&&bool(output),"open registry streams");
 std::map<std::string,Q> sheets;for(const auto& [k,v]:cfg.at("nominal_sheet_values").obj()){Q q(v.str());require(q>0,"positive nominal sheet value");sheets[k]=q;}
 I rows=0,segments=0,prepared=0,latent=0,numeric=0,symbolic=0;std::map<std::string,I> states;std::string line;
 while(true){I offset=I(input.tellg());if(!std::getline(input,line))break;if(++rows%10000==0)check();auto r=Json::parse(line);const auto& ss=r.at("segments").arr();require(!ss.empty(),"nonempty source chain");segments+=I(ss.size());I axis=r.at("flow_axis").integer();std::string source_state=r.at("state").str(),group=r.at("native_group_id").str(),material=r.at("raw_material").str();std::array<I,4> box{};for(int i=0;i<4;++i)box[i]=r.at("tile_box_internal").at(i).integer();
  Json row=Json::object();row["source_chain_row"]=rows;row["source_chain_byte_offset"]=offset;row["native_group_id"]=group;row["original_conductor"]=r.at("original_conductor");row["native_working_plane_id"]=r.at("native_working_plane_id");row["raw_material"]=material;row["raw_type_id"]=r.at("raw_type_id");row["tile_box_internal"]=r.at("tile_box_internal");row["flow_axis"]=axis;row["source_state"]=source_state;row["native_segments_referenced"]=I(ss.size());row["native_core_resistors_rewritten"]=false;
  bool geometric=(source_state=="full_tile_chain_positive_R"||source_state=="full_tile_chain_with_zero_R"||source_state=="uncovered_tile_ends")&&axis>=0&&axis<=1;bool zero=false,continuous=true;Json knots=Json::array();std::set<std::string> native_names;
  for(size_t i=0;i<ss.size();++i){auto& s=ss[i];require(s.arr().size()==6,"native segment width");I lo=s.at(0).integer(),hi=s.at(1).integer();std::string a=s.at(2).str(),b=s.at(3).str();for(auto& name:{a,b}){require(name.rfind("_rmesh_"+group+"_",0)==0,"native private-node snapshot namespace");native_names.insert(name);}zero|=native_number(s.at(4).str())==0;
   if(lo>=hi)geometric=false;if(i==0)knots.push(Json::Array{lo,a});else if(ss[i-1].at(1).integer()!=lo||ss[i-1].at(3).str()!=a)continuous=false;knots.push(Json::Array{hi,b});
  }
  if(geometric&&(knots.at(0).at(0).integer()<box[axis]||knots.at(knots.arr().size()-1).at(0).integer()>box[axis+2]||box[3-axis]<=box[1-axis]))geometric=false;
  row["native_voltage_knots"]=knots;bool ready=geometric&&continuous&&!zero;std::string state;Json ends=Json::array();bool complete=true;
  if(!geometric)state="deferred_creation_geometry";else if(!continuous)state="deferred_chain_topology";else if(zero)state="deferred_zero_R_constraint";
  else{
   auto values=knots.arr();std::string prefix="_rmesh_axis_end_"+group+"_"+std::to_string(rows);I width=box[3-axis]-box[1-axis];require(width>0,"positive strip width");
   auto make_end=[&](bool lower,I from,I to,const std::string& anchor){std::string name=prefix+(lower?"_lo":"_hi");require(!native_names.count(name)&&from<to,"fresh finite end state");Q squares=qi(to-from)/qi(width);Json e=Json::object();e["axis_interval_internal"]=Json::Array{from,to};e["endpoint_nodes"]=lower?Json(Json::Array{name,anchor}):Json(Json::Array{anchor,name});e["new_latent_node"]=name;e["resistance_squares_exact"]=ratio(squares);
    if(sheets.count(material)){e["nominal_resistance_milliohms_exact"]=ratio(sheets.at(material)*squares);++numeric;}else{e["requires_sheet_model_for_material"]=material;++symbolic;complete=false;}ends.push(e);++latent;return name;};
   I first=values.front().at(0).integer(),last=values.back().at(0).integer();if(first>box[axis]){auto name=make_end(true,box[axis],first,values.front().at(1).str());values.insert(values.begin(),Json::Array{box[axis],name});}if(last<box[axis+2]){auto name=make_end(false,last,box[axis+2],values.back().at(1).str());values.push_back(Json::Array{box[axis+2],name});}
   require(values.front().at(0).integer()==box[axis]&&values.back().at(0).integer()==box[axis+2],"complete candidate axis bounds");for(size_t i=1;i<values.size();++i)require(values[i-1].at(0).integer()<values[i].at(0).integer(),"increasing candidate knots");row["candidate_voltage_knots"]=values;++prepared;state=ends.arr().empty()?"native_full_axis_candidate":complete?"axis_with_nominal_finite_ends":"axis_with_symbolic_end_resistance";
  }
  row["end_stub_resistors"]=ends;row["geometric_axis_prepared"]=ready;row["numeric_end_resistors_complete"]=ready&&complete;row["preparation_state"]=state;row["native_snapshot_selection_qualified"]=false;row["material_device_interface_qualified"]=false;row["resistance_PVT_qualified"]=false;row["runtime_model_eligible"]=false;row["release_qualified"]=false;++states[state];output<<row.dump()<<'\n';require(bool(output),"registry write");
 }
 require(input.eof()&&!input.bad()&&rows>0,"registry input read");output.close();require(bool(output),"registry close");Json result=Json::object(),counts=Json::object();for(auto& [k,v]:states)counts[k]=v;result["source_chains"]=rows;result["native_segments_referenced"]=segments;result["geometric_axes_prepared"]=prepared;result["new_latent_end_states"]=latent;result["nominal_numeric_end_resistors"]=numeric;result["symbolic_end_resistors"]=symbolic;result["chains_by_preparation_state"]=counts;result["all_source_chains_accounted"]=true;result["native_core_resistors_rewritten"]=false;result["native_snapshot_selection_qualified"]=false;result["full_C_attachment_qualified"]=false;result["resistance_PVT_qualified"]=false;result["contact_impedance_qualified"]=false;result["physical_domain_complete"]=false;result["runtime_model_eligible"]=false;result["release_qualified"]=false;check();std::ofstream summary(out/"summary.json");summary<<result.dump()<<'\n';summary.close();require(bool(summary),"summary write");return 0;
}catch(const std::exception& e){std::cerr<<"prepare_axis_registry: "<<e.what()<<'\n';return 1;}}
