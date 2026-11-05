#pragma once
#include "../charge_compiler/json.hpp"
#include <cstdint>
class ConductorMap{
 std::vector<uint32_t> values;uint64_t nets=0;
 static uint64_t integer(const char* p,int width){uint64_t n=0;for(int k=0;k<width;k++)n|=uint64_t(static_cast<unsigned char>(p[k]))<<(8*k);return n;}
public:
 ConductorMap(const std::string& path,const std::string& magic){std::ifstream in(path,std::ios::binary);require(bool(in),"conductor map input");char h[24];in.read(h,24);require(bool(in)&&std::string(h,8)==magic,"conductor map header");uint64_t count=integer(h+8,8);nets=integer(h+16,8);require(count>0&&count<100000000&&nets>0&&nets<=UINT32_MAX,"bounded conductor map");values.resize(count);
  for(auto& v:values){char b[4];in.read(b,4);require(bool(in),"complete conductor map entry");v=uint32_t(integer(b,4));require(v<nets,"conductor map entry bounds");}char c;require(!in.get(c)&&in.eof(),"conductor map trailing bytes");}
 uint32_t at(uint64_t id)const{require(id<values.size(),"conductor map lookup bounds");return values[id];}
 uint64_t size()const{return values.size();}uint64_t net_count()const{return nets;}
};
