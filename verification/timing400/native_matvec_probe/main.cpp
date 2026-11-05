#include <Epetra_SerialComm.h>
#include <Epetra_Map.h>
#include <Epetra_CrsMatrix.h>
#include <Epetra_Vector.h>
#include <omp.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <stdexcept>
#include <vector>
#include <cstdint>
#include <cstring>
#include <limits>

void check(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
template<class T> void read(std::ifstream& in,T* p,size_t count) {
    in.read(reinterpret_cast<char*>(p),sizeof(T)*count); check(bool(in),"truncated captured matrix");
}
uint64_t fingerprint(const Epetra_CrsMatrix& a) {
    uint64_t h=1469598103934665603ULL;
    for(int i=0;i<a.NumMyRows();++i) {
        int count;double* values;int* columns;check(a.ExtractMyRowView(i,count,values,columns)==0,"hash row");
        for(int k=0;k<count;++k) {
            uint64_t v;std::memcpy(&v,&values[k],sizeof(v));
            h^=v;h*=1099511628211ULL;h^=uint64_t(a.ColMap().GID(columns[k]));h*=1099511628211ULL;
        }
    }
    return h;
}
int main(int argc,char** argv) {
  try {
    check(argc==3,"usage: native_matvec_probe matrix.bin output_directory");
    std::ifstream in(argv[1],std::ios::binary);int n,m;read(in,&n,1);read(in,&m,1);
    check(n==174551 && m==11209902,"unexpected captured graph");
    std::vector<int> row(n+1),col(m),counts(n);std::vector<double> values(m);
    read(in,row.data(),row.size());read(in,col.data(),col.size());read(in,values.data(),values.size());
    check(row[0]==0 && row[n]==m && in.peek()==EOF,"matrix format");
    Epetra_SerialComm comm;Epetra_Map map(n,0,comm);
    for(int i=0;i<n;++i) {check(row[i+1]>=row[i],"row ordering");counts[i]=row[i+1]-row[i];}
    Epetra_CrsMatrix a(Copy,map,counts.data());
    for(int i=0;i<n;++i) check(a.InsertGlobalValues(i,counts[i],values.data()+row[i],col.data()+row[i])==0,"insert");
    check(a.FillComplete()==0,"fill");auto before=fingerprint(a);
    check(a.OptimizeStorage()==0 && fingerprint(a)==before,"packing changed coefficients");
    int* offsets;int* indices;double* coefficients;
    check(a.ExtractCrsDataPointers(offsets,indices,coefficients)==0,"packed CSR view");
    std::vector<int> gids(a.NumMyCols());
    for(int i=0;i<a.NumMyCols();++i) {gids[i]=a.ColMap().GID(i);check(gids[i]>=0 && gids[i]<n,"serial column map");}
    Epetra_Vector x(map),reference(map),result(map);
    omp_set_dynamic(0);
    for(int threads: {0,1,2,4}) {
      std::vector<int> boundaries(threads+1);
      if(threads) {
        boundaries.front()=0;boundaries.back()=n;
        for(int t=1;t<threads;++t)
          boundaries[t]=int(std::lower_bound(offsets,offsets+n+1,(int64_t(m)*t)/threads)-offsets);
      }
      auto multiply=[&]() {
        if(!threads) {check(a.Multiply(false,x,result)==0,"reference matvec");return;}
        #pragma omp parallel for schedule(static) num_threads(threads) if(threads>1)
        for(int part=0;part<threads;++part) {
          for(int i=boundaries[part];i<boundaries[part+1];++i) {
            double sum=0.;
            for(int k=offsets[i];k<offsets[i+1];++k) sum+=coefficients[k]*x[gids[indices[k]]];
            result[i]=sum;
          }
        }
      };
      double maximum_error=0.,maximum_bound=0.;
      for(int fixture=0;fixture<3;++fixture) {
        for(int i=0;i<n;++i) x[i]=fixture==0 ? std::sin(.013*i)+std::cos(.027*i) : fixture==1 ? (i%2 ? -1. : 1.) : 1e-6*(i%127-63);
        check(a.Multiply(false,x,reference)==0,"accuracy reference");multiply();
        for(int i=0;i<n;++i) {
          double absolute_sum=0.;
          for(int k=offsets[i];k<offsets[i+1];++k) absolute_sum+=std::abs(coefficients[k])*std::abs(x[gids[indices[k]]]);
          double epsilon=std::numeric_limits<double>::epsilon(),terms=offsets[i+1]-offsets[i];
          double bound=8*(terms+1)*epsilon/(1-(terms+1)*epsilon)*absolute_sum;
          double error=std::abs(result[i]-reference[i]);
          check(std::isfinite(result[i]) && error<=bound,"matvec differs beyond summation bound");
          maximum_error=std::max(maximum_error,error);maximum_bound=std::max(maximum_bound,bound);
        }
      }
      for(int i=0;i<n;++i) x[i]=std::sin(.013*i)+std::cos(.027*i);
      for(int warmup=0;warmup<5;++warmup) multiply();
      auto begin=std::chrono::steady_clock::now();
      for(int repetition=0;repetition<50;++repetition) multiply();
      double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
      std::ofstream output(std::string(argv[2])+"/threads"+std::to_string(threads)+".bin",std::ios::binary);
      output.write(reinterpret_cast<const char*>(result.Values()),sizeof(double)*n);check(bool(output),"result write");
      check(fingerprint(a)==before,"benchmark changed captured equations");
      std::cout<<std::setprecision(17)<<"{\"threads\":"<<threads<<",\"reference_Epetra\":"<<(threads==0 ? "true" : "false")
        <<",\"repetitions\":50,\"total_multiply_s\":"<<seconds<<",\"maximum_observed_error\":"<<maximum_error
        <<",\"maximum_summation_bound\":"<<maximum_bound<<",\"all_three_fixture_checks_passed\":true,\"original_matrix_unchanged\":true}"<<std::endl;
    }
    return 0;
  } catch(const std::exception& error) {std::cerr<<error.what()<<std::endl;return 1;}
}
