// Sufficient proof of identical Decimal-fold capacitance matrices: same raw
// value-token sequence within each unordered node pair. Differing spellings or
// zero/cancellation representations are inconclusive, never silently accepted.
#include "../charge_compiler/json.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <regex>
#include <string_view>
#include <unordered_map>
#include <time.h>
#include <omp.h>
#include <parallel/algorithm>
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Hash{using is_transparent=void;size_t operator()(std::string_view s)const{return std::hash<std::string_view>{}(s);}};
using Intern=std::unordered_map<std::string,uint32_t,Hash,std::equal_to<>>;
static bool space(char c){return c==' '||c=='\t'||c=='\r'||c=='\n'||c=='\f'||c=='\v';}
static void ascii(const std::string& s){for(unsigned char c:s)require((c>=32&&c<=126)||space(char(c)),"unsupported non-ASCII/control input");}
static std::string_view token(std::string_view& s){while(!s.empty()&&space(s.front()))s.remove_prefix(1);size_t n=0;while(n<s.size()&&!space(s[n]))++n;auto result=s.substr(0,n);s.remove_prefix(n);return result;}
static uint32_t intern(Intern& table,std::string_view value){auto it=table.find(value);if(it!=table.end())return it->second;require(table.size()<UINT32_MAX,"intern capacity");uint32_t id=uint32_t(table.size());table.emplace(std::string(value),id);return id;}
struct Record{uint32_t a,b,value,sequence;};
struct Less{bool operator()(const Record& a,const Record& b)const{if(a.a!=b.a)return a.a<b.a;if(a.b!=b.b)return a.b<b.b;return a.sequence<b.sequence;}};
static std::vector<Record> capacitors(const std::string& path,Intern& nodes,Intern& values,double deadline){
 std::array<char,1048576> buffer{};std::ifstream input;input.rdbuf()->pubsetbuf(buffer.data(),buffer.size());input.open(path,std::ios::binary);require(bool(input),"open capacitor file");std::vector<Record> rows;std::string line;uint64_t lines=0;
 static const std::regex numeric(R"(^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE]([+-]?[0-9]+))?(?:meg|[fpnumkg]?)$)",std::regex::icase);
 while(std::getline(input,line)){ascii(line);if(++lines%100000==0)require(now()<deadline,"card comparison deadline");if(line.empty()||line[0]!='C')continue;std::string_view tail=line;token(tail);auto a=token(tail),b=token(tail),v=token(tail);require(!a.empty()&&!b.empty()&&!v.empty(),"malformed capacitor card");if(values.find(v)==values.end()){std::match_results<std::string_view::const_iterator> match;require(v.size()<=256&&std::regex_match(v.begin(),v.end(),match,numeric),"unsupported/nonfinite capacitor value");if(match[1].matched){auto exponent=std::stoll(match[1].str());require(exponent>=-1000&&exponent<=1000,"unsupported Decimal exponent range");}}auto x=intern(nodes,a),y=intern(nodes,b);if(x>y)std::swap(x,y);require(rows.size()<UINT32_MAX,"capacitor sequence capacity");rows.push_back({x,y,intern(values,v),uint32_t(rows.size())});}
 require(input.eof()&&!input.bad(),"capacitor read failure");require(now()<deadline,"card comparison deadline");return rows;
}
static std::vector<std::string> devices(const std::string& path,double deadline){
 std::array<char,1048576> buffer{};std::ifstream input;input.rdbuf()->pubsetbuf(buffer.data(),buffer.size());input.open(path,std::ios::binary);require(bool(input),"open device file");std::string line;std::vector<std::string> result;uint64_t lines=0;
 while(std::getline(input,line)){ascii(line);if(++lines%100000==0)require(now()<deadline,"device comparison deadline");if(line.rfind("device ",0)!=0)continue;std::string_view s=line;std::string normalized;for(;;){auto word=token(s);if(word.empty())break;if(!normalized.empty())normalized+=' ';normalized+=word;}result.push_back(std::move(normalized));}
 require(input.eof()&&!input.bad(),"device read failure");__gnu_parallel::sort(result.begin(),result.end());require(now()<deadline,"device comparison deadline");return result;
}
int main(int argc,char** argv){try{
 require(argc==2,"usage: compare_native_cards CONFIG");auto c=Json::read(argv[1]);double deadline=c.at("deadline_uptime").num(),start=now();require(start<deadline,"card comparison deadline");int threads=int(c.at("threads").integer());require(threads>0&&threads<=64,"bounded comparison threads");omp_set_num_threads(threads);
 Intern nodes,values;auto left=capacitors(c.at("left_spice").str(),nodes,values,deadline);auto right=capacitors(c.at("right_spice").str(),nodes,values,deadline);require(left.size()==right.size(),"inconclusive: C record counts differ");
 __gnu_parallel::sort(left.begin(),left.end(),Less{});__gnu_parallel::sort(right.begin(),right.end(),Less{});require(now()<deadline,"card comparison deadline");
 for(size_t i=0;i<left.size();++i){auto& a=left[i];auto& b=right[i];require(a.a==b.a&&a.b==b.b&&a.value==b.value,"inconclusive: per-pair raw value sequences differ at sorted row "+std::to_string(i));if(i%1000000==0)require(now()<deadline,"card comparison deadline");}
 auto a=devices(c.at("left_ext").str(),deadline),b=devices(c.at("right_ext").str(),deadline);require(a==b,"native device statement multiset differs");Json result=Json::object();result["same_per_pair_value_token_sequences"]=true;result["same_native_device_statement_multiset"]=true;result["exact_Decimal_fold_matrix_equality_implied"]=true;result["capacitor_records_each"]=static_cast<long long>(left.size());result["native_devices_each"]=static_cast<long long>(a.size());result["distinct_nodes"]=static_cast<long long>(nodes.size());result["distinct_value_tokens"]=static_cast<long long>(values.size());result["threads"]=threads;result["elapsed_s"]=now()-start;result["release_qualified"]=false;std::cout<<result.dump()<<'\n';return 0;
}catch(const std::exception& e){std::cerr<<"compare_native_cards: "<<e.what()<<'\n';return 1;}}
