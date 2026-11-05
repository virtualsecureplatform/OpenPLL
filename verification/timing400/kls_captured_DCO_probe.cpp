// Exercise user-selected KLS on the complete captured DCO matrix/RHS.
#include <kls/kls.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
void require(bool ok,const char* message) {if(!ok)throw std::runtime_error(message);}
template<class T>void read(std::ifstream& input,T* p,size_t n) {
    input.read(reinterpret_cast<char*>(p),sizeof(T)*n);require(bool(input),"truncated input");
}
uint64_t fingerprint(const std::vector<double>& v) {
    uint64_t h=1469598103934665603ULL;
    for(double value:v) {uint64_t b;std::memcpy(&b,&value,8);h^=b;h*=1099511628211ULL;}
    return h;
}
int main(int argc,char** argv) {
    kls_solver* solver=nullptr;
    try {
        require(argc==3,"usage: kls_captured_DCO_probe input_dir output_dir");
        std::string input=argv[1],output=argv[2];
        std::ifstream file(input+"/original_A.bin",std::ios::binary);int n,m;read(file,&n,1);read(file,&m,1);
        require(n==174551 && m==11209902,"captured dimensions");
        std::vector<int> row(n+1),col(m);std::vector<double> values(m);
        read(file,row.data(),row.size());read(file,col.data(),col.size());read(file,values.data(),values.size());
        require(row.front()==0 && row.back()==m && file.peek()==EOF,"CSR format");
        auto hash=fingerprint(values);kls_options options;kls_default_options(&options);
        options.threads=4;options.record_tiny_solve_timing=0;
        options.expected_refactorizations=20000;options.expected_solves=20000;
        require(kls_create(&solver)==KLS_OK,"KLS create");
        kls_accuracy_policy policy;require(kls_get_accuracy_policy(solver,&policy)==KLS_OK,"KLS policy query");
        require(policy==KLS_ACCURACY_COMPONENTWISE_BACKWARD_ERROR,"unexpected default certification policy");
        auto start=std::chrono::steady_clock::now();
        auto stage=[&](const char* name,int status) {
            double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            std::cout<<std::setprecision(17)<<"{\"stage\":\""<<name<<"\",\"status\":"<<status<<",\"elapsed_s\":"<<seconds<<"}"<<std::endl;
            require(status==KLS_OK,name);
        };
        stage("analyze",kls_analyze_csr(solver,KLS_INDEX_INT32,n,row.data(),col.data(),0,&options));
        stage("factor",kls_factor(solver,values.data()));
        for(const std::string label:{"native_Newton_RHS","known_solution"}) {
            std::vector<double> rhs(n),x(n);std::ifstream stream(input+"/"+label+".bin",std::ios::binary);read(stream,rhs.data(),n);
            auto rhs_hash=fingerprint(rhs);
            stage(label.c_str(),kls_solve(solver,1,rhs.data(),0,x.data(),0));
            require(fingerprint(values)==hash && fingerprint(rhs)==rhs_hash,"KLS changed original equations");
            for(double value:x)require(std::isfinite(value),"nonfinite solution");
            std::ofstream saved(output+"/"+label+".solution.bin",std::ios::binary);
            saved.write(reinterpret_cast<char*>(x.data()),sizeof(double)*n);require(bool(saved),"solution write");
        }
        kls_stats stats{};stats.struct_size=sizeof(stats);require(kls_get_stats(solver,&stats)==KLS_OK,"KLS stats");
        std::cout<<std::setprecision(17)<<"{\"stage\":\"stats\",\"status\":0,\"nnz_l\":"<<stats.nnz_l<<",\"nnz_u\":"<<stats.nnz_u
            <<",\"memory_peak_bytes\":"<<stats.memory_peak_bytes<<",\"analysis_s\":"<<stats.analysis_seconds
            <<",\"factor_s\":"<<stats.factor_seconds<<",\"solve_s\":"<<stats.solve_seconds<<"}"<<std::endl;
        kls_destroy(solver);return 0;
    }catch(const std::exception& error) {
        std::cerr<<error.what()<<std::endl;if(solver)kls_destroy(solver);return 1;
    }
}
