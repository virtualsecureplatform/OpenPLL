#include "../charge_compiler/json.hpp"
#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <thread>
#include <unordered_map>
#include <exception>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Stats {uint64_t caps=0,nonzero=0,missing=0,zero_missing=0,same=0;std::unordered_map<std::string,std::pair<uint64_t,uint64_t>> unknown;std::exception_ptr error;};
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);I threads=cfg.at("threads").integer();require(threads>0&&threads<=16,"thread bounds");double deadline=cfg.at("deadline_uptime").num();
 std::unordered_map<std::string,uint32_t> names;std::string line;std::ifstream input(cfg.at("names").str());require(bool(input),"conductor names open");uint64_t original=0;
 while(std::getline(input,line)){auto r=Json::parse(line);require(r.at(0).integer()==I(original++),"conductor contiguous IDs");require(names.emplace(r.at(1).str(),r.at(0).integer()).second,"conductor unique names");}require(input.eof()&&original>0,"conductor names complete");
 input.close();input.open(cfg.at("native_nodes").str());require(bool(input),"native R nodes open");uint64_t native=0,inserted=0;
 while(std::getline(input,line)){if(native++%10000==0)require(now()<deadline,"registry deadline");auto r=Json::parse(line);auto c=names.find(r.at("original_conductor").str());require(c!=names.end(),"R original conductor missing");uint32_t id=c->second;auto [it,ok]=names.emplace(r.at("printed_name").str(),id);require(ok||it->second==id,"native printed name conductor collision");inserted+=ok;}require(input.eof(),"native R nodes complete");
 std::string deck=cfg.at("deck").str();uint64_t bytes=std::filesystem::file_size(deck);std::vector<Stats> stats(threads);std::vector<std::thread> jobs;
 for(I part=0;part<threads;part++)jobs.emplace_back([&,part]{auto&s=stats[part];try{std::ifstream stream(deck,std::ios::binary);require(bool(stream),"deck open");uint64_t begin=bytes*part/threads,end=bytes*(part+1)/threads;if(begin){stream.seekg(begin-1);char ch;stream.get(ch);if(ch!='\n'){std::string skipped;std::getline(stream,skipped);}}else stream.seekg(0);std::string text;uint64_t count=0;
 while(stream&&uint64_t(stream.tellg())<end&&std::getline(stream,text)){if(count++%10000==0)require(now()<deadline,"endpoint scan deadline");if(text.empty()||text[0]!='C')continue;std::istringstream row(text);std::string instance,a,b,token;require(bool(row>>instance>>a>>b>>token),"C token syntax");size_t used=0;long double value=std::stold(token,&used);std::string suffix=token.substr(used);require(suffix.empty()||suffix=="f"||suffix=="p"||suffix=="n"||suffix=="u"||suffix=="m"||suffix=="k"||suffix=="G","C suffix");require(std::isfinite(value),"C finite");bool nonzero=value!=0;s.caps++;s.nonzero+=nonzero;auto x=names.find(a),y=names.find(b);bool absent=x==names.end()||y==names.end();if(absent){if(nonzero)s.missing++;else s.zero_missing++;for(auto*n:{&a,&b})if(names.find(*n)==names.end()){require(s.unknown.size()<100000||s.unknown.contains(*n),"bounded missing endpoint inventory");auto&u=s.unknown[*n];if(nonzero)u.first++;else u.second++;}}else if(x->second==y->second)s.same++;
 }require(!stream.bad(),"complete deck shard");}catch(...){s.error=std::current_exception();}});
 for(auto&t:jobs)t.join();Stats all;for(auto&s:stats){if(s.error)std::rethrow_exception(s.error);all.caps+=s.caps;all.nonzero+=s.nonzero;all.missing+=s.missing;all.zero_missing+=s.zero_missing;all.same+=s.same;for(auto&[name,n]:s.unknown){all.unknown[name].first+=n.first;all.unknown[name].second+=n.second;}}
 std::vector<std::string> sorted;for(auto&[name,n]:all.unknown)sorted.push_back(name);std::sort(sorted.begin(),sorted.end());std::ofstream unknown(cfg.at("unknown_output").str());for(auto&name:sorted){auto n=all.unknown.at(name);unknown<<Json(Json::Array{name,I(n.first),I(n.second)}).dump()<<'\n';}unknown.close();require(bool(unknown),"unknown endpoint inventory close");
 Json report=Json::object();report["original_conductors"]=I(original);report["native_R_node_records"]=I(native);report["added_native_R_names"]=I(inserted);report["registered_endpoint_names"]=I(names.size());report["capacitor_records"]=I(all.caps);report["nonzero_capacitor_records"]=I(all.nonzero);report["nonzero_capacitors_with_unresolved_endpoints"]=I(all.missing);report["zero_capacitors_with_unresolved_endpoints"]=I(all.zero_missing);report["unresolved_endpoint_names"]=I(all.unknown.size());report["same_original_conductor_capacitors"]=I(all.same);std::ofstream out(cfg.at("report").str());out<<report.dump()<<'\n';require(bool(out),"report write");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
