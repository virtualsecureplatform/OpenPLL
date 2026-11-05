#pragma once
#include "sparse_runs_v2.hpp"
#include <omp.h>
#include <atomic>
#include <exception>
// Applies stored symmetric coefficients, including diagonals and either off-diagonal sign.
namespace symmetric_operator {
class Matrix {
 std::vector<uint64_t> offsets;
 std::vector<uint32_t> columns;
 std::vector<long double> values;
public:
 uint64_t nodes=0,records=0;
 template<class Check> Matrix(const std::string&path,uint64_t n,uint64_t maximum_bytes,Check check):nodes(n){
  require(nodes>0&&nodes<=UINT32_MAX,"symmetric operator dimensions");
  std::vector<uint32_t> degree(nodes,0);uint64_t count=0;
  {sparse::Reader input(path);sparse::Record r;while(input.next(r)){
   if(records++%10000==0)check();uint32_t i=r.key>>32,j=r.key&UINT32_MAX;
   require(i<=j&&j<nodes,"symmetric operator input bounds");
   require(degree[i]<UINT32_MAX,"symmetric operator degree overflow");degree[i]++;count++;
   if(i!=j){require(degree[j]<UINT32_MAX,"symmetric operator degree overflow");degree[j]++;count++;}
  }}
  require(count<=(UINT64_MAX-(nodes+1)*8-nodes*4)/20,"symmetric operator allocation overflow");
  require((nodes+1)*8+nodes*4+count*(sizeof(uint32_t)+sizeof(long double))<=maximum_bytes,"symmetric operator bounded memory");
  offsets.resize(nodes+1);for(uint64_t i=0;i<nodes;i++)offsets[i+1]=offsets[i]+degree[i];
  columns.resize(count);values.resize(count);std::fill(degree.begin(),degree.end(),0);uint64_t second=0;
  {sparse::Reader input(path);sparse::Record r;while(input.next(r)){
   if(second++%10000==0)check();uint32_t i=r.key>>32,j=r.key&UINT32_MAX;
   require(i<=j&&j<nodes,"symmetric operator second pass bounds");
   auto put=[&](uint32_t row,uint32_t col){uint64_t k=offsets[row]+degree[row]++;require(k<offsets[row+1],"symmetric operator stable degrees");columns[k]=col;values[k]=r.value;};
   put(i,j);if(i!=j)put(j,i);
  }}require(second==records,"symmetric operator complete passes");
  for(uint64_t i=0;i<nodes;i++)require(offsets[i]+degree[i]==offsets[i+1],"symmetric operator complete row");
 }
 template<class Check> std::vector<long double> apply(const std::vector<double>&x,Check check,int threads)const{
  require(threads>=1&&threads<=32,"symmetric operator thread bound");require(x.size()==nodes,"symmetric operator vector dimension");
  for(auto v:x)require(std::isfinite(v),"symmetric operator finite input");
  std::vector<long double> y(nodes);std::vector<std::exception_ptr> errors(threads);std::atomic<bool> cancelled{false};
  #pragma omp parallel for num_threads(threads) schedule(dynamic,4096)
  for(uint64_t i=0;i<nodes;i++){
   if(cancelled.load())continue;
   try{if(i%10000==0)check();sparse::Sum sum;
    for(uint64_t k=offsets[i];k<offsets[i+1];k++){long double term=values[k]*static_cast<long double>(x[columns[k]]);require(std::isfinite(term),"symmetric operator finite product");sum.add(term);}
    y[i]=sum.value();require(std::isfinite(y[i]),"symmetric operator finite output");
   }catch(...){errors[omp_get_thread_num()]=std::current_exception();cancelled=true;}
  }for(auto&e:errors)if(e)std::rethrow_exception(e);return y;
 }
};
}
