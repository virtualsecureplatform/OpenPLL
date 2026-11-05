#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <numeric>
#include <iostream>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Map{uint64_t targets;std::vector<uint32_t> values;};
static Map mapping(const std::string&path){std::ifstream in(path,std::ios::binary);require(bool(in),"voltage map open");char h[24];in.read(h,24);require(bool(in)&&std::string(h,8)=="CNETDOF1","map header");uint64_t n=sparse::load(h+8),targets=sparse::load(h+16);require(n&&n<=UINT32_MAX&&targets&&targets<=UINT32_MAX,"map dimensions");Map m{targets,std::vector<uint32_t>(n)};in.read((char*)m.values.data(),n*4);require(bool(in),"map records");char extra;require(!in.get(extra)&&in.eof(),"map complete");for(auto v:m.values)require(v<targets,"map target bounds");return m;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto zero=mapping(cfg.at("zero_map").str()),original=mapping(cfg.at("original_net_map").str());require(zero.values.size()==original.values.size(),"maps share original voltage domain");uint32_t nodes=zero.targets,nets=original.targets;
 std::vector<uint32_t> expected(nodes,UINT32_MAX),parent(nodes),size(nodes,1);std::iota(parent.begin(),parent.end(),0);std::vector<uint8_t> seen(nets,0);
 for(size_t i=0;i<zero.values.size();i++){auto target=zero.values[i],net=original.values[i];require(expected[target]==UINT32_MAX||expected[target]==net,"zero R alias crosses original conductors");expected[target]=net;seen[net]=1;}
 for(auto v:expected)require(v!=UINT32_MAX,"every constrained voltage covered");for(auto v:seen)require(v==1,"every original conductor represented");require(expected[0]==0,"abstract reference preserved");
 auto root=[&](uint32_t n){while(parent[n]!=n){parent[n]=parent[parent[n]];n=parent[n];}return n;};uint64_t components=nodes,edges=0,entries=0;
 for(auto&file:cfg.at("matrices").arr()){sparse::Reader input(file.str());sparse::Record r;while(input.next(r)){if(entries++%10000==0)require(now()<deadline,"graph component audit deadline");uint32_t a=r.key>>32,b=r.key&UINT32_MAX;require(a<=b&&b<nodes,"matrix node bounds");if(a==b||r.value==0)continue;require(r.value<0,"nonnegative edge weights required");require(expected[a]==expected[b],"conductance crosses original conductors");edges++;a=root(a);b=root(b);if(a==b)continue;if(size[a]<size[b])std::swap(a,b);parent[b]=a;size[a]+=size[b];components--;}}
 std::vector<uint32_t> conductor_root(nets,UINT32_MAX);for(uint32_t i=0;i<nodes;i++){auto r=root(i),net=expected[i];require(conductor_root[net]==UINT32_MAX||conductor_root[net]==r,"original conductor fragmented in positive G graph");conductor_root[net]=r;}
 require(components==nets,"graph components equal original conductors");std::ofstream out(cfg.at("component_map").str(),std::ios::binary);out.write("CNETDOF1",8);char h[16];sparse::store(h,nodes);sparse::store(h+8,nets);out.write(h,16);out.write((char*)expected.data(),uint64_t(nodes)*4);out.close();require(bool(out),"verified component map close");
 Json report=Json::object();report["constrained_voltage_nodes"]=I(nodes);report["original_voltage_nodes"]=I(zero.values.size());report["original_conductors"]=I(nets);report["positive_weight_graph_components"]=I(components);report["nonzero_graph_edges_scanned"]=I(edges);report["sparse_records_scanned"]=I(entries);report["all_original_conductors_exactly_connected"]=true;report["all_edges_within_original_conductors"]=true;report["all_original_and_constrained_map_slots_checked"]=true;std::ofstream report_file(cfg.at("report").str());report_file<<report.dump()<<'\n';require(bool(report_file),"report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
