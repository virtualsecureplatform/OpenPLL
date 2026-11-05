#pragma once
#include <filesystem>
#include <fstream>
#include <cstdint>
// Own a record iff its first byte lies in [begin,end). Require newline termination.
namespace bounded_jsonl {
class Range {
 std::ifstream input;uint64_t end=0;bool done=false;
public:
 Range(const std::string&path,uint64_t begin,uint64_t stop):input(path,std::ios::binary),end(stop){
  require(bool(input),"range input open");uint64_t size=std::filesystem::file_size(path);
  require(begin<=stop&&stop<=size&&size<=INT64_MAX,"JSONL range bounds");
  if(begin==stop){done=true;return;}
  input.seekg(begin?begin-1:0);require(bool(input),"JSONL range seek");
  if(begin){char previous;input.get(previous);require(bool(input),"JSONL preceding byte");if(previous!='\n'){std::string skipped;std::getline(input,skipped);require(!input.bad(),"JSONL partial record skip");if(input.eof())done=true;}}
 }
 bool next(std::string&raw,uint64_t&offset){
  if(done)return false;auto position=input.tellg();require(position>=0,"JSONL record position");offset=uint64_t(position);if(offset>=end){done=true;return false;}
  require(bool(std::getline(input,raw)),"complete owned JSONL record");require(!input.eof()&&!input.bad(),"newline terminated owned JSONL record");return true;
 }
};
}
