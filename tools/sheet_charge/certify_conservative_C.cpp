// Exact stored-coefficient certificate. Upstream quadrature and PSD are separate.
#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include <gmpxx.h>
#include <iostream>
#include <time.h>
using I = long long;
static double now() { timespec t{}; require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock"); return t.tv_sec+t.tv_nsec*1e-9; }
struct Dyadic { uint64_t significand; int exponent; bool negative; };
static Dyadic parts(long double v) {
 char raw[10]; std::memcpy(raw,&v,10); uint16_t e; std::memcpy(&e,raw+8,2);
 return {sparse::load(raw), ((e&0x7fff)?int(e&0x7fff)-16383:1-16383)-63, bool(e&0x8000)};
}
static mpq_class scaled(const mpz_class& n,int exponent) {
 mpq_class q(n); if(exponent>=0) mpq_mul_2exp(q.get_mpq_t(),q.get_mpq_t(),exponent);
 else mpq_div_2exp(q.get_mpq_t(),q.get_mpq_t(),-exponent); return q;
}
int main(int argc,char**argv) { try {
 require(argc==2,"usage CONFIG"); auto cfg=Json::read(argv[1]);
 auto count=cfg.at("node_count").integer(); require(count>0&&count<=10000000,"bounded node count");
 uint64_t nodes=count,entries=0; int minimum=100000,maximum=-100000;
 double deadline=cfg.at("deadline_uptime").num(); auto check=[&](){require(now()<deadline,"certificate deadline");};
 std::string path=cfg.at("matrix").str();
 { sparse::Reader input(path); sparse::Record r; while(input.next(r)) {
   if(entries++%10000==0) check(); require((r.key&UINT32_MAX)<nodes,"matrix node bounds");
   if(r.value==0) continue; auto b=parts(r.value); minimum=std::min(minimum,b.exponent); maximum=std::max(maximum,b.exponent);
 }}
 if(minimum==100000) minimum=maximum=0; require(maximum-minimum<=512,"bounded exact exponent span");
 std::vector<mpz_class> residual(nodes),norm(nodes),diagonal(nodes); uint64_t read=0,positive_edges=0,negative_edges=0;
 { sparse::Reader input(path); sparse::Record r; while(input.next(r)) {
   if(read++%10000==0) check(); uint32_t i=r.key>>32,j=r.key&UINT32_MAX;
   require(j<nodes,"stable matrix node bounds"); if(r.value==0) continue; auto b=parts(r.value);
   require(b.exponent>=minimum&&b.exponent<=maximum,"stable coefficient exponent");
   mpz_class magnitude; mpz_import(magnitude.get_mpz_t(),1,-1,sizeof(b.significand),0,0,&b.significand);
   mpz_mul_2exp(magnitude.get_mpz_t(),magnitude.get_mpz_t(),b.exponent-minimum);
   mpz_class v=b.negative?-magnitude:magnitude; residual[i]+=v; norm[i]+=magnitude;
   if(i==j) diagonal[i]=v; else { residual[j]+=v; norm[j]+=magnitude; positive_edges+=v>0; negative_edges+=v<0; }
 }}
 require(read==entries,"complete two-pass coverage");
 // Same coefficient criterion as compare_sparse_matrices.cpp, represented exactly.
 const mpq_class absolute(1e-8),relative(2e-12);
 uint64_t outside=0,nonzero=0,gauge_failed=0; mpz_class largest=0; mpq_class largest_ratio=0;
 std::ofstream rows(cfg.at("row_certificate").str()); require(bool(rows),"row certificate open");
 for(uint64_t i=0;i<nodes;i++) {
   if(i%10000==0) check(); mpz_class correction=-residual[i], corrected=diagonal[i]+correction;
   mpz_class mag=abs(correction); mpq_class old=scaled(diagonal[i],minimum),replacement=scaled(corrected,minimum);
   mpq_class old_abs=abs(old),new_abs=abs(replacement),error=scaled(mag,minimum);
   mpq_class bound=absolute+relative*(old_abs>new_abs?old_abs:new_abs),ratio=error/bound;
   outside+=error>bound; nonzero+=correction!=0; gauge_failed+=mag*1000000000000UL>norm[i];
   if(mag>largest) largest=mag; if(ratio>largest_ratio) largest_ratio=ratio;
   Json row=Json::object(); row["row"]=I(i); row["stored_diagonal_integer"]=diagonal[i].get_str();
   row["residual_integer"]=residual[i].get_str(); row["L1_integer"]=norm[i].get_str();
   row["diagonal_correction_integer"]=correction.get_str(); row["conservative_diagonal_integer"]=corrected.get_str();
   rows<<row.dump()<<'\n';
 }
 rows.close(); require(bool(rows),"row certificate close");
 Json report=Json::object(); report["node_count"]=I(nodes); report["upper_entries"]=I(entries);
 report["common_binary_quantum_exponent"]=minimum; report["nonzero_diagonal_corrections"]=I(nonzero);
 report["positive_offdiagonal_edges"]=I(positive_edges); report["negative_offdiagonal_edges"]=I(negative_edges);
 report["maximum_absolute_diagonal_correction_integer"]=largest.get_str();
 report["maximum_correction_over_coefficient_tolerance_exact"]=largest_ratio.get_str();
 report["rows_outside_coefficient_tolerance"]=I(outside); report["all_corrections_within_existing_coefficient_tolerance"]=outside==0;
 report["original_rows_outside_1e12_gauge_screen"]=I(gauge_failed);
 report["logical_operator_constant_nullspace_exact"]=true; report["stored_matrix_modified"]=false;
 report["upstream_integration_error_certified"]=false; report["full_matrix_passivity_verified"]=false;
 report["physical_RC_qualified"]=false; report["release_qualified"]=false;
 std::ofstream out(cfg.at("report").str()); out<<report.dump()<<'\n'; out.close(); require(bool(out),"report close");
 return 0;
 } catch(const std::exception&e) { std::cerr<<e.what()<<'\n'; return 1; }
}
