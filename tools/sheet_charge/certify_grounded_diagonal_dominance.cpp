#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <gmpxx.h>
#include <iostream>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Bits{uint64_t significand;int exponent;bool negative;};
static Bits bits(long double value){char raw[10];std::memcpy(raw,&value,10);uint64_t s=sparse::load(raw);uint16_t e;std::memcpy(&e,raw+8,2);return {s,((e&0x7fff)?int(e&0x7fff)-16383:1-16383)-63,bool(e&0x8000)};}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);uint64_t n=cfg.at("node_count").integer();require(n>1&&n<=10000000,"bounded grounded dimensions");uint64_t ground=cfg.at("ground_id").integer();require(ground<n,"ground index");double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"exact DD deadline");};std::string path=cfg.at("matrix").str();uint64_t entries=0;int minimum=100000,maximum=-100000;
 {sparse::Reader input(path);sparse::Record r;while(input.next(r)){if(entries++%10000==0)check();uint32_t i=r.key>>32,j=r.key&UINT32_MAX;require(j<n,"DD matrix bounds");if(i==ground||j==ground||r.value==0)continue;auto b=bits(r.value);minimum=std::min(minimum,b.exponent);maximum=std::max(maximum,b.exponent);}}
 if(minimum==100000)minimum=maximum=0;require(maximum-minimum<=512,"bounded exact DD exponent span");
 std::vector<mpz_class> margin(n),norm(n);uint64_t count=0,positive_edges=0,negative_diagonal=0;
 {sparse::Reader input(path);sparse::Record r;while(input.next(r)){if(count++%10000==0)check();uint32_t i=r.key>>32,j=r.key&UINT32_MAX;if(i==ground||j==ground||r.value==0)continue;auto b=bits(r.value);mpz_class magnitude;mpz_import(magnitude.get_mpz_t(),1,-1,sizeof(b.significand),0,0,&b.significand);mpz_mul_2exp(magnitude.get_mpz_t(),magnitude.get_mpz_t(),b.exponent-minimum);if(i==j){if(b.negative){margin[i]-=magnitude;negative_diagonal++;}else margin[i]+=magnitude;norm[i]+=magnitude;}else{positive_edges+=!b.negative;margin[i]-=magnitude;margin[j]-=magnitude;norm[i]+=magnitude;norm[j]+=magnitude;}}}require(count==entries,"DD complete passes");
 uint64_t positive=0,negative=0,zero=0,worst_row=0;mpq_class worst=0;
 for(uint64_t i=0;i<n;i++){if(i%10000==0)check();if(i==ground)continue;positive+=margin[i]>0;negative+=margin[i]<0;zero+=margin[i]==0;if(margin[i]<0){mpq_class ratio(-margin[i],norm[i]);ratio.canonicalize();if(ratio>worst){worst=ratio;worst_row=i;}}}
 Json r=Json::object();r["upper_entries"]=I(entries);r["node_count_including_reference"]=I(n);r["fixed_reference_id"]=I(ground);r["grounded_rows"]=I(n-1);r["common_binary_quantum_exponent"]=minimum;r["strictly_dominant_rows"]=I(positive);r["negative_dominance_margin_rows"]=I(negative);r["zero_dominance_margin_rows"]=I(zero);r["positive_grounded_offdiagonal_records"]=I(positive_edges);r["negative_grounded_diagonal_records"]=I(negative_diagonal);r["weak_diagonal_dominance_exact"]=negative==0;r["grounded_PSD_certified_by_exact_diagonal_dominance"]=negative==0;r["grounded_SPD_certified_by_strict_diagonal_dominance"]=negative==0&&zero==0;r["indefiniteness_proved"]=false;r["largest_negative_margin_to_row_l1_ratio_numerator"]=worst.get_num().get_str();r["largest_negative_margin_to_row_l1_ratio_denominator"]=worst.get_den().get_str();r["largest_negative_margin_to_row_l1_ratio_approximate"]=worst.get_d();r["largest_negative_margin_row"]=I(worst_row);r["largest_negative_margin_integer"]=negative?margin[worst_row].get_str():"0";r["matrix_modified"]=false;r["physical_RC_qualified"]=false;r["release_qualified"]=false;
 std::ofstream out(cfg.at("report").str());out<<r.dump()<<'\n';require(bool(out),"DD report");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
