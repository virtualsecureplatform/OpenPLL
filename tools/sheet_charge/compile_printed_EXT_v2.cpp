#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <filesystem>
#include <unordered_map>
#include <atomic>
#include <memory>
#include <sstream>
#include <omp.h>
#include <time.h>
#include <iostream>
using Real=long double;using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static std::string quoted(const std::string& line,size_t& pos){pos=line.find('"',pos);require(pos!=std::string::npos,"EXT quoted name");size_t end=line.find('"',++pos);require(end!=std::string::npos,"EXT quoted name end");auto name=line.substr(pos,end-pos);pos=end+1;return name;}
// Bound default printf %lg rounding from the decimal exponent, including
// suppressed trailing zeroes. At powers of ten this is conservative.
static std::pair<Real,Real> decimal(const std::string& token){
 size_t used=0;Real v=std::stold(token,&used);require(used==token.size()&&std::isfinite(v),"finite complete EXT value");if(v==0)return {0,0};
 auto epos=token.find_first_of("eE");std::string m=token.substr(0,epos);int exponent=epos==std::string::npos?0:std::stoi(token.substr(epos+1));if(m[0]=='+'||m[0]=='-')m.erase(0,1);
 auto dot=m.find('.');int before=dot==std::string::npos?int(m.size()):int(dot);std::string digits;for(char c:m)if(c!='.'){require(c>='0'&&c<='9',"EXT decimal digits");digits+=c;}
 size_t first=digits.find_first_not_of('0');require(first!=std::string::npos,"EXT nonzero decimal");int order=exponent+before-int(first)-1;
 Real bound=.5L*std::pow(10.L,order-5);require(std::isfinite(bound)&&bound>0,"EXT serialization bound");bound+=8*std::numeric_limits<Real>::epsilon()*std::fabs(v);return {v,bound};
}
struct Acc{sparse::Value value,error;};
int main(int argc,char**argv){try{
 require(argc==2,"usage: compile_printed_EXT CONFIG");auto cfg=Json::read(argv[1]);I threads=cfg.at("threads").integer(),limit=cfg.at("max_accumulator_entries").integer();require(threads>0&&threads<=16&&limit>=16&&limit<=1000000,"bounded EXT resources");double deadline=cfg.at("deadline_uptime").num();
 std::unordered_map<std::string,uint32_t> names;std::ifstream name_input(cfg.at("names").str());require(bool(name_input),"EXT conductor names");std::string line;while(std::getline(name_input,line)){auto row=Json::parse(line);auto id=row.arr()[0].integer();require(id==I(names.size()),"contiguous unique EXT conductor IDs");require(names.emplace(row.arr()[1].str(),id).second,"unique EXT conductor names");}require(name_input.eof()&&!names.empty(),"complete EXT names");
 uint32_t nodes=names.size();auto seen=std::make_unique<std::atomic<uint8_t>[]>(nodes);for(uint32_t i=0;i<nodes;i++)seen[i]=0;
 std::string input_path=cfg.at("ext").str(),out=cfg.at("output").str();std::filesystem::create_directory(out);uint64_t bytes=std::filesystem::file_size(input_path);
 std::vector<std::exception_ptr> errors(threads);std::vector<uint64_t> caps(threads),node_records(threads),substrates(threads),runs(threads),same(threads),scales(threads);std::vector<std::vector<std::string>> zero_extension(threads);
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{
  std::unordered_map<uint64_t,Acc> acc;acc.reserve(limit);std::ifstream stream(input_path,std::ios::binary);require(bool(stream),"EXT shard input");uint64_t begin=bytes*part/threads,end=bytes*(part+1)/threads;
  if(begin){stream.seekg(begin-1);char c;stream.get(c);if(c!='\n'){std::string skipped;std::getline(stream,skipped);}}else stream.seekg(0);
  auto flush=[&](){if(acc.empty())return;std::vector<sparse::Record> values,bounds;values.reserve(acc.size());bounds.reserve(acc.size());for(auto&[key,a]:acc){values.push_back({key,a.value.signed_sum.value(),a.value.absolute_sum.value(),a.value.terms});bounds.push_back({key,a.error.signed_sum.value(),a.error.absolute_sum.value(),a.error.terms});}auto order=[](auto&a,auto&b){return a.key<b.key;};std::sort(values.begin(),values.end(),order);std::sort(bounds.begin(),bounds.end(),order);auto stem=out+"/part_"+std::to_string(part)+"_run_"+std::to_string(runs[part]++);sparse::write(stem+".value.bin",values);sparse::write(stem+".error.bin",bounds);acc.clear();};
  auto id=[&](const std::string& name){auto found=names.find(name);require(found!=names.end(),"printed EXT name absent from conductor map: "+name);return found->second;};
  auto add=[&](uint32_t a,uint32_t b,Real v,Real error){uint64_t key=(uint64_t(std::min(a,b))<<32)|std::max(a,b);auto& x=acc[key];x.value.add(v);x.error.add(error);};
  auto edge=[&](uint32_t a,uint32_t b,Real v,Real error){if(a==b){same[part]++;return;}if(v==0&&error==0)return;add(a,a,v,error);add(b,b,v,error);add(a,b,-v,error);if(acc.size()>=uint64_t(limit))flush();};
  std::string text;uint64_t read=0;while(stream&&uint64_t(stream.tellg())<end&&std::getline(stream,text)){if(read++%10000==0)require(now()<deadline,"EXT compilation deadline");
   if(text.starts_with("cap ")){size_t p=0;auto a=id(quoted(text,p));auto b=id(quoted(text,p));std::istringstream tail(text.substr(p));std::string token,extra;require(bool(tail>>token)&&!(tail>>extra),"printed EXT cap record");auto[v,e]=decimal(token);edge(a,b,v,e);caps[part]++;}
   else if(text.starts_with("node ")||text.starts_with("substrate ")){bool substrate=text.starts_with("substrate ");size_t p=0;auto name=quoted(text,p);std::istringstream tail(text.substr(p));std::string resistance,token;require(bool(tail>>resistance>>token),"printed EXT node record");auto[v,e]=decimal(token);auto found=names.find(name);if(found==names.end()){require(!substrate&&v==0&&e==0,"unmapped printed node must have exactly zero capacitance");zero_extension[part].push_back(name);node_records[part]++;continue;}auto a=found->second;require(seen[a].exchange(1)==0,"unique printed EXT node");if(substrate){require(a==0&&v==0,"declared substrate must be reference with zero printed cap");substrates[part]++;}else{require(a!=0,"reference must use substrate declaration");edge(0,a,v,e);node_records[part]++;}}
   else if(text.starts_with("scale ")){std::istringstream tail(text.substr(6));Real r,l,c;std::string extra;require(bool(tail>>r>>l>>c)&&!(tail>>extra)&&c>0,"EXT scale record");require(c==cfg.at("native_internal_units_per_printed_EXT_unit").num(),"EXT scale identity");scales[part]++;}
  }require(!stream.bad(),"EXT shard read");flush();
 }catch(...){errors[part]=std::current_exception();}}
 for(auto&e:errors)if(e)std::rethrow_exception(e);
 std::vector<std::string> extra;for(auto&part:zero_extension)extra.insert(extra.end(),part.begin(),part.end());std::sort(extra.begin(),extra.end());require(std::adjacent_find(extra.begin(),extra.end())==extra.end(),"unique zero-extension node names");require(uint64_t(nodes)+extra.size()<UINT32_MAX,"bounded zero-extended node count");std::ofstream extension(out+"/zero_extension_nodes.jsonl");for(size_t i=0;i<extra.size();i++)extension<<Json(Json::Array{I(nodes+i),extra[i]}).dump()<<'\n';extension.close();require(bool(extension),"zero-extension node map close");
 auto total=[](auto&v){uint64_t n=0;for(auto x:v)n+=x;return n;};require(total(node_records)+total(substrates)==nodes+extra.size()&&total(substrates)==1&&total(scales)==1,"complete printed EXT node/scale coverage");for(uint32_t i=0;i<nodes;i++)require(seen[i]==1,"every known conductor has a printed EXT node");
 Json report=Json::object();report["conductor_nodes"]=I(nodes+extra.size());report["known_conductor_nodes"]=I(nodes);report["explicit_zero_extension_nodes"]=I(extra.size());report["zero_extension_has_no_printed_coupling_endpoints"]=true;report["printed_node_records"]=I(total(node_records));report["printed_cap_records"]=I(total(caps));report["substrate_records"]=I(total(substrates));report["same_conductor_edges_ignored"]=I(total(same));report["paired_sparse_runs"]=I(total(runs));report["printed_values_already_in_trace_units"]=true;std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
