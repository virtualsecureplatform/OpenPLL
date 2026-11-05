#include "../charge_compiler/json.hpp"
#include <omp.h>
#include <iostream>
int main(){try{require(omp_get_thread_limit()==2,"explicit two-thread OpenMP limit");int observed=0;
#pragma omp parallel num_threads(8)
{
#pragma omp single
 observed=omp_get_num_threads();
}
require(observed>0&&observed<=2,"geometry-like eight-thread request bounded to reserved cores");Json r=Json::object();r["thread_limit"]=omp_get_thread_limit();r["observed_threads_for_eight_thread_request"]=observed;std::cout<<r.dump()<<'\n';return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
