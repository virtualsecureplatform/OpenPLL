#include "../charge_compiler/json.hpp"
#include "sparse_runs.hpp"
#include <filesystem>
#include <iostream>
int main(int argc,char**argv){try{
 require(argc==2,"usage: sparse_run_controls OUTPUT");std::filesystem::path out=argv[1];
 sparse::Sum sum;sum.add(1e30L);sum.add(1);sum.add(-1e30L);require(sum.value()==1,"compensated severe cancellation");
 sparse::write((out/"a.bin").string(),{{0,1e30L,1e30L,1},{1,-5,5,1}});
 sparse::write((out/"b.bin").string(),{{0,1,1,1},{2,7,7,1}});
 sparse::write((out/"c.bin").string(),{{0,-1e30L,1e30L,1},{1,5,5,1}});
 std::cout<<"{\"severe_cancellation_preserved\":true}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
