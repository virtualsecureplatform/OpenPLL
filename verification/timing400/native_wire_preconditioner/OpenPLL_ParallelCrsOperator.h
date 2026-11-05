// Experimental serial-map CSR operator: parallel rows, original row sums.
// The referenced scaled matrix must outlive this operator and remain fixed.
#ifndef OPENPLL_PARALLEL_CRS_OPERATOR_H
#define OPENPLL_PARALLEL_CRS_OPERATOR_H
#include <Epetra_CrsMatrix.h>
#include <Epetra_Operator.h>
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace OpenPLLParallelCrs {
class Operator : public Epetra_Operator {
    Epetra_CrsMatrix& matrix_;
    int* offsets_=nullptr; int* columns_=nullptr; double* coefficients_=nullptr;
    int threads_=1;
    std::vector<int> gids_, boundaries_;
    static void check(bool value,const char* message) {
        if(!value) throw std::runtime_error(message);
    }
public:
    explicit Operator(Epetra_CrsMatrix& matrix):matrix_(matrix) {
        check(matrix.Comm().NumProc()==1,"parallel CSR requires serial maps");
        int requested=1;
        if(const char* setting=std::getenv("OPENPLL_WIRE_MATVEC_THREADS")) {
            char* end=nullptr; long value=std::strtol(setting,&end,10);
            check(end!=setting && *end=='\0' && value>=1 && value<=4,"parallel CSR thread setting");
            requested=int(value);
        }
#ifndef _OPENMP
        check(requested==1,"parallel CSR needs OpenMP compilation");
#endif
        threads_=matrix.NumMyRows()>=4096 ? requested : 1;
        check(matrix.OptimizeStorage()==0,"parallel CSR storage packing");
        check(matrix.ExtractCrsDataPointers(offsets_,columns_,coefficients_)==0,"parallel CSR view");
        const int n=matrix.NumMyRows();
        check(matrix.NumGlobalRows()==matrix.NumGlobalCols(),"parallel CSR square operator");
        for(int i=0;i<n;++i)
            check(matrix.DomainMap().GID(i)==i && matrix.RangeMap().GID(i)==i &&
                  matrix.RowMap().GID(i)==i,"parallel CSR contiguous serial maps");
        gids_.resize(matrix.NumMyCols());
        for(size_t i=0;i<gids_.size();++i) {
            gids_[i]=matrix.ColMap().GID(i);
            check(gids_[i]>=0 && gids_[i]<n,"parallel CSR column map");
        }
        boundaries_.resize(threads_+1);boundaries_.front()=0;boundaries_.back()=n;
        for(int t=1;t<threads_;++t)
            boundaries_[t]=int(std::lower_bound(offsets_,offsets_+n+1,
                               (static_cast<long long>(offsets_[n])*t)/threads_)-offsets_);
        std::cout << "OpenPLL_parallel_CSR rows=" << n << " nonzeros=" << offsets_[n]
                  << " requested_threads=" << requested << " active_threads=" << threads_ << std::endl;
    }
    int SetUseTranspose(bool use) override {return use ? -1 : 0;}
    int Apply(const Epetra_MultiVector& x,Epetra_MultiVector& y) const override {
        if(x.NumVectors()!=1 || y.NumVectors()!=1 || x[0]==y[0] ||
           !x.Map().SameAs(matrix_.DomainMap()) || !y.Map().SameAs(matrix_.RangeMap())) return -1;
        const double* input=x[0]; double* output=y[0];
        const int threads=threads_;
#pragma omp parallel for schedule(static) num_threads(threads) if(threads>1)
        for(int part=0;part<threads;++part) {
            for(int i=boundaries_[part];i<boundaries_[part+1];++i) {
                double sum=0.;
                for(int k=offsets_[i];k<offsets_[i+1];++k)
                    sum+=coefficients_[k]*input[gids_[columns_[k]]];
                output[i]=sum;
            }
        }
        return 0;
    }
    int ApplyInverse(const Epetra_MultiVector&,Epetra_MultiVector&) const override {return -1;}
    double NormInf() const override {return matrix_.NormInf();}
    const char* Label() const override {return "OpenPLL unchanged parallel CSR rows";}
    bool UseTranspose() const override {return false;}
    bool HasNormInf() const override {return true;}
    const Epetra_Comm& Comm() const override {return matrix_.Comm();}
    const Epetra_Map& OperatorDomainMap() const override {return matrix_.DomainMap();}
    const Epetra_Map& OperatorRangeMap() const override {return matrix_.RangeMap();}
};
}
#endif
