// Offline probe for the existing serial Xyce SDK. No simulator is modified.
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

class ExactApproximation : public Epetra_Operator {
    Epetra_CrsMatrix& b_; mutable Epetra_LinearProblem problem_;
    std::unique_ptr<Amesos_BaseSolver> solver_;
public:
    explicit ExactApproximation(Epetra_CrsMatrix& b): b_(b), problem_(&b,nullptr,nullptr) {
        solver_.reset(Amesos().Create("Klu",problem_)); check(bool(solver_),"Amesos KLU unavailable");
        check(solver_->SymbolicFactorization()==0,"KLU symbolic factorization");
        check(solver_->NumericFactorization()==0,"KLU numeric factorization");
    }
    int SetUseTranspose(bool use) override { return use ? -1 : 0; }
    int Apply(const Epetra_MultiVector& x,Epetra_MultiVector& y) const override { return b_.Multiply(false,x,y); }
    int ApplyInverse(const Epetra_MultiVector& x,Epetra_MultiVector& y) const override {
        problem_.SetLHS(&y); problem_.SetRHS(const_cast<Epetra_MultiVector*>(&x));
        return solver_->Solve();
    }
    double NormInf() const override { return b_.NormInf(); }
    const char* Label() const override { return "OpenPLL exact sparse approximate Jacobian"; }
    bool UseTranspose() const override { return false; }
    bool HasNormInf() const override { return true; }
    const Epetra_Comm& Comm() const override { return b_.Comm(); }
    const Epetra_Map& OperatorDomainMap() const override { return b_.OperatorDomainMap(); }
    const Epetra_Map& OperatorRangeMap() const override { return b_.OperatorRangeMap(); }
};

int main(int argc,char** argv) {
    try {
        check(argc==3,"usage: native_solver_probe input_dir output_dir");
        std::string input=argv[1], output=argv[2];
        std::ifstream dims(input+"/dimensions.txt"); int n=0; dims>>n; check(n>0,"dimensions");
        Epetra_SerialComm comm; Epetra_Map map(n,0,comm);
        auto a=load(input+"/scaled_A.bin",map), b=load(input+"/scaled_B.bin",map);
        auto t=std::chrono::steady_clock::now(); ExactApproximation prec(*b);
        double factor_s=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();
        for(const std::string label: {"known_solution","native_Newton_RHS"}) {
            Epetra_Vector x(map), rhs(map), residual(map); x.PutScalar(0.);
            std::ifstream in(input+"/"+label+".bin",std::ios::binary); read(in,rhs.Values(),n);
            Epetra_LinearProblem problem(a.get(),&x,&rhs); AztecOO solver(problem);
            check(solver.SetPrecOperator(&prec)==0,"SetPrecOperator");
            solver.SetAztecOption(AZ_solver,AZ_gmres); solver.SetAztecOption(AZ_kspace,50);
            solver.SetAztecOption(AZ_output,AZ_none); solver.SetAztecOption(AZ_scaling,AZ_none);
            solver.SetAztecOption(AZ_conv,AZ_rhs);
            t=std::chrono::steady_clock::now(); int code=solver.Iterate(300,1e-12);
            double solve_s=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();
            check(a->Multiply(false,x,residual)==0,"residual matvec"); residual.Update(-1.,rhs,1.);
            double rn=0.,bn=0.; residual.Norm2(&rn); rhs.Norm2(&bn);
            check(code==0 && rn/bn<1e-12,"native GMRES convergence");
            std::ofstream result(output+"/"+label+".bin",std::ios::binary);
            result.write(reinterpret_cast<char*>(x.Values()),n*sizeof(double)); check(bool(result),"solution write");
            std::cout << "{\"case\":\"" << label << "\",\"iterations\":" << solver.NumIters()
                << ",\"factorization_s\":" << factor_s << ",\"solve_s\":" << solve_s
                << ",\"scaled_true_relative_residual\":" << rn/bn << "}" << std::endl;
        }
        return 0;
    } catch(const std::exception& ex) { std::cerr << ex.what() << std::endl; return 1; }
}
