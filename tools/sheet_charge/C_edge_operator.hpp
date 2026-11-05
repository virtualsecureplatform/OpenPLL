// Signed C incidence operator: stored diagonals are replaced by exact edge sums.
// Charge conservation does not establish passivity. No weights are clamped.
#pragma once
#include "sparse_runs_v2.hpp"
#include <omp.h>
#include <atomic>
#include <exception>
namespace capacitance {
class EdgeGraph {
 std::vector<uint64_t> offsets;
 std::vector<uint32_t> neighbors;
 std::vector<long double> weights;
public:
 uint64_t nodes=0,edges=0;
 template<class Check> EdgeGraph(const std::string&path,uint64_t node_count,uint64_t maximum_bytes,Check check):nodes(node_count){
  require(nodes>0&&nodes<=UINT32_MAX,"edge graph node count");std::vector<uint32_t> degree(nodes,0);uint64_t scanned=0;
  {sparse::Reader input(path);sparse::Record r;while(input.next(r)){if(scanned++%10000==0)check();uint32_t i=r.key>>32,j=r.key&UINT32_MAX;require(i<=j&&j<nodes,"edge graph input bounds");if(i==j||r.value==0)continue;require(degree[i]<UINT32_MAX&&degree[j]<UINT32_MAX,"edge graph degree bound");degree[i]++;degree[j]++;edges++;}}
  uint64_t bytes=(nodes+1)*sizeof(uint64_t)+nodes*sizeof(uint32_t)+2*edges*(sizeof(uint32_t)+sizeof(long double));require(bytes<=maximum_bytes,"edge graph bounded adjacency memory");offsets.resize(nodes+1);for(uint64_t i=0;i<nodes;i++)offsets[i+1]=offsets[i]+degree[i];require(offsets.back()==2*edges,"edge graph incidence count");neighbors.resize(2*edges);weights.resize(2*edges);std::fill(degree.begin(),degree.end(),0);uint64_t second=0;
  {sparse::Reader input(path);sparse::Record r;while(input.next(r)){if(second++%10000==0)check();uint32_t i=r.key>>32,j=r.key&UINT32_MAX;if(i==j||r.value==0)continue;require(j<nodes,"stable signed C graph second pass");for(int direction=0;direction<2;direction++){auto a=direction?j:i,b=direction?i:j;uint64_t slot=offsets[a]+degree[a]++;require(slot<offsets[a+1],"edge graph stable degree");neighbors[slot]=b;weights[slot]=-r.value;}}}require(scanned==second,"edge graph complete passes");for(uint64_t i=0;i<nodes;i++)require(offsets[i]+degree[i]==offsets[i+1],"edge graph row completeness");
 }
 template<class Check> std::vector<long double> apply(const std::vector<double>&voltage,Check check,int threads)const{
  require(threads>0&&threads<=32,"bounded edge graph thread count");require(voltage.size()==nodes,"edge graph vector dimension");for(auto v:voltage)require(std::isfinite(v),"finite edge graph input voltage");std::vector<long double> current(nodes);
  std::vector<std::exception_ptr> errors(threads);std::atomic<bool> cancelled{false};
  #pragma omp parallel for num_threads(threads) schedule(dynamic,4096)
  for(uint64_t i=0;i<nodes;i++){if(cancelled.load())continue;try{if(i%10000==0)check();sparse::Sum sum;long double vi=voltage[i];for(uint64_t k=offsets[i];k<offsets[i+1];k++){long double term=weights[k]*(vi-static_cast<long double>(voltage[neighbors[k]]));require(std::isfinite(term),"finite edge graph current");sum.add(term);}current[i]=sum.value();require(std::isfinite(current[i]),"finite edge graph row current");}catch(...){errors[omp_get_thread_num()]=std::current_exception();cancelled=true;}}for(auto&e:errors)if(e)std::rethrow_exception(e);return current;
 }
};
}
