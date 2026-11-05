#include "../charge_compiler/json.hpp"
#include <omp.h>
#include <iostream>
#include <string>
int main(int argc,char**argv){try{
 require(argc==2,"one explicit reserved thread count required");std::string arg=argv[1];size_t consumed=0;int limit=std::stoi(arg,&consumed);require(consumed==arg.size()&&limit>=1&&limit<=32,"reserved thread count in 1..32");
 require(omp_get_thread_limit()==limit,"OpenMP process limit matches CPU lease");
 Json result=Json::object();result["thread_limit"]=limit;Json observations=Json::array();
 for(int requested:{8,32}){int observed=0;
#pragma omp parallel num_threads(requested)
 {
#pragma omp single
 observed=omp_get_num_threads();
 }
 require(observed>0&&observed<=limit&&observed<=requested,"loader/projector team bounded by reserved cores");Json row=Json::object();row["requested_threads"]=requested;row["observed_threads"]=observed;observations.push(row);
 }
 result["teams"]=observations;std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
