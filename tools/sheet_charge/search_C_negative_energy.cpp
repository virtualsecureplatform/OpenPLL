// Two-pass Lanczos candidate search only. An independent exact energy test is mandatory.
#include "../charge_compiler/json.hpp"
#include "C_edge_operator_v2.hpp"
#include <time.h>
#include <iostream>
extern "C" void dstev_(char*,int*,double*,double*,double*,int*,double*,int*);
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static uint64_t random_bits(uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto c=Json::read(argv[1]);I count=c.at("node_count").integer();int threads=c.at("threads").integer(),limit=c.at("iterations").integer();
 require(count>1&&count<=10000000&&threads>0&&threads<=32&&limit>0&&limit<=512,"bounded C energy search");uint64_t n=count;
 double deadline=c.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"C energy search deadline");};
 auto zero=read_zero_C_mask(c.at("zero_rows").str(),n);int quantum=c.at("coefficient_quantum_exponent").integer();require(quantum>=-20000&&quantum<=20000,"diagonal quantum");
 std::vector<long double>scale(n);std::ifstream rows(c.at("diagonal_certificate").str());require(bool(rows),"search diagonal certificate");std::string line;uint64_t seen=0,active=0;
 while(std::getline(rows,line)){
  if(seen%10000==0)check();auto r=Json::parse(line);require(seen<n&&r.at("row").integer()==I(seen),"complete ordered search diagonals");
  auto text=r.at("conservative_diagonal_integer").str();char*end=nullptr;long double d=std::strtold(text.c_str(),&end);require(end==text.c_str()+text.size()&&std::isfinite(d)&&d>=0,"finite nonnegative certified diagonal");
  d=std::ldexp(d,quantum);require(std::isfinite(d)&&d>=0&&(!zero[seen]||d==0),"consistent source-zero search diagonal");
  if(seen&&d>0){scale[seen]=1/std::sqrt(d);active++;}seen++;
 }
 require(rows.eof()&&!rows.bad()&&seen==n&&active>0,"complete nontrivial search namespace");
 capacitance::EdgeGraph graph(c.at("matrix").str(),n,c.at("maximum_adjacency_bytes").integer(),check,c.at("zero_rows").str());
 auto initial=[&](){std::vector<double>v(n);long double norm=std::sqrt(static_cast<long double>(active));for(uint64_t i=1;i<n;i++)if(scale[i])v[i]=(random_bits(i)&1?1:-1)/norm;return v;};
 auto apply=[&](const std::vector<double>&v){
  std::vector<double>x(n);for(uint64_t i=0;i<n;i++)x[i]=v[i]*scale[i];auto y=graph.apply(x,check,threads);
  for(uint64_t i=0;i<n;i++)y[i]*=scale[i];return y;
 };
 std::vector<double>q=initial(),previous(n);std::vector<long double>alpha,beta;long double old_beta=0;
 int maximum=std::min<uint64_t>(limit,active);
 for(int k=0;k<maximum;k++){
  check();auto w=apply(q);sparse::Sum diagonal;
  for(uint64_t i=0;i<n;i++){w[i]-=old_beta*previous[i];diagonal.add(q[i]*w[i]);}
  long double a=diagonal.value();require(std::isfinite(a),"finite Lanczos diagonal");alpha.push_back(a);sparse::Sum square;
  for(uint64_t i=0;i<n;i++){w[i]-=a*q[i];square.add(w[i]*w[i]);}
  long double b=std::sqrt(square.value());require(std::isfinite(b)&&b>=0,"finite Lanczos norm");beta.push_back(b);
  Json progress=Json::object();progress["phase"]=std::string("candidate_Lanczos_search");progress["iterations_completed"]=k+1;progress["candidate_is_passivity_proof"]=false;
  {std::ofstream p(c.at("progress").str());p<<progress.dump()<<'\n';require(bool(p),"search progress write");}
  if(b==0)break;previous.swap(q);for(uint64_t i=0;i<n;i++)q[i]=w[i]/b;old_beta=b;
 }
 int m=alpha.size(),ld=m,info=0;std::vector<double>d(m),e(std::max(1,m-1)),z(m*m),work(std::max(1,2*m-2));
 for(int k=0;k<m;k++){d[k]=alpha[k];if(k+1<m)e[k]=beta[k];}char vectors='V';dstev_(&vectors,&m,d.data(),e.data(),z.data(),&ld,work.data(),&info);require(info==0&&std::isfinite(d[0]),"small tridiagonal eigensystem");
 q=initial();std::fill(previous.begin(),previous.end(),0);std::vector<long double>voltage(n);old_beta=0;
 for(int k=0;k<m;k++){
  check();for(uint64_t i=0;i<n;i++)voltage[i]+=z[k]*q[i]*scale[i];
  if(k+1<m){auto w=apply(q);previous.swap(q);for(uint64_t i=0;i<n;i++)q[i]=(w[i]-old_beta*q[i]-alpha[k]*previous[i])/beta[k];old_beta=beta[k];}
  Json progress=Json::object();progress["phase"]=std::string("candidate_vector_reconstruction");progress["iterations_completed"]=k+1;
  {std::ofstream p(c.at("progress").str());p<<progress.dump()<<'\n';require(bool(p),"replay progress write");}
 }
 long double largest=0;for(auto v:voltage){require(std::isfinite(v),"finite candidate voltage");largest=std::max(largest,std::fabs(v));}require(largest>0,"nonzero candidate vector");
 std::vector<double>result(n);for(uint64_t i=0;i<n;i++)result[i]=voltage[i]/largest;require(result[0]==0,"explicit reference zero retained");
 std::ofstream out(c.at("vector").str(),std::ios::binary);out.write("DDVEC001",8);char h[8];sparse::store(h,n);out.write(h,8);out.write((char*)result.data(),n*8);out.close();require(bool(out),"candidate vector close");
 Json report=Json::object();report["node_count"]=I(n);report["active_nonreference_positive_diagonal_states"]=I(active);report["iterations"]=m;
 report["minimum_tridiagonal_ritz_estimate"]=d[0];report["method"]=std::string("diagonally scaled, two-pass unreorthogonalized Lanczos; search only");
 report["candidate_is_passivity_or_indefiniteness_proof"]=false;report["exact_full_energy_verification_required"]=true;
 report["zero_diagonal_states_not_excited"]=true;report["full_matrix_passivity_verified"]=false;report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream output(c.at("report").str());output<<report.dump()<<'\n';output.close();require(bool(output),"Lanczos search report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
