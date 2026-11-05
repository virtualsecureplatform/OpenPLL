// Necessary PSD test only; exact negative principal minors are constructive witnesses.
#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include "zero_C_mask.hpp"
#include <gmpxx.h>
#include <time.h>
#include <iostream>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static mpz_class exact(long double v,int quantum){
 char raw[10];std::memcpy(raw,&v,10);uint16_t e;std::memcpy(&e,raw+8,2);
 int shift=((e&0x7fff)?int(e&0x7fff)-16383:1-16383)-63-quantum;
 require(shift>=0&&shift<=512,"exact coefficient quantum");
 uint64_t sig=sparse::load(raw);mpz_class z;mpz_import(z.get_mpz_t(),1,-1,8,0,0,&sig);
 mpz_mul_2exp(z.get_mpz_t(),z.get_mpz_t(),shift);return e&0x8000?-z:z;
}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto c=Json::read(argv[1]);I n=c.at("node_count").integer(),q=c.at("coefficient_quantum_exponent").integer();
 require(n>1&&n<=10000000&&q>=-20000&&q<=20000,"bounded principal pairs");
 require(c.at("ground_id").integer()==0,"explicit reference zero required");
 double deadline=c.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"principal pair deadline");};
 auto zero=read_zero_C_mask(c.at("zero_rows").str(),n);std::vector<mpz_class>d(n),sum(n);
 std::ifstream rows(c.at("diagonal_certificate").str());require(bool(rows),"diagonal certificate");std::string line;I seen=0;
 while(std::getline(rows,line)){if(seen%10000==0)check();auto r=Json::parse(line);require(seen<n&&r.at("row").integer()==seen,"ordered complete diagonal rows");
  d[seen]=mpz_class(r.at("conservative_diagonal_integer").str());require(d[seen]>=0&&(!zero[seen]||d[seen]==0),"nonnegative consistent source-zero diagonal");sum[seen]=d[seen];seen++;}
 require(rows.eof()&&!rows.bad()&&seen==n,"complete diagonals");
 sparse::Reader input(c.at("matrix").str());sparse::Record r;I count=0,pairs=0,negative=0;Json witnesses=Json::array();
 while(input.next(r)){
  if(count++%10000==0)check();uint64_t i=r.key>>32,j=r.key&UINT32_MAX;require(j<uint64_t(n),"matrix bounds");
  if(i==j||r.value==0||zero[i]||zero[j])continue;
  mpz_class b=exact(r.value,q);sum[i]+=b;sum[j]+=b;if(i==0)continue;
  pairs++;mpz_class det=d[i]*d[j]-b*b;
  if(det>=0)continue;negative++;
  if(negative>32)continue;
  // Rational two-coordinate vector; all other coordinates, including reference, are zero.
  mpq_class x,y,energy;
  if(d[i]>0){x=mpq_class(b);y=-mpq_class(d[i]);}
  else{x=-mpq_class(d[j]+1,2*b);x.canonicalize();y=1;}
  energy=mpq_class(d[i])*x*x+2*mpq_class(b)*x*y+mpq_class(d[j])*y*y;
  energy.canonicalize();require(energy<0,"constructive exact negative energy");
  Json w=Json::object();w["i"]=I(i);w["j"]=I(j);w["a_integer"]=d[i].get_str();w["b_integer"]=b.get_str();w["d_integer"]=d[j].get_str();
  w["determinant_integer"]=det.get_str();w["x"]=x.get_str();w["y"]=y.get_str();w["energy_in_coefficient_quantum"]=energy.get_str();witnesses.push(w);
 }
 for(I i=0;i<n;i++){if(i%10000==0)check();require(sum[i]==0,"independent exact implicit diagonal identity");}
 Json out=Json::object();out["node_count"]=n;out["source_upper_entries"]=count;out["tested_nonzero_grounded_pairs"]=pairs;
 out["negative_principal_pairs"]=negative;out["witnesses"]=witnesses;out["coefficient_quantum_exponent"]=q;
 out["exact_implicit_diagonal_identity_verified"]=true;out["indefiniteness_proved"]=negative>0;
 out["full_matrix_passivity_verified"]=false;out["passing_necessary_screen_is_not_PSD_certificate"]=true;
 out["physical_RC_qualified"]=false;out["release_qualified"]=false;
 std::ofstream report(c.at("report").str());report<<out.dump()<<'\n';report.close();require(bool(report),"report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
