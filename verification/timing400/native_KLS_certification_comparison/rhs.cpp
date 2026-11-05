#include "OpenPLL_KLU_comparison.h"
#include "OpenPLL_KLS_comparison.h"
#include <cstring>
#include <cstdint>
// Exercise the complete opt-in adapter on an unchanged captured native matrix.
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
        check(argc==4,"usage: native_adapter_probe input_dir output_dir");
        std::string input=argv[1],output=argv[2]; int n;
        std::ifstream dims(input+"/dimensions.txt"); dims>>n; check(n>0,"dimensions");
        Epetra_SerialComm comm; Epetra_Map map(n,0,comm);
        auto a=load(input+"/original_A.bin",map); auto before=fingerprint(*a);
        for(const std::string label: {"native_Newton_RHS","native_repeat","perturbed_native","known_solution","known_repeat"}) {
          for(const bool warm: {std::string(argv[3])=="KLS"}) {
            Epetra_Vector x(map),rhs(map),residual(map); x.PutScalar(0.);
            std::string source_label=(label=="known_solution" || label=="known_repeat") ? "known_solution" : "native_Newton_RHS";
            std::ifstream in(input+"/"+source_label+".bin",std::ios::binary); read(in,rhs.Values(),n);
            if(label=="perturbed_native") {
                Epetra_Vector known_rhs(map); std::ifstream extra(input+"/known_solution.bin",std::ios::binary); read(extra,known_rhs.Values(),n);
                double native_norm=0., known_norm=0.;
                for(int i=0;i<n;++i) {
                    int count; double* values; int* indices; a->ExtractMyRowView(i,count,values,indices);
                    double scale=0.; for(int j=0;j<count;++j) scale=std::max(scale,std::abs(values[j]));
                    native_norm+=std::pow(rhs[i]/scale,2); known_norm+=std::pow(known_rhs[i]/scale,2);
                }
                rhs.Update(.001*std::sqrt(native_norm/known_norm),known_rhs,1.);
            }
            std::string result_label=(warm ? "warm_" : "baseline_")+label;
            std::vector<double> copy(rhs.Values(),rhs.Values()+n);
            std::ofstream rhs_file(output+"/"+result_label+".rhs.bin",std::ios::binary);
            rhs_file.write(reinterpret_cast<char*>(copy.data()),n*sizeof(double)); check(bool(rhs_file),"RHS write");
            rhs_file.close();
            Epetra_LinearProblem problem(a.get(),&x,&rhs);
            auto started=std::chrono::steady_clock::now();
            check((warm ? OpenPLLWireKLSCertComparisonPC::solve(problem,false) : OpenPLLWireKLUCertComparisonPC::solve(problem,false))==0,"adapter solve failed");
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
