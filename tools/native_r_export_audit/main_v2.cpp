// Exact diagnostic comparison of native printed R cards; no model qualification.
#include "../charge_compiler/json.hpp"
#include <array>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>
#include <time.h>
using I=long long;
using Point=std::pair<I,I>;
using Nodes=std::map<std::string,std::map<Point,I>>;
using Edge=std::tuple<std::string,std::string,double>;
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
static std::vector<std::string> words(const std::string& line){
    std::istringstream in(line);std::vector<std::string> out;std::string word;
    for(;;){in>>std::ws;if(in.eof())break;need(bool(in>>std::quoted(word)),"malformed quoted record");out.push_back(word);}
    return out;
}
static I integer(const std::string& s){size_t n;I v=std::stoll(s,&n);need(n==s.size(),"invalid integer");return v;}
static double number(const std::string& s){size_t n;double v=std::stod(s,&n);need(n==s.size()&&std::isfinite(v),"invalid finite number");return v;}
static Edge edge(std::string a,std::string b,double value){if(b<a)std::swap(a,b);return {a,b,value};}
static double uptime(){timespec t{};need(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static void save(const std::string& path,const Json& j){std::ofstream f(path);f<<j.dump()<<'\n';f.close();need(bool(f),"write "+path);}
int main(int argc,char** argv){try{
    need(argc==2,"usage: native_r_export_audit CONFIG");Json cfg=Json::read(argv[1]);
    const double deadline=cfg.at("deadline_uptime").num();
    auto check=[&](){need(uptime()<deadline,"whole-check deadline exhausted");};check();
    need(std::filesystem::create_directory(cfg.at("output").str()),"fresh native output required");
    Nodes expected_nodes;std::map<Edge,I> expected_edges;std::map<std::string,I> expected_degree,ignored;
    std::array<char,1024*1024> buf1{},buf2{};
    std::ifstream ext;ext.rdbuf()->pubsetbuf(buf1.data(),buf1.size());ext.open(cfg.at("export").str());need(bool(ext),"open export");
    std::string line;float scale=0;I records=0,exported_nodes=0,exported_edges=0;
    while(std::getline(ext,line)){
        if(++records%10000==0)check();
        auto f=words(line);if(f.empty())continue;
        if(f[0]=="scale"){need(f.size()==4&&scale==0,"scale record");scale=float(number(f[1]));need(scale>0&&std::isfinite(scale),"resistance scale");}
        else if(f[0]=="rnode"){need(f.size()==7,"rnode record");++expected_nodes[f[1]][{integer(f[4]),integer(f[5])}];++exported_nodes;}
        else if(f[0]=="resist"){need(f.size()==4,"resistor record");++expected_edges[edge(f[1],f[2],number(f[3]))];++expected_degree[f[1]];++expected_degree[f[2]];++exported_edges;}
        else ++ignored[f[0]];
    }
    need(ext.eof()&&scale>0,"incomplete export");
    std::ifstream native;native.rdbuf()->pubsetbuf(buf2.data(),buf2.size());native.open(cfg.at("native").str());need(bool(native),"open native");
    const std::string out=cfg.at("output").str();
    std::ofstream rows(out+"/groups.jsonl");need(bool(rows),"open groups output");
    std::map<std::string,std::pair<std::string,Point>> nodes;
    using Raw=std::tuple<std::string,std::string,std::string,std::string,std::string>;
    std::map<std::string,std::pair<Raw,I>> branches;
    std::string id,name,pending_owner,pending_branch;bool active=false;I total=0,matched=0;
    std::map<std::string,std::vector<std::string>> candidates;
    struct Selection {Nodes nodes;std::map<Edge,I> edges;};
    std::map<std::string,Selection> latest;
    auto finish=[&](){
        need(pending_branch.empty(),"unpaired branch");Nodes actual_nodes;std::map<std::string,I> degree;std::map<Edge,I> edges;
        for(auto& [ptr,n]:nodes)++actual_nodes[n.first][n.second];
        bool node_match=true,edge_match=true;
        for(auto& [label,points]:actual_nodes){auto it=expected_nodes.find(label);node_match&=it!=expected_nodes.end()&&it->second==points;}
        for(auto& [ptr,raw_count]:branches){
            need(raw_count.second==2,"branch incident multiplicity is not two");auto& [a,b,value,type,status]=raw_count.first;
            need(nodes.count(a)&&nodes.count(b),"unbound branch endpoint");
            double observed=number(value);float native_value=float(observed);need(double(native_value)==observed,"native resistor is not exact float32");
            float resistance=native_value/scale;need(std::isfinite(resistance),"nonfinite printed resistor");
            char printed[64];std::snprintf(printed,sizeof(printed),"%.6g",double(resistance));
            auto key=edge(nodes.at(a).first,nodes.at(b).first,number(printed));++edges[key];
            ++degree[nodes.at(a).first];++degree[nodes.at(b).first];
        }
        for(auto& [key,count]:edges){auto it=expected_edges.find(key);edge_match&=it!=expected_edges.end()&&it->second==count;}
        for(auto& [label,points]:actual_nodes){
            I want=expected_degree.count(label)?expected_degree.at(label):0;
            I have=degree.count(label)?degree.at(label):0;edge_match&=want==have;
        }
        Json r=Json::object();r["native_group_id"]=id;r["original_conductor"]=name;
        r["native_nodes"]=I(nodes.size());r["native_branches"]=I(branches.size());
        r["printed_node_names_coordinates_match"]=node_match;r["printed_resistors_and_incidence_match"]=edge_match;
        r["ambiguous_printed_node_names"]=actual_nodes.size()!=nodes.size();r["runtime_model_eligible"]=false;
        rows<<r.dump()<<'\n';need(bool(rows),"write group");
        auto& list=candidates[name];if(node_match&&edge_match){list.push_back(id);++matched;}
        latest[name]=Selection{std::move(actual_nodes),std::move(edges)};
        active=false;nodes.clear();branches.clear();
    };
    while(std::getline(native,line)){
        if(++records%10000==0)check();
        auto f=words(line);need(!f.empty(),"empty native record");
        if(f[0]=="TYPE"){need(!active&&f.size()==3,"type record");continue;}
        if(f[0]=="BEGIN"){
            need(!active&&f.size()==3&&integer(f[1])==total+1,"native group sequence");
            id=f[1];name=f[2];active=true;++total;continue;
        }
        need(active&&f.size()>=2&&f[1]==id,"native group alignment");
        if(f[0]=="NODE"){
            need(pending_branch.empty()&&f.size()==8&&!nodes.count(f[2]),"native node record");
            nodes.emplace(f[2],std::make_pair(f[3],Point{integer(f[4]),integer(f[5])}));
        } else if(f[0]=="BRANCH"){
            need(pending_branch.empty()&&f.size()==4&&nodes.count(f[2]),"branch record");pending_owner=f[2];pending_branch=f[3];
        } else if(f[0]=="EDGE"){
            need(f.size()==8&&!pending_branch.empty()&&pending_owner==f[2]&&(f[2]==f[3]||f[2]==f[4]),"unpaired incident edge");
            Raw raw{f[3],f[4],f[5],f[6],f[7]};auto [it,added]=branches.emplace(pending_branch,std::make_pair(raw,I(0)));
            need(added||it->second.first==raw,"inconsistent branch record");++it->second.second;pending_branch.clear();pending_owner.clear();
        } else if(f[0]=="END"){need(f.size()==2,"group end");finish();}
        else throw std::runtime_error("unknown native record");
    }
    need(native.eof()&&!active&&total>0,"incomplete native groups");rows.close();need(bool(rows),"close groups");check();
    Nodes union_nodes;std::map<Edge,I> union_edges;
    for(auto& [label,selection]:latest){
        check();
        for(auto& [node,points]:selection.nodes)for(auto& [point,count]:points)union_nodes[node][point]+=count;
        for(auto& [key,count]:selection.edges)union_edges[key]+=count;
    }
    const bool complete_nodes=union_nodes==expected_nodes,complete_edges=union_edges==expected_edges;
    Json result=Json::object(),labels=Json::object(),ignored_json=Json::object();I none=0,one=0,multiple=0;
    for(auto& [label,ids]:candidates){Json list=Json::array();for(auto& x:ids)list.push(x);labels[label]=list;if(ids.empty())++none;else if(ids.size()==1)++one;else ++multiple;}
    for(auto& [kind,count]:ignored)ignored_json[kind]=count;
    result["last_group_node_cards_equal_entire_export"]=complete_nodes;
    result["last_group_resistor_cards_equal_entire_export"]=complete_edges;
    result["native_groups"]=total;result["matching_printed_groups"]=matched;result["exported_node_cards"]=exported_nodes;
    result["exported_resistor_cards"]=exported_edges;result["labels_with_no_matching_group"]=none;
    result["labels_with_one_matching_group"]=one;result["labels_with_multiple_matching_groups"]=multiple;
    result["matching_group_ids_by_label"]=labels;result["other_export_record_counts"]=ignored_json;
    result["scope"]="printed node name/coordinate and resistor cards only; capacitance, device binding, contact/tile domains and final lifetime selection remain unqualified";
    result["runtime_model_eligible"]=false;result["release_qualified"]=false;save(out+"/summary.json",result);return 0;
}catch(const std::exception& e){std::fprintf(stderr,"native_r_export_audit: %s\n",e.what());return 1;}}
