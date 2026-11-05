#pragma once
#include "sparse_runs_v2.hpp"
#include <filesystem>
namespace sparse {
class SliceReader{
 std::ifstream input;uint64_t left=0,last=0;bool first=true;
public:
 uint64_t total=0;
 SliceReader(const std::string& path,uint64_t begin,uint64_t end):input(path,std::ios::binary){require(bool(input),"sparse slice input");char h[16];input.read(h,16);require(bool(input)&&std::string(h,8)=="SPCRUN01","sparse slice header");total=load(h+8);uint64_t size=std::filesystem::file_size(path);require(size>=16&&(size-16)%40==0&&(size-16)/40==total,"sparse slice file size");require(begin<=end&&end<=total,"sparse slice bounds");input.seekg(std::streamoff(16+40*begin));require(bool(input),"sparse slice seek");left=end-begin;}
 bool next(Record& r){if(!left)return false;char b[40];input.read(b,40);require(bool(input),"sparse slice complete record");r.key=load(b);r.value=0;r.absolute=0;std::memcpy(&r.value,b+8,10);std::memcpy(&r.absolute,b+18,10);r.terms=load(b+28);require(std::isfinite(r.value)&&std::isfinite(r.absolute)&&r.absolute>=0&&r.terms>0&&magnitude_bound(r.value,r.absolute),"sparse slice finite bounded values");require((r.key>>32)<=(r.key&UINT32_MAX),"sparse slice upper triangle");for(int k=36;k<40;k++)require(b[k]==0,"sparse slice reserved bytes");require(first||r.key>last,"sparse slice sorted keys");last=r.key;first=false;left--;return true;}
};
}
