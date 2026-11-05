#include "../charge_compiler/json.hpp"
#include "bounded_jsonl_range.hpp"
#include <iostream>
int main(int argc,char**argv){try{
 require(argc==2,"usage OUTPUT_DIRECTORY");std::filesystem::path out=argv[1];uint64_t trials=0;
 for(auto text:std::vector<std::string>{"","a\n","a\nbc\n\nxyz\n","alpha\r\nbeta\n","\xc3\xa9\nlast\n"}){
  auto path=out/("fixture_"+std::to_string(trials)+".jsonl");{std::ofstream f(path,std::ios::binary);f<<text;}
  std::vector<std::pair<uint64_t,std::string>> expected;uint64_t pos=0;while(pos<text.size()){auto end=text.find('\n',pos);require(end!=text.npos,"fixture termination");expected.emplace_back(pos,text.substr(pos,end-pos));pos=end+1;}
  for(uint64_t begin=0;begin<=text.size();begin++)for(uint64_t end=begin;end<=text.size();end++){
   bounded_jsonl::Range input(path.string(),begin,end);std::vector<std::pair<uint64_t,std::string>> actual,wanted;std::string line;uint64_t offset;
   while(input.next(line,offset))actual.emplace_back(offset,line);for(auto&record:expected)if(record.first>=begin&&record.first<end)wanted.push_back(record);require(actual==wanted,"exact range record ownership");trials++;
  }
 }
 auto invalid=out/"unterminated.jsonl";{std::ofstream f(invalid);f<<"complete\npartial";}int rejected=0;
 for(int kind=0;kind<3;kind++){bool failed=false;try{bounded_jsonl::Range input(invalid.string(),kind==1?20:0,kind==2?17:15);std::string line;uint64_t offset;while(input.next(line,offset)){} }catch(const std::runtime_error&){failed=true;}require(failed,"invalid range or unterminated owned record rejected");rejected++;}
 Json r=Json::object();r["exhaustive_range_ownership_trials"]=static_cast<long long>(trials);r["invalid_controls_rejected"]=rejected;std::cout<<r.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
