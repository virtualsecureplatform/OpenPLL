#include "OpenPLL_WirePreconditioner_v2.h"
#include "OpenPLL_WirePreconditioner_warm_reuse_bounded.h"
#include "OpenPLL_WirePreconditioner_cached_parallel_reuse.h"
#include <cstring>
#include <cstdint>
// Synthetic coefficient changes on the captured graph; not a native Newton sequence.
#include <Epetra_SerialComm.h>
#include <Epetra_Map.h>
#include <Epetra_CrsMatrix.h>
#include <Epetra_Vector.h>
#include <Epetra_LinearProblem.h>
#include <Epetra_Operator.h>
#include <Amesos.h>
#include <Amesos_BaseSolver.h>
#include <AztecOO.h>
#include <az_aztec.h>
#include <fstream>
#include <iostream>
#include <memory>
#include <vector>
#include <cmath>
#include <chrono>
#include <stdexcept>

void check(bool value, const char* msg) { if (!value) throw std::runtime_error(msg); }
template<class T> void read(std::ifstream& in, T* p, size_t n) {
    in.read(reinterpret_cast<char*>(p), n*sizeof(T)); check(bool(in), "truncated input");
}
std::unique_ptr<Epetra_CrsMatrix> load(const std::string& path, const Epetra_Map& map) {
    std::ifstream in(path, std::ios::binary);
    int n, nnz; read(in,&n,1); read(in,&nnz,1);
    check(n==map.NumGlobalElements() && nnz>0, "matrix dimensions");
    std::vector<int> row(n+1), col(nnz), counts(n); std::vector<double> val(nnz);
    read(in,row.data(),row.size()); read(in,col.data(),col.size()); read(in,val.data(),val.size());
    check(row[0]==0 && row[n]==nnz && in.peek()==EOF, "matrix format");
    for(int i=0;i<n;++i) { check(row[i+1]>=row[i],"row order"); counts[i]=row[i+1]-row[i]; }
    auto a=std::make_unique<Epetra_CrsMatrix>(Copy,map,counts.data());
    for(int i=0;i<n;++i) {
        check(a->InsertGlobalValues(i,counts[i],val.data()+row[i],col.data()+row[i])==0,"matrix insert");
    }
    check(a->FillComplete()==0,"FillComplete"); return a;
}

uint64_t fingerprint(const Epetra_CrsMatrix& a) {
    uint64_t h=1469598103934665603ULL;
    for(int i=0;i<a.NumMyRows();++i) {
        int count; double* values; int* indices; check(a.ExtractMyRowView(i,count,values,indices)==0,"hash row");
        for(int k=0;k<count;++k) {
            uint64_t value; std::memcpy(&value,&values[k],sizeof(value));
            h^=value; h*=1099511628211ULL; h^=uint64_t(a.ColMap().GID(indices[k])); h*=1099511628211ULL;
        }
    }
    return h;
}
int main(int argc,char** argv) {
    try {
        check(argc==3,"usage: native_adapter_probe input_dir output_dir");
        std::string input=argv[1],output=argv[2]; int n;
        std::ifstream dims(input+"/dimensions.txt"); dims>>n; check(n>0,"dimensions");
        Epetra_SerialComm comm; Epetra_Map map(n,0,comm);
        auto a=load(input+"/original_A.bin",map); auto before=fingerprint(*a);
        std::vector<std::vector<double>> original(n);
        for(int i=0;i<n;++i) {
            int count; double* values; int* indices; a->ExtractMyRowView(i,count,values,indices);
            original[i].assign(values,values+count);
        }
        OpenPLLScaledCrs::Cache scale_audit_cache(*a);
        Epetra_Vector audit_rs(map),audit_cs(map);
        for(int i=0;i<n;++i) {audit_rs[i]=.1+(i%13)/13.;audit_cs[i]=.2+(i%17)/17.;}
        const double deltas[]={0.,1e-8,1e-6,1e-4,.01,0.,.01,0.,5e-7,5e-6,2e-5,3e-4,-1e-5,0.,.002,0.};
        for(int step=0;step<16;++step) {
          double gamma=step==6 ? 2. : 1.;
          for(int i=0;i<n;++i) {
            int count; double* values; int* indices; a->ExtractMyRowView(i,count,values,indices);
            for(int k=0;k<count;++k) {
              double value=original[i][k];
              if(a->ColMap().GID(indices[k])==i) value+=deltas[step]*std::abs(value);
              values[k]=gamma*value;
            }
          }
          before=fingerprint(*a);
          {
            Epetra_CrsMatrix reference(*a);
            check(reference.LeftScale(audit_rs)==0 && reference.RightScale(audit_cs)==0,"reference scaling");
            auto& cached=scale_audit_cache.update(*a,audit_rs,audit_cs);
            check(fingerprint(reference)==fingerprint(cached),"cached coefficients differ from two-pass Epetra scaling");
            check(fingerprint(*a)==before,"cache changed original matrix");
            std::cout << "SCALED_CACHE_CHECK step=" << step << " bitwise_equal=1" << std::endl;
          }
          std::string label="step"+std::to_string(step);
          for(int variant=0;variant<3;++variant) {
            Epetra_Vector x(map),rhs(map),residual(map),known(map); x.PutScalar(0.);
            for(int i=0;i<n;++i) known[i]=.1*(std::sin(.013*i+.0001*step)+std::cos(.027*i));
            check(a->Multiply(false,known,rhs)==0,"generate current known RHS");
            std::string result_label=(variant==0 ? "baseline_" : variant==1 ? "bounded_" : "cached_")+label;
            std::vector<double> copy(rhs.Values(),rhs.Values()+n);
            std::ofstream rhs_file(output+"/"+result_label+".rhs.bin",std::ios::binary);
            rhs_file.write(reinterpret_cast<char*>(copy.data()),n*sizeof(double)); check(bool(rhs_file),"RHS write");
            rhs_file.close();
            Epetra_LinearProblem problem(a.get(),&x,&rhs);
            auto started=std::chrono::steady_clock::now();
            std::cout << "PROBE_VARIANT label=" << result_label << std::endl;
            check((variant==0 ? OpenPLLWirePC::solve(problem,false) : variant==1 ? OpenPLLWireBoundedReusePC::solve(problem,false) : OpenPLLWireCachedParallelReusePC::solve(problem,false))==0,"adapter solve failed");
            double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
            check(fingerprint(*a)==before,"adapter changed original Jacobian");
            check(std::memcmp(copy.data(),rhs.Values(),sizeof(double)*n)==0,"adapter changed original RHS");
            check(a->Multiply(false,x,residual)==0,"residual matvec"); residual.Update(-1.,rhs,1.);
            double maximum; residual.NormInf(&maximum);
            std::ofstream result(output+"/"+result_label+".bin",std::ios::binary);
            result.write(reinterpret_cast<char*>(x.Values()),n*sizeof(double)); check(bool(result),"solution write");
            std::cout << "{\"case\":\"" << result_label << "\",\"solve_wall_s\":" << wall << ",\"original_residual_inf\":" << maximum
                << ",\"original_Jacobian_unchanged\":true,\"original_RHS_unchanged\":true}" << std::endl;
        }
        }
        return 0;
    } catch(const std::exception& ex) { std::cerr << ex.what() << std::endl; return 1; }
}
