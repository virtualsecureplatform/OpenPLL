// Fixed-graph diagnosis: exact native settings versus lifecycle hints.
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
void require(bool ok,const char* m){if(!ok)throw std::runtime_error(m);}
template<class T>void read(std::ifstream& in,T* p,size_t n){in.read(reinterpret_cast<char*>(p),sizeof(T)*n);require(bool(in),"truncated input");}
int main(int argc,char** argv){
 kls_solver* solver=nullptr;
 try{
  require(argc==3,"usage: profile input_dir output_dir");std::string input=argv[1],output=argv[2];
  std::ifstream file(input+"/original_A.bin",std::ios::binary);int n,m;read(file,&n,1);read(file,&m,1);
  require(n==174551 && m==11209902,"dimensions");
  std::vector<int> row(n+1),col(m);std::vector<double> original(m),values(m),rhs(n),known(n),x(n);
  read(file,row.data(),row.size());read(file,col.data(),col.size());read(file,original.data(),original.size());
  require(row[0]==0 && row[n]==m && file.peek()==EOF,"CSR format");
  for(int i=0;i<n;++i)known[i]=.1*(std::sin(.013*i)+std::cos(.027*i));
  for(int hints:{0,20000}){
   const std::string prefix=hints?"hinted":"native_defaults";
   kls_options options;kls_default_options(&options);options.threads=4;options.record_tiny_solve_timing=0;
   options.expected_refactorizations=hints;options.expected_solves=hints;
   require(kls_create(&solver)==KLS_OK,"create");
   auto stage=[&](const std::string& name,auto action){
    auto start=std::chrono::steady_clock::now();int code=action();
    double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    kls_stats stats{};stats.struct_size=sizeof(stats);require(kls_get_stats(solver,&stats)==KLS_OK,"stats");
    std::cout<<std::setprecision(17)<<"{\"variant\":\""<<prefix<<"\",\"stage\":\""<<name<<"\",\"status\":"<<code
     <<",\"wall_s\":"<<wall<<",\"factor_total_s\":"<<stats.factor_seconds<<",\"refactor_total_s\":"<<stats.refactor_seconds
     <<",\"solve_total_s\":"<<stats.solve_seconds<<",\"nnz_l\":"<<stats.nnz_l<<",\"nnz_u\":"<<stats.nnz_u
     <<",\"ordering\":"<<stats.selected_ordering<<",\"orientation\":"<<stats.selected_orientation
     <<",\"factor_path\":\""<<kls_factor_path_name(stats.last_factor_path)<<"\",\"refactor_path\":\""<<kls_refactor_path_name(stats.last_refactor_path)
     <<"\",\"row_refactor_parallel\":"<<stats.row_refactor_last_parallel<<",\"memory_peak_bytes\":"<<stats.memory_peak_bytes<<"}"<<std::endl;
    require(code==KLS_OK,name.c_str());
   };
   values=original;
   stage("analyze",[&](){return kls_analyze_csr(solver,KLS_INDEX_INT32,n,row.data(),col.data(),0,&options);});
   stage("factor",[&](){return kls_factor(solver,values.data());});
   auto make_rhs=[&](){for(int i=0;i<n;++i){double sum=0.;for(int k=row[i];k<row[i+1];++k)sum+=values[k]*known[col[k]];rhs[i]=sum;}};
   auto save_answer=[&](const std::string& label){
    for(double v:x)require(std::isfinite(v),"nonfinite answer");
    std::ofstream a(output+"/"+prefix+"_"+label+".solution.bin",std::ios::binary);
    a.write(reinterpret_cast<char*>(x.data()),n*sizeof(double));require(bool(a),"solution write");
    std::ofstream b(output+"/"+prefix+"_"+label+".rhs.bin",std::ios::binary);
    b.write(reinterpret_cast<char*>(rhs.data()),n*sizeof(double));require(bool(b),"RHS write");
   };
   make_rhs();stage("solve_original",[&](){return kls_solve(solver,1,rhs.data(),0,x.data(),0);});save_answer("original");
   for(int i=0;i<n;i+=17)for(int k=row[i];k<row[i+1];++k)if(col[k]==i)values[k]+=1e-6*std::abs(values[k]);
   make_rhs();stage("refactor_sparse_diagonal",[&](){return kls_refactor(solver,values.data());});
   stage("solve_sparse_diagonal",[&](){return kls_solve(solver,1,rhs.data(),0,x.data(),0);});save_answer("sparse_diagonal");
   for(int k=0;k<m;++k)values[k]=1.01*original[k];make_rhs();
   stage("refactor_solve_global_scale",[&](){return kls_refactor_solve(solver,values.data(),1,rhs.data(),0,x.data(),0);});save_answer("global_scale");
   values=original;make_rhs();
   stage("refactor_solve_restore",[&](){return kls_refactor_solve(solver,values.data(),1,rhs.data(),0,x.data(),0);});save_answer("restore");
   kls_destroy(solver);solver=nullptr;
  }return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;if(solver)kls_destroy(solver);return 1;}
}
