#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <omp.h>
#include <iostream>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto c=Json::read(argv[1]);uint64_t n=c.at("node_count").integer(),ground=c.at("ground_id").integer();int threads=c.at("threads").integer(),limit=c.at("iterations").integer();require(n>1&&n<=10000000&&ground<n&&threads>0&&threads<=32&&limit>0&&limit<=4096,"bounded weighted search");double deadline=c.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"weighted search deadline");};
 std::vector<uint64_t> offsets(n+1);std::vector<uint32_t> degree(n);std::vector<long double> diagonal(n);uint64_t records=0;
 {sparse::Reader input(c.at("matrix").str());sparse::Record r;while(input.next(r)){if(records++%10000==0)check();uint32_t i=r.key>>32,j=r.key&UINT32_MAX;require(j<n,"weighted search matrix bounds");if(i==ground||j==ground)continue;if(i==j)diagonal[i]=r.value;else if(r.value!=0){require(degree[i]<UINT32_MAX&&degree[j]<UINT32_MAX,"weighted degree bounds");degree[i]++;degree[j]++;}}}
 for(uint64_t i=0;i<n;i++){require(i==ground||diagonal[i]>0,"positive grounded search diagonals");offsets[i+1]=offsets[i]+degree[i];}
 uint64_t count=offsets.back();require(c.at("maximum_adjacency_bytes").integer()>0&&uint64_t(c.at("maximum_adjacency_bytes").integer())>=(n+1)*8+n*36,"weighted memory minimum");require(count<=(c.at("maximum_adjacency_bytes").integer()-(n+1)*8-n*36)/12,"bounded weighted adjacency");std::vector<uint32_t> columns(count);std::vector<double> weights(count);std::fill(degree.begin(),degree.end(),0);
 {sparse::Reader input(c.at("matrix").str());sparse::Record r;uint64_t read=0;while(input.next(r)){if(read++%10000==0)check();uint32_t i=r.key>>32,j=r.key&UINT32_MAX;if(i==ground||j==ground||i==j||r.value==0)continue;double w=double(std::fabs(r.value));require(std::isfinite(w)&&w>0,"representable positive search weight");for(int d=0;d<2;d++){uint32_t a=d?j:i,b=d?i:j;uint64_t k=offsets[a]+degree[a]++;require(k<offsets[a+1],"weighted stable row");columns[k]=b;weights[k]=w;}}require(read==records,"weighted complete passes");}
 std::vector<double> x(n,1),next(n);x[ground]=0;double minratio=0,maximum=0;int completed=0;bool cap=false;
 for(int iteration=0;iteration<limit;iteration++){
  check();maximum=0;minratio=1;
  #pragma omp parallel for num_threads(threads) schedule(dynamic,4096) reduction(max:maximum) reduction(min:minratio)
  for(uint64_t i=0;i<n;i++){if(i==ground){next[i]=0;continue;}sparse::Sum s;for(uint64_t k=offsets[i];k<offsets[i+1];k++)s.add(static_cast<long double>(weights[k])*x[columns[k]]);long double sum=s.value(),diag=diagonal[i]*x[i];minratio=std::min(minratio,double((diag-sum)/(diag+sum)));next[i]=double(1+sum/diagonal[i]);maximum=std::max(maximum,next[i]);}
  completed=iteration+1;if(minratio>1e-10)break;if(!std::isfinite(maximum)||maximum>1e50){cap=true;break;}x.swap(next);
 }
 std::ofstream out(c.at("vector").str(),std::ios::binary);out.write("DDVEC001",8);char h[8];sparse::store(h,n);out.write(h,8);out.write((char*)x.data(),n*8);out.close();require(bool(out),"weighted vector close");Json r=Json::object();r["iterations_completed"]=completed;r["minimum_estimated_weighted_margin_ratio"]=minratio;r["growth_cap_reached"]=cap;r["node_count"]=I(n);r["threads"]=threads;r["candidate_is_passivity_proof"]=false;r["matrix_modified"]=false;std::ofstream report(c.at("report").str());report<<r.dump()<<'\n';require(bool(report),"search report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
