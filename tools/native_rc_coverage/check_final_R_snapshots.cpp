// Reconcile selected native snapshots with the final .res.ext node/R multisets.
#include "../charge_compiler/json.hpp"
#include <cmath>
#include <cstdio>
#include <iomanip>
#include <sstream>
#include <unordered_map>
using Counts=std::unordered_map<std::string,long long>;
struct Node {std::string name;long long x,y;};
struct Edge {std::string a,b,value;};
static std::string key(const Node& n){std::ostringstream s;s<<std::quoted(n.name)<<' '<<n.x<<' '<<n.y;return s.str();}
static std::string key(std::string a,std::string b,const std::string& value){
 if(a>b)std::swap(a,b);std::ostringstream s;s<<std::quoted(a)<<' '<<std::quoted(b)<<' '<<value;return s.str();
}
static void subtract(Counts& table,const std::string& k){auto i=table.find(k);require(i!=table.end()&&i->second>0,"final export record missing from selected snapshots: "+k);--i->second;}
int main(int argc,char**argv){try{
 require(argc==5,"usage: check_final_R_snapshots PROVENANCE RES_EXT SKIP_GROUPS OUTPUT");
 const auto skip=std::stoll(argv[3]);require(skip>=0,"negative skipped prefix");
 std::ifstream raw(argv[1]);require(bool(raw),"open provenance");
 std::unordered_map<std::string,Node> nodes;std::unordered_map<std::string,Edge> edges;
 Counts expected_nodes,expected_edges;long long group=0,last=0,selected=0,node_count=0,edge_count=0;
 bool active=false;std::string line,pending;Json chosen=Json::array();
 while(std::getline(raw,line)){
  std::istringstream s(line);std::string kind;s>>kind;
  if(kind=="TYPE")continue;
  if(kind=="BEGIN"){
   std::string original;s>>group>>std::quoted(original);require(bool(s)&&!active&&group==last+1,"native begin sequence");active=true;last=group;
   if(group>skip){Json item=Json::object();item["group"]=group;item["original"]=original;chosen.push(item);}
  }else{
   long long g;s>>g;require(bool(s)&&active&&g==group,"native record group");
   if(kind=="END"){
    require(pending.empty(),"unfinished branch");
    if(group>skip){
     ++selected;node_count+=nodes.size();edge_count+=edges.size();
     for(const auto&[p,n]:nodes)++expected_nodes[key(n)];
     for(const auto&[p,e]:edges){
      require(nodes.count(e.a)&&nodes.count(e.b),"branch endpoint absent");
      float native=std::stof(e.value);require(std::isfinite(native),"nonfinite native R");
      // Exact ResPrintExtRes expression: float milliohms / float scale,
      // promoted to double for printf's default-six-significant-digit %g.
      float ohms=native/1000.0F;char printed[128];std::snprintf(printed,sizeof printed,"%g",double(ohms));
      ++expected_edges[key(nodes.at(e.a).name,nodes.at(e.b).name,printed)];
     }
    }
    nodes.clear();edges.clear();active=false;
   }else if(group<=skip)continue;
   else if(kind=="NODE"){
    std::string pointer;Node n;unsigned why;int status;s>>pointer>>std::quoted(n.name)>>n.x>>n.y>>why>>status;
    require(bool(s)&&nodes.emplace(pointer,n).second,"malformed/duplicate node");
   }else if(kind=="BRANCH"){
    std::string owner;s>>owner>>pending;require(bool(s),"malformed branch");
   }else if(kind=="EDGE"){
    std::string owner;Edge e;unsigned type;int status;s>>owner>>e.a>>e.b>>e.value>>type>>status;
    require(bool(s)&&!pending.empty(),"edge without branch");auto[it,added]=edges.emplace(pending,e);
    require(added||(it->second.a==e.a&&it->second.b==e.b&&it->second.value==e.value),"inconsistent branch");pending.clear();
   }else throw std::runtime_error("unknown provenance record");
  }
 }
 require(raw.eof()&&!raw.bad()&&!active&&selected>0,"incomplete provenance");
 std::ifstream ext(argv[2]);require(bool(ext),"open final res.ext");long long actual_nodes=0,actual_edges=0,scale_count=0;
 while(std::getline(ext,line)){
  std::istringstream s(line);std::string kind;s>>kind;
  if(kind=="scale"){long long scale;s>>scale;require(scale==1000,"unexpected native R scale");++scale_count;}
  else if(kind=="rnode"){
   Node n;std::string r,c;int type;s>>std::quoted(n.name)>>r>>c>>n.x>>n.y>>type;
   require(bool(s)&&r=="0"&&type==0,"unexpected rnode declaration");subtract(expected_nodes,key(n));++actual_nodes;
  }else if(kind=="resist"){
   std::string a,b,v;s>>std::quoted(a)>>std::quoted(b)>>v;require(bool(s),"malformed exported R");
   subtract(expected_edges,key(a,b,v));++actual_edges;
  }
 }
 require(ext.eof()&&!ext.bad()&&scale_count==1,"incomplete final export");
 for(const auto&[k,v]:expected_nodes)require(v==0,"selected node not in final export: "+k);
 for(const auto&[k,v]:expected_edges)require(v==0,"selected resistor not in final export: "+k);
 Json report=Json::object();report["status"]="pass";report["selected_groups"]=chosen;
 report["selected_group_count"]=selected;report["obsolete_prefix_groups"]=skip;
 report["native_node_count"]=node_count;report["native_branch_count"]=edge_count;
 report["exported_node_count"]=actual_nodes;report["exported_resistor_count"]=actual_edges;
 report["final_res_ext_node_and_resistor_multisets_match"]=true;
 report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream out(argv[4]);require(bool(out),"open output");out<<report.dump()<<'\n';require(bool(out),"write output");
 std::cout<<"matched "<<selected<<" final snapshots, "<<actual_nodes<<" nodes, "<<actual_edges<<" resistors\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
