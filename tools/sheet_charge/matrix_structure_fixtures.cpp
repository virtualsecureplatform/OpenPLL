#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <filesystem>
int main(int argc,char**argv){try{
 require(argc==2,"usage: matrix_structure_fixtures OUTPUT");std::filesystem::path out=argv[1];
 std::vector<std::pair<std::string,std::vector<std::vector<long double>>>> cases{
  {"positive",{{1,-1,-1,1},{-1,3,1,-3},{-1,1,4,-4},{1,-3,-4,6}}},
  {"negative_diagonal",{{-1,1},{1,-1}}},
  {"negative_minor",{{-2,1,1},{1,1,-2},{1,-2,1}}},
  {"zero_diagonal_coupling",{{0,1,-1},{1,0,-1},{-1,-1,2}}},
  {"gauge_error",{{1,-1,-1,1},{-1,3.5L,1,-3},{-1,1,4,-4},{1,-3,-4,6}}},
  {"higher_order_indefinite",{{.255L,-.415L,-.085L,.245L},{-.415L,.695L,-.195L,-.085L},{-.085L,-.195L,.695L,-.415L},{.245L,-.085L,-.415L,.255L}}}
 };
 for(auto&[name,matrix]:cases){std::vector<sparse::Record> records;for(uint64_t i=0;i<matrix.size();i++)for(uint64_t j=i;j<matrix.size();j++)records.push_back({(i<<32)|j,matrix[i][j],std::fabs(matrix[i][j]),1});sparse::write((out/(name+".bin")).string(),records);}return 0;
 }catch(const std::exception&e){return 2;}}
