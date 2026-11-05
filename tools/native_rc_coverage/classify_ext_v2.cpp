// Exact EXT declaration and explicit-equivalence inventory, not an RC model.
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
 require(argc==2,"usage: classify_ext CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(uptime()<deadline,"deadline");};check();
 fs::path out=cfg.at("output").str();require(fs::create_directory(out),"fresh output required");
 struct Node {size_t parent;bool declared=false,port=false,device=false,native=false;};
 std::vector<Node> nodes;std::unordered_map<std::string,size_t> ids;
 auto intern=[&](const std::string& name){auto [it,added]=ids.emplace(name,nodes.size());if(added)nodes.push_back(Node{nodes.size()});return it->second;};
 auto root=[&](size_t a){while(nodes[a].parent!=a){nodes[a].parent=nodes[nodes[a].parent].parent;a=nodes[a].parent;}return a;};
 auto join=[&](size_t a,size_t b){a=root(a);b=root(b);if(a!=b)nodes[b].parent=a;};
 std::map<std::string,I> records;std::string line;I lines=0,aliases=0;
 std::ifstream ext(cfg.at("ext").str());require(bool(ext),"EXT open");
 while(std::getline(ext,line)){
  if(++lines%10000==0)check();size_t at=line.find_first_of(" \t");std::string kind=line.substr(0,at);++records[kind];
  if(kind!="node"&&kind!="port"&&kind!="device"&&kind!="equiv")continue;
  std::istringstream input(line);std::string token;input>>token;
  if(kind=="node"||kind=="port"){
   require(bool(input>>std::quoted(token)),"EXT node/port name");auto id=intern(token);
   if(kind=="node"){require(!nodes[id].declared,"duplicate EXT node declaration");nodes[id].declared=true;}
   else nodes[id].port=true;
  }else if(kind=="equiv"){
   std::string a,b;require(bool(input>>std::quoted(a)>>std::quoted(b)),"EXT equivalence");input>>std::ws;require(input.eof(),"EXT equivalence width");join(intern(a),intern(b));++aliases;
  }else{
   // Only quoted terminal-name incidence is recorded. This does not parse
   // device physics or assert that a quoted token is a conductive terminal.
   while(input){input>>std::ws;if(input.peek()==EOF)break;bool quoted=input.peek()=='"';require(bool(input>>std::quoted(token)),"EXT device token");if(quoted)nodes[intern(token)].device=true;}
  }
 }
 require(ext.eof()&&!ext.bad(),"EXT read");
 std::ifstream groups(cfg.at("groups").str());require(bool(groups),"groups open");while(std::getline(groups,line)){auto g=Json::parse(line);nodes[intern(g.at("original_conductor").str())].native=true;}require(groups.eof()&&!groups.bad(),"groups read");
 for(size_t i=0;i<nodes.size();++i){auto r=root(i);if(r!=i){nodes[r].declared|=nodes[i].declared;nodes[r].port|=nodes[i].port;nodes[r].device|=nodes[i].device;nodes[r].native|=nodes[i].native;}}
 std::ifstream fields(cfg.at("inventory").str());require(bool(fields),"inventory open");std::ofstream rows(out/"fields.jsonl");require(bool(rows),"output open");I count=0;
 std::map<std::string,I> counts;std::map<std::pair<std::string,std::string>,I> materials;
 while(std::getline(fields,line)){
  if(count++%10000==0)check();auto r=Json::parse(line);const auto field=r.at("field_key");r.obj().erase("field_key");r["field"]=field;const auto& name=field.at(0).str();std::string state;bool declared=false,port=false,device=false,native=false;
  if(name=="@SUBSTRATE_REFERENCE")state="explicit_reference";
  else {auto it=ids.find(name);if(it==ids.end())state="no_EXT_declaration_or_explicit_alias";else {const auto& n=nodes[root(it->second)];declared=n.declared;port=n.port;device=n.device;native=n.native;
   state=n.native?"explicit_alias_component_has_native_R_label":n.port?"port_component_without_native_R_label":n.device?"quoted_device_incidence_without_native_R_label":n.declared?"declared_component_without_port_device_or_native_R":"alias_or_incidence_without_node_declaration";}}
  ++counts[state];++materials[{state,field.at(2).str()}];r["EXT_inventory_state"]=state;r["EXT_component_node_declared"]=declared;r["EXT_component_has_port"]=port;r["EXT_component_has_quoted_device_token"]=device;r["EXT_component_has_native_R_label"]=native;rows<<r.dump()<<'\n';require(bool(rows),"output write");
 }
 require(fields.eof()&&!fields.bad(),"field inventory read");rows.close();require(bool(rows),"output close");
 Json result=Json::object(),c=Json::object(),rc=Json::object(),m=Json::array();for(auto& [k,v]:counts)c[k]=v;for(auto& [k,v]:records)rc[k]=v;for(auto& [k,v]:materials){Json r=Json::object();r["state"]=k.first;r["material"]=k.second;r["fields"]=v;m.push(r);}
 result["fields"]=count;result["counts"]=c;result["EXT_records"]=rc;result["explicit_equivalence_records"]=aliases;result["by_state_material"]=m;
 result["scope"]="EXT node declarations, explicit equivalence, ports and quoted device-token incidence only; absence is not proof of isolation, finite-R completeness or physical qualification";
 result["physical_domain_complete"]=false;result["runtime_model_eligible"]=false;result["release_qualified"]=false;check();std::ofstream summary(out/"summary.json");summary<<result.dump()<<'\n';summary.close();require(bool(summary),"summary close");return 0;
}catch(const std::exception& e){std::cerr<<"classify_ext: "<<e.what()<<'\n';return 1;}}
