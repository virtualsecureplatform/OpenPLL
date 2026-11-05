#include "../charge_compiler/json.hpp"
#include "sparse_run_slice.hpp"
#include <atomic>
#include <memory>
#include <iostream>
#include <omp.h>
#include <time.h>
using I=long long;using Real=long double;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Row{sparse::Sum value,l1;};
int main(int argc,char**argv){try{
 require(argc==2,"usage: audit_sparse_matrix CONFIG");auto cfg=Json::read(argv[1]);auto path=cfg.at("matrix").str();I nodes=cfg.at("node_count").integer(),threads=cfg.at("threads").integer();require(nodes>0&&nodes<100000000&&threads>0&&threads<=16,"bounded matrix audit dimensions");
 uint64_t memory=uint64_t(nodes)*(uint64_t(threads)*sizeof(Row)+2*sizeof(Real)+sizeof(std::atomic<uint8_t>));require(memory<=uint64_t(cfg.at("maximum_dense_bytes").integer()),"matrix audit dense memory budget");double deadline=cfg.at("deadline_uptime").num();Real gauge_limit=cfg.at("scaled_charge_residual_limit").num();require(gauge_limit>0&&gauge_limit<=1e-12L,"strict charge residual limit");
 sparse::SliceReader header(path,0,0);uint64_t total=header.total;std::vector<Real> diagonal(nodes),diagonal_absolute(nodes);auto seen=std::make_unique<std::atomic<uint8_t>[]>(nodes);for(I i=0;i<nodes;i++)seen[i]=0;
 std::vector<std::vector<Row>> rows(threads);std::vector<std::exception_ptr> errors(threads);std::vector<uint64_t> counts(threads),first(threads),last(threads);
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{auto& values=rows[part];values.resize(nodes);sparse::SliceReader input(path,total*part/threads,total*(part+1)/threads);sparse::Record r;
  while(input.next(r)){if(counts[part]%10000==0)require(now()<deadline,"matrix audit charge deadline");uint64_t i=r.key>>32,j=r.key&UINT32_MAX;require(j<uint64_t(nodes),"matrix audit node bounds");if(!counts[part])first[part]=r.key;last[part]=r.key;counts[part]++;
   if(i==j){require(seen[i].exchange(1)==0,"unique matrix diagonal");diagonal[i]=r.value;diagonal_absolute[i]=r.absolute;}
   values[i].value.add(r.value);values[i].l1.add(std::fabs(r.value));if(i!=j){values[j].value.add(r.value);values[j].l1.add(std::fabs(r.value));}
  }
 }catch(...){errors[part]=std::current_exception();}}
 for(auto& e:errors)if(e)std::rethrow_exception(e);uint64_t entries=0,prior=0;bool have=false;for(I part=0;part<threads;part++){if(counts[part]){require(!have||prior<first[part],"matrix audit global slice order");prior=last[part];have=true;}entries+=counts[part];}require(entries==total,"matrix audit complete entry coverage");
 Real maximum_residual=0;I maximum_row=0,zero_rows=0,negative_diagonals=0,significant_negative_diagonals=0;
 for(I i=0;i<nodes;i++){if(i%10000==0)require(now()<deadline,"matrix audit row reduction deadline");sparse::Sum value,l1;for(I part=0;part<threads;part++){value.add(rows[part][i].value.value());l1.add(rows[part][i].l1.value());}Real norm=l1.value(),residual=norm?std::fabs(value.value())/norm:0;zero_rows+=norm==0;if(residual>maximum_residual){maximum_residual=residual;maximum_row=i;}negative_diagonals+=diagonal[i]<0;significant_negative_diagonals+=diagonal[i]<-256*std::numeric_limits<Real>::epsilon()*diagonal_absolute[i];}
 rows.clear();rows.shrink_to_fit();std::vector<uint64_t> bad_minors(threads);std::vector<Json> witnesses(threads,Json::array());
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{sparse::SliceReader input(path,total*part/threads,total*(part+1)/threads);sparse::Record r;uint64_t read=0;
  while(input.next(r)){if(read++%10000==0)require(now()<deadline,"matrix audit principal minor deadline");uint64_t i=r.key>>32,j=r.key&UINT32_MAX;if(i==j)continue;Real a=diagonal[i],b=diagonal[j],det=a*b-r.value*r.value;
   Real eps=256*std::numeric_limits<Real>::epsilon(),ea=eps*diagonal_absolute[i],eb=eps*diagonal_absolute[j],ec=eps*r.absolute;
   Real uncertainty=std::fabs(b)*ea+std::fabs(a)*eb+2*std::fabs(r.value)*ec+ea*eb+ec*ec+32*std::numeric_limits<Real>::epsilon()*(std::fabs(a*b)+r.value*r.value);
   if(det < -uncertainty){bad_minors[part]++;if(witnesses[part].arr().size()<8)witnesses[part].push(Json::Array{I(i),I(j),double(a),double(b),double(r.value),double(det),double(uncertainty)});}
  }
 }catch(...){errors[part]=std::current_exception();}}
 for(auto& e:errors)if(e)std::rethrow_exception(e);uint64_t minors=0;Json examples=Json::array();for(I part=0;part<threads;part++){minors+=bad_minors[part];for(auto& row:witnesses[part].arr())if(examples.arr().size()<32)examples.push(row);}
 Json result=Json::object();result["upper_entries"]=I(total);result["node_count"]=nodes;result["maximum_scaled_charge_residual"]=double(maximum_residual);result["maximum_charge_residual_row"]=maximum_row;result["charge_conservation_within_limit"]=maximum_residual<=gauge_limit;result["zero_coefficient_rows"]=zero_rows;result["negative_diagonal_records"]=negative_diagonals;result["significant_negative_diagonal_records"]=significant_negative_diagonals;result["significant_negative_two_by_two_minors"]=I(minors);result["principal_minor_examples"]=examples;result["necessary_checks_pass"]=maximum_residual<=gauge_limit&&significant_negative_diagonals==0&&minors==0;
 result["dense_working_bytes_bound"]=I(memory);result["full_matrix_passivity_verified"]=false;result["global_passivity_qualified"]=false;result["physical_RC_qualified"]=false;result["release_qualified"]=false;
 std::ofstream output(cfg.at("report").str());output<<result.dump()<<'\n';output.close();require(bool(output),"matrix audit report close");std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
