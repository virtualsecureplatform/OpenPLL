// Component-block preconditioner pattern only. Full equations and all G edges remain required.
#include "../charge_compiler/json.hpp"
#include "sparse_runs_v2.hpp"
#include "zero_C_mask.hpp"
#include "conductor_map.hpp"
#include <memory>
#include <set>
#include <cholmod.h>
#include <time.h>
#include <iostream>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static std::string decimal(unsigned __int128 x){std::string s;do{s.push_back('0'+x%10);x/=10;}while(x);std::reverse(s.begin(),s.end());return s;}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);I count=cfg.at("node_count").integer();require(count>1&&count<=10000000,"bounded factor pattern");uint64_t n=count;
 double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(now()<deadline,"factor pattern deadline");};
 auto zero=read_zero_C_mask(cfg.at("zero_rows").str(),n);ConductorMap components(cfg.at("components").str(),"CNETDOF1");
 require(components.size()==n,"component namespace dimension");
 std::vector<uint64_t>component_sizes(components.net_count());for(uint64_t i=0;i<n;i++)component_sizes[components.at(i)]++;
 uint64_t largest_component=*std::max_element(component_sizes.begin(),component_sizes.end());
 std::vector<std::string>files{cfg.at("matrix").str()};for(const auto&path:cfg.at("G_matrices").arr())files.push_back(path.str());
 require(files.size()>1&&files.size()<=17&&std::set<std::string>(files.begin(),files.end()).size()==files.size(),"distinct bounded C/G sources");
 struct Stats{uint64_t records=0,C_records=0,G_records=0,edges=0,cross_C_keys=0;bool operator==(const Stats&)const=default;};
 auto scan=[&](auto consume){
  struct Stream{std::unique_ptr<sparse::Reader>reader;sparse::Record record;bool live;};std::vector<Stream>streams;
  for(const auto&file:files){auto reader=std::make_unique<sparse::Reader>(file);sparse::Record r;bool live=reader->next(r);streams.push_back({std::move(reader),r,live});}
  Stats stats;
  for(;;){
   uint64_t key=UINT64_MAX;bool any=false;for(auto&stream:streams)if(stream.live){any=true;key=std::min(key,stream.record.key);}if(!any)break;
   uint64_t i=key>>32,j=key&UINT32_MAX;require(j<n,"component pattern matrix bounds");bool present=false,c_present=false;
   for(size_t k=0;k<streams.size();k++){auto&stream=streams[k];if(!stream.live||stream.record.key!=key)continue;
    if(stats.records++%10000==0)check();(k?stats.G_records:stats.C_records)++;
    if(i!=j&&stream.record.value!=0){
     if(k){require(components.at(i)==components.at(j),"G edge crosses its certified component");present=true;}
     else if(!zero[i]&&!zero[j]){c_present=true;present=true;}
    }
    stream.live=stream.reader->next(stream.record);
   }
   if(i==j)continue;
   if(components.at(i)!=components.at(j)){stats.cross_C_keys+=c_present;continue;}
   if(present){stats.edges++;consume(i,j);}
  }
  return stats;
 };
 std::vector<uint64_t>counts(n,1);auto first=scan([&](uint64_t,uint64_t j){counts[j]++;});uint64_t edges=first.edges,read=first.records;
 uint64_t nz=n+edges;require(nz<=uint64_t(INT64_MAX)&&8*(nz+n+1)<=uint64_t(cfg.at("maximum_pattern_bytes").integer()),"bounded CSC pattern allocation");
 cholmod_common common{};require(cholmod_l_start(&common),"CHOLMOD long initialization");
 common.nmethods=1;common.method[0].ordering=CHOLMOD_AMD;common.postorder=1;common.supernodal=CHOLMOD_SIMPLICIAL;
 auto*a=cholmod_l_allocate_sparse(n,n,nz,1,1,1,CHOLMOD_PATTERN,&common);require(a&&a->itype==CHOLMOD_LONG,"CHOLMOD int64 pattern allocation");
 auto*p=static_cast<int64_t*>(a->p);auto*indices=static_cast<int64_t*>(a->i);p[0]=0;
 for(uint64_t j=0;j<n;j++){p[j+1]=p[j]+counts[j];counts[j]=p[j];}
 auto second=scan([&](uint64_t i,uint64_t j){require(counts[j]<uint64_t(p[j+1]),"pattern column bound");indices[counts[j]++]=i;});
 require(first==second,"stable complete component pattern passes");
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
 r["components"]=I(components.net_count());r["largest_component_voltage_nodes"]=I(largest_component);
 r["C_source_records"]=I(first.C_records);r["G_source_records"]=I(first.G_records);r["cross_component_C_keys_excluded_from_preconditioner"]=I(first.cross_C_keys);
 r["preconditioner_pattern_only_full_equations_unchanged"]=true;r["all_G_edges_retained_including_source_zero_C_states"]=true;
 r["numeric_factorization_started"]=false;r["KLU_fill_or_memory_bound_proved"]=false;r["G_pattern_included"]=true;
 r["full_matrix_passivity_verified"]=false;r["native_solver_qualified"]=false;r["physical_RC_qualified"]=false;r["release_qualified"]=false;
 require(cholmod_l_free_factor(&l,&common)&&cholmod_l_free_sparse(&a,&common)&&cholmod_l_finish(&common),"CHOLMOD close");
 std::ofstream output(cfg.at("report").str());output<<r.dump()<<'\n';output.close();require(bool(output),"pattern report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
