#pragma once
#include <cstdint>
#include <fstream>
#include <vector>
inline std::vector<uint8_t> read_zero_C_mask(const std::string&path,uint64_t nodes){
 require(nodes>0&&nodes<=UINT32_MAX,"zero-C mask node bound");
 std::ifstream input(path,std::ios::binary);require(bool(input),"zero-C mask input");char header[16]{};input.read(header,16);
 uint64_t count=0;for(int k=0;k<8;k++)count|=uint64_t(static_cast<unsigned char>(header[8+k]))<<(8*k);
 require(bool(input)&&std::string(header,8)=="CZEROR01"&&count==nodes,"zero-C mask namespace");
 std::vector<uint8_t>mask(nodes);input.read(reinterpret_cast<char*>(mask.data()),nodes);require(bool(input),"complete zero-C mask");
 char extra;require(!input.get(extra)&&input.eof(),"zero-C mask trailing bytes");for(auto value:mask)require(value<=1,"binary zero-C mask values");
 require(mask[0]==0,"explicit reference cannot be removed by the zero-row derivative");return mask;
}
