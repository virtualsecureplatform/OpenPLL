// Full logical C passivity certificate: exact diagonal identity and exact weighted DD.
#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include "zero_C_mask.hpp"
#include <gmpxx.h>
#include <iostream>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Bits{uint64_t significand;int exponent;bool negative;};
static Bits bits(long double value){char raw[10];std::memcpy(raw,&value,10);uint16_t e;std::memcpy(&e,raw+8,2);return {sparse::load(raw),((e&0x7fff)?int(e&0x7fff)-16383:1-16383)-63,bool(e&0x8000)};}
static mpz_class integer(uint64_t value){mpz_class n;mpz_import(n.get_mpz_t(),1,-1,sizeof(value),0,0,&value);return n;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);I count=cfg.at("node_count").integer();require(count>1&&count<=10000000,"bounded logical C dimension");uint64_t n=count;
 require(cfg.at("ground_id").integer()==0,"explicit reference 0 required");double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"logical weighted DD deadline");};
 auto zero=read_zero_C_mask(cfg.at("zero_rows").str(),n);I quantum=cfg.at("coefficient_quantum_exponent").integer();require(quantum>=-20000&&quantum<=20000,"coefficient quantum bound");
 std::ifstream input(cfg.at("vector").str(),std::ios::binary);char header[16]{};input.read(header,16);require(bool(input)&&std::string(header,8)=="DDVEC001"&&sparse::load(header+8)==n,"logical DD vector header");
 std::vector<double>z(n);input.read(reinterpret_cast<char*>(z.data()),8*n);require(bool(input),"complete logical DD vector");char extra;require(!input.get(extra)&&input.eof(),"logical vector trailing bytes");
 int minz=100000,maxz=-100000;std::vector<Bits>weights(n);
 for(uint64_t i=0;i<n;i++){require(std::isfinite(z[i])&&(i==0?z[i]==0:z[i]>0),"strictly positive non-reference logical DD weights");weights[i]=bits(z[i]);if(i){minz=std::min(minz,weights[i].exponent);maxz=std::max(maxz,weights[i].exponent);}}
 require(maxz-minz<=512,"bounded exact weight exponent span");
 std::vector<mpz_class>rowsum(n),margin(n),norm(n);uint64_t rows=0,negative_diagonal=0;
 std::ifstream diagonals(cfg.at("diagonal_certificate").str());require(bool(diagonals),"logical diagonal certificate");std::string line;
 auto weighted=[&](const mpz_class&m,uint64_t j){mpz_class value=m*integer(weights[j].significand);mpz_mul_2exp(value.get_mpz_t(),value.get_mpz_t(),weights[j].exponent-minz);return value;};
 while(std::getline(diagonals,line)){
  if(rows%10000==0)check();auto row=Json::parse(line);require(rows<n&&row.at("row").integer()==I(rows),"logical diagonal coverage/order");
  mpz_class d(row.at("conservative_diagonal_integer").str());require(!zero[rows]||d==0,"source-zero diagonal must be exactly zero");rowsum[rows]=d;
  if(rows){margin[rows]=weighted(d,rows);norm[rows]=abs(margin[rows]);negative_diagonal+=d<0;}rows++;
 }
 require(diagonals.eof()&&!diagonals.bad()&&rows==n,"all logical diagonals supplied");
 sparse::Reader matrix(cfg.at("matrix").str());sparse::Record record;uint64_t entries=0,positive_edges=0;
 while(matrix.next(record)){
  if(entries++%10000==0)check();uint64_t i=record.key>>32,j=record.key&UINT32_MAX;require(j<n,"logical DD matrix bounds");
  if(i==j||record.value==0||zero[i]||zero[j])continue;auto b=bits(record.value);require(b.exponent>=quantum&&b.exponent-quantum<=512,"exact source coefficient quantum");
  mpz_class magnitude=integer(b.significand);mpz_mul_2exp(magnitude.get_mpz_t(),magnitude.get_mpz_t(),b.exponent-quantum);
  if(b.negative){rowsum[i]-=magnitude;rowsum[j]-=magnitude;}else{rowsum[i]+=magnitude;rowsum[j]+=magnitude;}
  if(i==0)continue;positive_edges+=!b.negative;mpz_class a=weighted(magnitude,j),c=weighted(magnitude,i);
  margin[i]-=a;margin[j]-=c;norm[i]+=a;norm[j]+=c;
 }
 uint64_t positive=0,negative=0,zeros=0,worst_row=0;mpq_class worst=0;
 for(uint64_t i=0;i<n;i++){
  if(i%10000==0)check();require(rowsum[i]==0,"exact implicit diagonal does not match retained source edges");if(i==0)continue;
  positive+=margin[i]>0;negative+=margin[i]<0;zeros+=margin[i]==0;
  if(margin[i]<0){require(norm[i]>0,"negative margin norm");mpq_class ratio(-margin[i],norm[i]);ratio.canonicalize();if(ratio>worst){worst=ratio;worst_row=i;}}
 }
 Json report=Json::object();report["node_count"]=I(n);report["source_upper_entries"]=I(entries);report["ground_id"]=0;
 report["strictly_dominant_rows"]=I(positive);report["zero_margin_rows"]=I(zeros);report["negative_margin_rows"]=I(negative);report["negative_diagonal_rows"]=I(negative_diagonal);
 report["positive_grounded_offdiagonal_records"]=I(positive_edges);report["largest_negative_margin_ratio_exact"]=worst.get_str();report["largest_negative_margin_row"]=I(worst_row);
 report["exact_implicit_diagonal_identity_verified"]=true;report["constant_nullspace_verified_exactly"]=true;
 report["full_matrix_passivity_verified"]=negative==0;report["grounded_SPD_verified"]=negative==0&&zeros==0;
 report["certificate"]=std::string("exact GMP weighted diagonal dominance of the full grounded logical operator plus exact constant nullspace");
 report["failed_sufficient_certificate_is_not_indefiniteness"]=true;report["indefiniteness_proved"]=false;report["physical_RC_qualified"]=false;report["release_qualified"]=false;
 std::ofstream out(cfg.at("report").str());out<<report.dump()<<'\n';out.close();require(bool(out),"logical DD report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
