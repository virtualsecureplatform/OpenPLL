#pragma once
#include "sparse_runs_v2.hpp"
namespace charge {
inline void header(std::ostream&out,uint64_t rows,uint64_t columns,uint64_t count){out.write("QCRUN001",8);char h[24];sparse::store(h,rows);sparse::store(h+8,columns);sparse::store(h+16,count);out.write(h,24);}
inline void record(std::ostream&out,const sparse::Record&r,uint64_t rows,uint64_t columns){require((r.key>>32)<rows&&(r.key&UINT32_MAX)<columns,"rectangular charge index bounds");require(std::isfinite(r.value)&&std::isfinite(r.absolute)&&r.absolute>=0&&r.terms>0&&sparse::magnitude_bound(r.value,r.absolute),"charge coefficient bounds");char b[40]{};sparse::store(b,r.key);std::memcpy(b+8,&r.value,10);std::memcpy(b+18,&r.absolute,10);sparse::store(b+28,r.terms);out.write(b,40);}
inline void write(const std::string&path,uint64_t rows,uint64_t columns,const std::vector<sparse::Record>&values){std::ofstream out(path,std::ios::binary);require(bool(out),"charge output open");header(out,rows,columns,values.size());uint64_t last=0;bool first=true;for(auto&r:values){require(first||r.key>last,"unique sorted charge keys");record(out,r,rows,columns);last=r.key;first=false;}out.close();require(bool(out),"charge output close");}
class Reader{
 std::ifstream input;uint64_t remaining,last=0;bool first=true;
public:
 uint64_t rows,columns,count;
 explicit Reader(const std::string&path):input(path,std::ios::binary){require(bool(input),"charge input open");char h[32];input.read(h,32);require(bool(input)&&std::string(h,8)=="QCRUN001","rectangular charge header");rows=sparse::load(h+8);columns=sparse::load(h+16);count=remaining=sparse::load(h+24);require(rows>0&&columns>0&&rows<=UINT32_MAX&&columns<=UINT32_MAX,"charge dimensions");}
 bool next(sparse::Record&r){if(!remaining){char c;require(!input.get(c)&&input.eof(),"charge file trailing bytes");return false;}char b[40];input.read(b,40);require(bool(input),"complete charge coefficient");r.key=sparse::load(b);r.value=r.absolute=0;std::memcpy(&r.value,b+8,10);std::memcpy(&r.absolute,b+18,10);r.terms=sparse::load(b+28);require((r.key>>32)<rows&&(r.key&UINT32_MAX)<columns,"charge input bounds");require(std::isfinite(r.value)&&std::isfinite(r.absolute)&&r.absolute>=0&&r.terms>0&&sparse::magnitude_bound(r.value,r.absolute),"charge input coefficient bounds");require(first||r.key>last,"charge input key ordering");for(int k=36;k<40;k++)require(b[k]==0,"charge reserved bytes");first=false;last=r.key;remaining--;return true;}
};
}
