#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <filesystem>
int main(int argc,char**argv){try{require(argc==2,"printed_EXT_fixtures OUTPUT");std::string out=argv[1];
 for(int changed=0;changed<2;changed++){long double m[4][4]{};auto edge=[&](int a,int b,long double v){m[a][a]+=v;m[b][b]+=v;m[a][b]-=v;m[b][a]-=v;};edge(0,1,1.23456789L);edge(0,3,.0001L);edge(1,2,89.1970802919708L+changed);edge(1,3,-.0009370535299867L);edge(2,3,999999.9L);std::vector<sparse::Record> rows;for(uint64_t i=0;i<4;i++)for(uint64_t j=i;j<4;j++)rows.push_back({i<<32|j,m[i][j],std::fabs(m[i][j]),1});sparse::write(out+(changed?"/changed.bin":"/actual.bin"),rows);}return 0;
 }catch(const std::exception&e){return 2;}}
