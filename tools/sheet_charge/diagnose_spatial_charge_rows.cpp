#include "../charge_compiler/json.hpp"
#include "sparse_run_slice.hpp"
#include <atomic>
#include <memory>
#include <iostream>
#include <omp.h>
#include <time.h>
#include <iomanip>
#include <sstream>
using I=long long;using Real=long double;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Row{sparse::Sum value,l1,source_absolute;};
int main(int argc,char**argv){try{
 if(argc==3&&std::string(argv[1])=="--fixture"){std::vector<sparse::Record> rows{{0,1e-30L,1.0L,10},{1,-1e-30L,1.0L,10},{(uint64_t(1)<<32)|1,1e-30L,1.0L,10},{(uint64_t(2)<<32)|2,1e-30L,1.0L,10},{(uint64_t(3)<<32)|3,1e-3L,1.0L,10}};sparse::write(argv[2],rows);return 0;}
 require(argc==2,"usage: diagnose_spatial_charge_rows CONFIG");auto cfg=Json::read(argv[1]);auto path=cfg.at("matrix").str();I nodes=cfg.at("node_count").integer(),threads=cfg.at("threads").integer();require(nodes>0&&nodes<100000000&&threads>0&&threads<=16,"bounded matrix audit dimensions");
 uint64_t memory=uint64_t(nodes)*(uint64_t(threads)*sizeof(Row)+2*sizeof(Real)+sizeof(std::atomic<uint8_t>));require(memory<=uint64_t(cfg.at("maximum_dense_bytes").integer()),"matrix audit dense memory budget");double deadline=cfg.at("deadline_uptime").num();Real gauge_limit=cfg.at("scaled_charge_residual_limit").num();require(gauge_limit>0&&gauge_limit<=1e-12L,"strict charge residual limit");
 sparse::SliceReader header(path,0,0);uint64_t total=header.total;std::vector<Real> diagonal(nodes),diagonal_absolute(nodes);auto seen=std::make_unique<std::atomic<uint8_t>[]>(nodes);for(I i=0;i<nodes;i++)seen[i]=0;
 std::vector<std::vector<Row>> rows(threads);std::vector<std::exception_ptr> errors(threads);std::vector<uint64_t> counts(threads),first(threads),last(threads);
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{auto& values=rows[part];values.resize(nodes);sparse::SliceReader input(path,total*part/threads,total*(part+1)/threads);sparse::Record r;
  while(input.next(r)){if(counts[part]%10000==0)require(now()<deadline,"matrix audit charge deadline");uint64_t i=r.key>>32,j=r.key&UINT32_MAX;require(j<uint64_t(nodes),"matrix audit node bounds");if(!counts[part])first[part]=r.key;last[part]=r.key;counts[part]++;
   if(i==j){require(seen[i].exchange(1)==0,"unique matrix diagonal");diagonal[i]=r.value;diagonal_absolute[i]=r.absolute;}
   values[i].value.add(r.value);values[i].l1.add(std::fabs(r.value));values[i].source_absolute.add(r.absolute);if(i!=j){values[j].value.add(r.value);values[j].l1.add(std::fabs(r.value));values[j].source_absolute.add(r.absolute);}
  }
 }catch(...){errors[part]=std::current_exception();}}
 for(auto& e:errors)if(e)std::rethrow_exception(e);uint64_t entries=0,prior=0;bool have=false;for(I part=0;part<threads;part++){if(counts[part]){require(!have||prior<first[part],"matrix audit global slice order");prior=last[part];have=true;}entries+=counts[part];}require(entries==total,"matrix audit complete entry coverage");
 Real maximum_residual=0,maximum_absolute=0,maximum_source_scaled=0;I maximum_row=0,zero_rows=0,bad_reduced=0,unexplained=0;Json examples=Json::array();
 auto precise=[](Real x){std::ostringstream stream;stream<<std::setprecision(std::numeric_limits<Real>::max_digits10)<<x;return stream.str();};
 for(I i=0;i<nodes;i++){if(i%10000==0)require(now()<deadline,"row diagnostic deadline");sparse::Sum value,l1,source_absolute;for(I part=0;part<threads;part++){value.add(rows[part][i].value.value());l1.add(rows[part][i].l1.value());source_absolute.add(rows[part][i].source_absolute.value());}Real sum=value.value(),norm=l1.value(),original=source_absolute.value(),residual=norm?std::fabs(sum)/norm:0,scaled=original?std::fabs(sum)/original:0;zero_rows+=norm==0;bool reduced_bad=residual>gauge_limit,not_roundoff=std::fabs(sum)>256*std::numeric_limits<Real>::epsilon()*original;bad_reduced+=reduced_bad;unexplained+=not_roundoff;maximum_absolute=std::max(maximum_absolute,std::fabs(sum));maximum_source_scaled=std::max(maximum_source_scaled,scaled);
  if(residual>maximum_residual){maximum_residual=residual;maximum_row=i;}if((reduced_bad&&examples.arr().size()<32)||i==1196557){Json witness=Json::object();witness["row"]=i;witness["signed_row_sum_native_units"]=precise(sum);witness["reduced_row_L1_native_units"]=precise(norm);witness["source_absolute_contribution_sum_native_units"]=precise(original);witness["relative_to_reduced_row_L1"]=double(residual);witness["relative_to_source_absolute_sum"]=double(scaled);witness["outside_heuristic_roundoff_screen"]=not_roundoff;examples.push(witness);}}
 Json result=Json::object();result["upper_entries"]=I(total);result["node_count"]=nodes;result["maximum_scaled_charge_residual"]=double(maximum_residual);result["maximum_charge_residual_row"]=maximum_row;result["maximum_absolute_charge_residual_native_units"]=precise(maximum_absolute);result["maximum_source_absolute_normalized_residual"]=precise(maximum_source_scaled);result["rows_exceeding_reduced_row_relative_limit"]=bad_reduced;result["rows_outside_heuristic_source_roundoff_screen"]=unexplained;result["zero_coefficient_rows"]=zero_rows;result["witnesses"]=examples;result["source_roundoff_screen_is_rigorous_error_bound"]=false;result["native_capacitance_unit_F"]=1e-18;result["matrix_modified"]=false;result["charge_conservation_proved"]=false;result["physical_RC_qualified"]=false;result["release_qualified"]=false;
 std::ofstream output(cfg.at("report").str());output<<result.dump()<<'\n';output.close();require(bool(output),"matrix audit report close");std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
