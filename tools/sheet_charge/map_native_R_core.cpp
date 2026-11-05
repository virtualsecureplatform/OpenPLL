// Join final native R snapshot identities to the immutable spatial voltage map.
#include "../charge_compiler/json.hpp"
#include <bit>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <unordered_map>
#include <unordered_set>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Node{std::string private_id,name,conductor;I x=0,y=0,global=-1;};
struct Edge{std::string a,b,value;unsigned type=0;int status=0;};
int main(int argc,char**argv){try{
 require(argc==2,"usage: map_native_R_core CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();
 std::unordered_map<std::string,std::string> groups;auto selected=Json::read(cfg.at("selected_groups").str());for(auto& row:selected.at("selected_groups").arr())require(groups.emplace(std::to_string(row.at("group").integer()),row.at("original").str()).second,"unique selected R group");selected=Json();
 std::unordered_map<std::string,I> global;std::ifstream runtime(cfg.at("R_nodes").str());require(bool(runtime),"spatial R node input");std::string line;I prior=0;while(std::getline(runtime,line)){require(now()<deadline,"R voltage map deadline");auto row=Json::parse(line);I id=row.at(0).integer();require(id==prior+1&&global.emplace(row.at(1).str(),id).second,"unique contiguous spatial R IDs");prior=id;}require(runtime.eof(),"complete spatial R map");
 std::unordered_map<std::string,Node> index;auto raw=Json::read(cfg.at("nodes").str());for(auto& row:raw.arr()){auto g=row.at("native_group_id").str();auto group=groups.find(g);if(group==groups.end())continue;Node n;n.private_id=row.at("private_id").str();n.name=row.at("printed_name").str();n.conductor=row.at("original_conductor").str();require(n.conductor==group->second,"R index conductor identity");n.x=row.at("point_internal").at(0).integer();n.y=row.at("point_internal").at(1).integer();auto found=global.find(n.private_id);if(found!=global.end())n.global=found->second;require(index.emplace(g+":"+row.at("native_pointer").str(),n).second,"unique native R pointer within snapshot");}raw=Json();
 std::ifstream provenance(cfg.at("provenance").str());require(bool(provenance),"native R provenance input");std::ofstream node_output(cfg.at("node_output").str()),edge_output(cfg.at("edge_output").str());require(bool(node_output)&&bool(edge_output),"native core map outputs");
 std::unordered_map<std::string,Node> nodes;std::unordered_map<std::string,Edge> edges;std::unordered_set<std::string> completed;std::string group,original,pending;bool active=false,keep=false;I total_nodes=0,total_edges=0,positive=0,zero=0,unmapped_nodes=0,unmapped_edges=0,self=0;
 while(std::getline(provenance,line)){require(now()<deadline,"native R core mapping deadline");std::istringstream s(line);std::string kind;s>>kind;if(kind=="TYPE")continue;
  if(kind=="BEGIN"){require(!active,"non-nested native snapshot");s>>group>>std::quoted(original);require(bool(s),"native snapshot header");active=true;keep=groups.count(group);if(keep)require(groups.at(group)==original,"selected native original conductor");nodes.clear();edges.clear();pending.clear();continue;}
  std::string g;s>>g;require(bool(s)&&active&&g==group,"native snapshot record identity");
  if(kind=="END"){require(pending.empty(),"complete native branch pair");if(keep){require(completed.insert(group).second,"selected snapshot only once");for(auto&[pointer,n]:nodes){Json r=Json::object();r["native_group_id"]=group;r["native_pointer"]=pointer;r["private_id"]=n.private_id;r["printed_name"]=n.name;r["original_conductor"]=n.conductor;r["point_internal"]=Json::Array{n.x,n.y};r["global_voltage_id"]=n.global;r["basis_binding_state"]=n.global<0?"requires_R_only_voltage_union":"exact_existing_spatial_voltage";node_output<<r.dump()<<'\n';total_nodes++;unmapped_nodes+=n.global<0;}
    for(auto&[branch,e]:edges){require(nodes.count(e.a)&&nodes.count(e.b),"R core endpoint exists in selected snapshot");auto&a=nodes.at(e.a);auto&b=nodes.at(e.b);size_t used=0;float value=std::stof(e.value,&used);require(used==e.value.size()&&std::isfinite(value)&&value>=0,"finite nonnegative native float R");float ohms=value/1000.0F;char printed[128];std::snprintf(printed,sizeof printed,"%g",double(ohms));Json r=Json::object();r["native_group_id"]=group;r["native_branch_pointer"]=branch;r["original_conductor"]=original;r["private_endpoints"]=Json::Array{a.private_id,b.private_id};r["global_voltage_ids"]=Json::Array{a.global,b.global};r["native_resistance_milliohm_token"]=e.value;r["native_resistance_float_bits"]=I(std::bit_cast<uint32_t>(value));r["printed_native_resistance_ohm_token"]=std::string(printed);r["raw_type_id"]=I(e.type);r["native_status"]=e.status;r["branch_kind"]=value==0?"exact_zero_voltage_constraint":"positive_native_resistor";if(value>0){r["nominal_conductance_siemens"]=1000.0/double(value);positive++;}else zero++;r["native_resistor_rewritten"]=false;edge_output<<r.dump()<<'\n';total_edges++;unmapped_edges+=a.global<0||b.global<0;self+=a.private_id==b.private_id;}
   }active=false;continue;}
  if(!keep)continue;
  if(kind=="NODE"){std::string pointer,name;I x,y;s>>pointer>>std::quoted(name)>>x>>y;require(bool(s),"native core node record");auto found=index.find(group+":"+pointer);require(found!=index.end(),"native snapshot pointer absent from corrected index");auto n=found->second;require(n.name==name&&n.x==x&&n.y==y,"native core node name/coordinate identity");require(nodes.emplace(pointer,n).second,"unique native snapshot node");}
  else if(kind=="BRANCH"){std::string owner;s>>owner>>pending;require(bool(s)&&!pending.empty(),"native branch record");}
  else if(kind=="EDGE"){std::string owner;Edge e;s>>owner>>e.a>>e.b>>e.value>>e.type>>e.status;require(bool(s)&&!pending.empty(),"native edge record");auto[it,added]=edges.emplace(pending,e);require(added||(it->second.a==e.a&&it->second.b==e.b&&it->second.value==e.value&&it->second.type==e.type),"stable native branch payload");pending.clear();}
  else throw std::runtime_error("unknown native provenance record");
 }
 require(provenance.eof()&&!active&&completed.size()==groups.size(),"complete final native core snapshot coverage");node_output.close();edge_output.close();require(bool(node_output)&&bool(edge_output),"native core outputs closed");Json report=Json::object();report["selected_native_groups"]=I(completed.size());report["native_core_nodes"]=total_nodes;report["native_core_branches"]=total_edges;report["positive_native_resistors"]=positive;report["exact_zero_voltage_branches"]=zero;report["self_branches"]=self;report["nodes_requiring_R_only_voltage_union"]=unmapped_nodes;report["branches_requiring_R_only_voltage_union"]=unmapped_edges;report["native_resistors_rewritten"]=false;report["physical_RC_qualified"]=false;report["release_qualified"]=false;std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
