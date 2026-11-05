#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
int main(int argc,char**argv){try{
 require(argc==2,"usage: spatial_collapse_fixture OUTPUT");
 std::vector<sparse::Record> rows;long double matrix[4][4]={{1,-1,-1,1},{-1,3,1,-3},{-1,1,4,-4},{1,-3,-4,6}};
 for(uint64_t a=0;a<4;a++)for(uint64_t b=a;b<4;b++)rows.push_back({(a<<32)|b,matrix[a][b],std::fabs(matrix[a][b]),1});sparse::write(argv[1],rows);return 0;
 }catch(const std::exception&e){return 2;}}
