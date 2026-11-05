// Structural fill benchmark only. No numeric factorization, solve or passivity claim.
#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include "zero_C_mask.hpp"
#include <cholmod.h>
#include <time.h>
#include <iostream>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static std::string decimal(unsigned __int128 x){std::string s;do{s.push_back('0'+x%10);x/=10;}while(x);std::reverse(s.begin(),s.end());return s;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);I count=cfg.at("node_count").integer();require(count>1&&count<=10000000,"bounded factor pattern");uint64_t n=count;
 double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"factor pattern deadline");};
 auto zero=read_zero_C_mask(cfg.at("zero_rows").str(),n);std::vector<uint64_t>counts(n,1);uint64_t read=0,edges=0;
 {sparse::Reader input(cfg.at("matrix").str());sparse::Record r;while(input.next(r)){
  if(read++%10000==0)check();uint64_t i=r.key>>32,j=r.key&UINT32_MAX;require(j<n,"factor pattern node bounds");
  if(i!=j&&r.value!=0&&!zero[i]&&!zero[j]){counts[j]++;edges++;}
 }}
 uint64_t nz=n+edges;require(nz<=uint64_t(INT64_MAX)&&8*(nz+n+1)<=uint64_t(cfg.at("maximum_pattern_bytes").integer()),"bounded CSC pattern allocation");
 cholmod_common common{};require(cholmod_l_start(&common),"CHOLMOD long initialization");
 common.nmethods=1;common.method[0].ordering=CHOLMOD_AMD;common.postorder=1;common.supernodal=CHOLMOD_SIMPLICIAL;
 auto*a=cholmod_l_allocate_sparse(n,n,nz,1,1,1,CHOLMOD_PATTERN,&common);require(a&&a->itype==CHOLMOD_LONG,"CHOLMOD int64 pattern allocation");
 auto*p=static_cast<int64_t*>(a->p);auto*indices=static_cast<int64_t*>(a->i);p[0]=0;
 for(uint64_t j=0;j<n;j++){p[j+1]=p[j]+counts[j];counts[j]=p[j];}
 {sparse::Reader input(cfg.at("matrix").str());sparse::Record r;uint64_t again=0,kept=0;while(input.next(r)){
  if(again++%10000==0)check();uint64_t i=r.key>>32,j=r.key&UINT32_MAX;require(j<n,"stable factor pattern bounds");
  if(i!=j&&r.value!=0&&!zero[i]&&!zero[j]){require(counts[j]<uint64_t(p[j+1]),"pattern column bound");indices[counts[j]++]=i;kept++;}
 }require(again==read&&kept==edges,"stable complete pattern passes");}
 for(uint64_t j=0;j<n;j++){indices[counts[j]++]=j;require(counts[j]==uint64_t(p[j+1]),"complete upper pattern column");}
 check();double start=now();auto*l=cholmod_l_analyze(a,&common);double elapsed=now()-start;
 require(l&&common.status==CHOLMOD_OK&&l->itype==CHOLMOD_LONG&&!l->is_super,"complete simplicial symbolic factor");
 auto*columns=static_cast<int64_t*>(l->ColCount);auto*perm=static_cast<int64_t*>(l->Perm);unsigned __int128 total=0,flops=0;uint64_t largest=0;
 Json column_counts=Json::array(),permutation=Json::array();
 for(uint64_t j=0;j<n;j++){if(j%10000==0)check();require(columns[j]>0&&uint64_t(columns[j])<=n&&perm[j]>=0&&uint64_t(perm[j])<n,"valid symbolic columns/permutation");
  total+=columns[j];flops+=static_cast<unsigned __int128>(columns[j])*columns[j];largest=std::max(largest,uint64_t(columns[j]));
  if(n<=128){column_counts.push(I(columns[j]));permutation.push(I(perm[j]));}}
 Json r=Json::object();r["node_count"]=I(n);r["source_upper_records"]=I(read);r["pattern_upper_nonzeros"]=I(nz);
 r["symbolic_factor_nonzeros_exact"]=decimal(total);r["predicted_simplicial_L_index_value_bytes_exact"]=decimal(total*16);
 r["sum_squared_column_counts_exact"]=decimal(flops);r["largest_factor_column"]=I(largest);r["analysis_seconds_nonisolated"]=elapsed;
 r["CHOLMOD_peak_bytes"]=I(common.memory_usage);r["ordering"]=std::string("AMD with weighted postorder; simplicial symbolic analysis only");
 if(n<=128){r["column_counts"]=column_counts;r["permutation"]=permutation;}
 r["numeric_factorization_started"]=false;r["KLU_fill_or_memory_bound_proved"]=false;r["G_pattern_included"]=false;
 r["full_matrix_passivity_verified"]=false;r["native_solver_qualified"]=false;r["physical_RC_qualified"]=false;r["release_qualified"]=false;
 require(cholmod_l_free_factor(&l,&common)&&cholmod_l_free_sparse(&a,&common)&&cholmod_l_finish(&common),"CHOLMOD close");
 std::ofstream output(cfg.at("report").str());output<<r.dump()<<'\n';output.close();require(bool(output),"pattern report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
