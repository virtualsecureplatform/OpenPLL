#pragma once
#include <bit>
#include <cfloat>
#include <cstring>
#include <fstream>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
#include <algorithm>
namespace sparse {
using Real=long double;
static_assert(sizeof(Real)==16&&LDBL_MANT_DIG==64&&LDBL_MAX_EXP==16384);
static_assert(std::endian::native==std::endian::little);
struct Sum{Real sum=0,correction=0;void add(Real x){Real t=sum+x;correction+=std::fabs(sum)>=std::fabs(x)?(sum-t)+x:(x-t)+sum;sum=t;}Real value()const{return sum+correction;}};
struct Value{Sum signed_sum,absolute_sum;uint64_t terms=0;
 void add(Real value){require(std::isfinite(value),"finite sparse coefficient");signed_sum.add(value);absolute_sum.add(std::fabs(value));require(terms<UINT64_MAX,"sparse term overflow");terms++;}
 void merge(Real value,Real absolute,uint64_t count){require(std::isfinite(value)&&std::isfinite(absolute)&&absolute>=0&&count>0&&count<=UINT64_MAX-terms,"valid sparse reduction record");signed_sum.add(value);absolute_sum.add(absolute);terms+=count;}
};
struct Record{uint64_t key=0;Real value=0,absolute=0;uint64_t terms=0;};
inline void store(char* p,uint64_t n){for(int k=0;k<8;k++)p[k]=char(n>>(8*k));}
inline uint64_t load(const char* p){uint64_t n=0;for(int k=0;k<8;k++)n|=uint64_t(static_cast<unsigned char>(p[k]))<<(8*k);return n;}
inline void write_record(std::ostream& out,const Record& r){require(std::isfinite(r.value)&&std::isfinite(r.absolute)&&r.absolute>=0&&r.terms>0,"sparse record values");char bytes[40]{};store(bytes,r.key);std::memcpy(bytes+8,&r.value,10);std::memcpy(bytes+18,&r.absolute,10);store(bytes+28,r.terms);out.write(bytes,40);}
inline void header(std::ostream& out,uint64_t count){out.write("SPCRUN01",8);char bytes[8];store(bytes,count);out.write(bytes,8);}
inline void write(const std::string& path,const std::vector<Record>& rows){std::ofstream out(path,std::ios::binary);require(bool(out),"sparse run output");header(out,rows.size());uint64_t last=0;bool first=true;for(auto r:rows){require(first||r.key>last,"sorted unique sparse keys");write_record(out,r);last=r.key;first=false;}out.close();require(bool(out),"sparse run close");}
class Reader{
 std::ifstream input;uint64_t remaining=0,last=0;bool first=true;
public:
 explicit Reader(const std::string& path):input(path,std::ios::binary){require(bool(input),"sparse run input");char h[16];input.read(h,16);require(bool(input)&&std::string(h,8)=="SPCRUN01","sparse run header");remaining=load(h+8);}
 bool next(Record& r){if(!remaining){char c;require(!input.get(c)&&input.eof(),"sparse run trailing bytes");return false;}char b[40];input.read(b,40);require(bool(input),"complete sparse record");r.key=load(b);r.value=0;r.absolute=0;std::memcpy(&r.value,b+8,10);std::memcpy(&r.absolute,b+18,10);r.terms=load(b+28);require(std::isfinite(r.value)&&std::isfinite(r.absolute)&&r.absolute>=0&&r.terms>0,"finite sparse input");require(first||r.key>last,"sparse sorted unique input");for(int k=36;k<40;k++)require(b[k]==0,"sparse reserved bytes");last=r.key;first=false;remaining--;return true;}
};
}
