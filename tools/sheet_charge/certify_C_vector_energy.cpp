// Exact full signed-edge energy of a finite binary64 voltage vector.
#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include "zero_C_mask.hpp"
#include <gmpxx.h>
#include <time.h>
#include <iostream>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Bits{uint64_t significand;int exponent;bool negative;};
static Bits bits(long double value){char raw[10];std::memcpy(raw,&value,10);uint16_t e;std::memcpy(&e,raw+8,2);return {sparse::load(raw),((e&0x7fff)?int(e&0x7fff)-16383:1-16383)-63,bool(e&0x8000)};}
static mpz_class integer(Bits b,int quantum){require(b.exponent>=quantum&&b.exponent-quantum<=4096,"bounded exact binary quantum");mpz_class z;mpz_import(z.get_mpz_t(),1,-1,8,0,0,&b.significand);mpz_mul_2exp(z.get_mpz_t(),z.get_mpz_t(),b.exponent-quantum);return b.negative?-z:z;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto c=Json::read(argv[1]);I count=c.at("node_count").integer(),quantum=c.at("coefficient_quantum_exponent").integer();
 require(count>1&&count<=10000000&&quantum>=-20000&&quantum<=20000,"bounded exact C energy");uint64_t n=count;
 double deadline=c.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"exact C energy deadline");};
 auto zero=read_zero_C_mask(c.at("zero_rows").str(),n);std::ifstream input(c.at("vector").str(),std::ios::binary);char h[16];input.read(h,16);
 require(bool(input)&&std::string(h,8)=="DDVEC001"&&sparse::load(h+8)==n,"signed energy vector header");std::vector<double>v(n);input.read((char*)v.data(),n*8);char extra;
 require(bool(input)&&!input.get(extra)&&input.eof(),"complete signed energy vector");require(v[0]==0,"explicit reference 0 voltage required");
 int minimum=100000,maximum=-100000;for(auto x:v){require(std::isfinite(x),"finite signed energy vector");if(x!=0){auto b=bits(x);minimum=std::min(minimum,b.exponent);maximum=std::max(maximum,b.exponent);}}
 if(minimum==100000)minimum=maximum=0;require(maximum-minimum<=4096,"bounded vector exponent span");
 std::vector<mpz_class>x(n);for(uint64_t i=0;i<n;i++){if(i%10000==0)check();if(v[i]!=0)x[i]=integer(bits(v[i]),minimum);}
 sparse::Reader matrix(c.at("matrix").str());sparse::Record r;uint64_t records=0,edges=0;mpz_class energy=0,l1=0;
 while(matrix.next(r)){
  if(records++%10000==0)check();uint64_t i=r.key>>32,j=r.key&UINT32_MAX;require(j<n,"signed energy matrix bounds");
  if(i==j||r.value==0||zero[i]||zero[j])continue;edges++;mpz_class difference=x[i]-x[j];if(difference==0)continue;
  mpz_class contribution=-integer(bits(r.value),quantum)*difference*difference;energy+=contribution;l1+=abs(contribution);
 }
 Json report=Json::object();report["node_count"]=I(n);report["source_upper_records"]=I(records);report["retained_nonzero_edges"]=I(edges);
 report["energy_integer"]=energy.get_str();report["absolute_contribution_integer"]=l1.get_str();
 report["coefficient_quantum_exponent"]=quantum;report["voltage_quantum_exponent"]=minimum;report["energy_quantum_exponent"]=quantum+2*minimum;
 report["energy_definition"]=std::string("sum over retained i<j: -stored_Cij*(binary64_xi-binary64_xj)^2; raw C to F factor is positive 1e-18");
 report["exact_full_operator_vector_energy_verified"]=true;report["indefiniteness_proved"]=energy<0;
 report["nonnegative_vector_energy_does_not_prove_PSD"]=true;report["full_matrix_passivity_verified"]=false;
 report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream output(c.at("report").str());output<<report.dump()<<'\n';output.close();require(bool(output),"exact energy report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
