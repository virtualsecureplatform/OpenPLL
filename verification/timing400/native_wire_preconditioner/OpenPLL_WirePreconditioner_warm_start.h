// Experimental serial-only adapter. The Newton matrix/RHS are never changed.
#ifndef OPENPLL_WIRE_WARM_START_H
#define OPENPLL_WIRE_WARM_START_H
#include <Epetra_Comm.h>
#include <Epetra_CrsMatrix.h>
#include <Epetra_Vector.h>
#include <Epetra_LinearProblem.h>
#include <Epetra_Operator.h>
#include <Amesos.h>
#include <Amesos_BaseSolver.h>
#include <AztecOO.h>
#include <az_aztec.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include <chrono>

namespace OpenPLLWireWarmPC {
inline void require(bool ok,const char* msg) { if(!ok) throw std::runtime_error(msg); }
template<class T> void read(std::ifstream& in,T* dst,size_t n) {
    in.read(reinterpret_cast<char*>(dst),n*sizeof(T)); require(bool(in),"truncated wire-C metadata");
}
class ExactApproximation : public Epetra_Operator {
    Epetra_CrsMatrix& b_; mutable Epetra_LinearProblem problem_;
    std::unique_ptr<Amesos_BaseSolver> solver_;
public:
    explicit ExactApproximation(Epetra_CrsMatrix& b): b_(b),problem_(&b,nullptr,nullptr) {
        solver_.reset(Amesos().Create("Klu",problem_)); require(bool(solver_),"KLU unavailable");
        require(solver_->SymbolicFactorization()==0,"wire-PC symbolic factorization"); refactor();
    }
    void refactor() { require(solver_->NumericFactorization()==0,"wire-PC numeric factorization"); }
    int SetUseTranspose(bool use) override { return use ? -1 : 0; }
    int Apply(const Epetra_MultiVector& x,Epetra_MultiVector& y) const override { return b_.Multiply(false,x,y); }
    int ApplyInverse(const Epetra_MultiVector& x,Epetra_MultiVector& y) const override {
        problem_.SetLHS(&y); problem_.SetRHS(const_cast<Epetra_MultiVector*>(&x)); return solver_->Solve();
    }
    double NormInf() const override { return b_.NormInf(); }
    const char* Label() const override { return "OpenPLL wire-C approximate Jacobian"; }
    bool UseTranspose() const override { return false; }
    bool HasNormInf() const override { return true; }
    const Epetra_Comm& Comm() const override { return b_.Comm(); }
    const Epetra_Map& OperatorDomainMap() const override { return b_.OperatorDomainMap(); }
    const Epetra_Map& OperatorRangeMap() const override { return b_.OperatorRangeMap(); }
};
struct Entry { int source, gid; double capacitance; };
struct Sample { int row, source, gid; double capacitance; };
class Cache {
    int n_, m_; size_t calls_=0;
    std::string model_;
    std::vector<int> row_, col_;
    std::vector<double> capacitance_;
    std::vector<unsigned char> keep_, sample_;
    std::vector<std::vector<Entry>> entries_;
    std::vector<Sample> samples_;
    std::unique_ptr<Epetra_CrsMatrix> approximation_;
    std::unique_ptr<ExactApproximation> inverse_;
    std::unique_ptr<Epetra_Vector> previous_physical_;
public:
    Cache(const std::string& path,const Epetra_CrsMatrix& a): model_(path) {
        require(a.Comm().NumProc()==1,"wire-PC supports serial execution only");
        std::ifstream in(path,std::ios::binary); char magic[8]; read(in,magic,8);
        require(std::string(magic,8)=="OPLLCAP1","wire-PC metadata version");
        read(in,&n_,1); read(in,&m_,1);
        require(n_==a.NumGlobalRows() && m_>0,"wire-PC metadata dimensions");
        row_.resize(n_+1); col_.resize(m_); capacitance_.resize(m_); keep_.resize(m_); sample_.resize(m_);
        read(in,row_.data(),row_.size()); read(in,col_.data(),col_.size());
        read(in,capacitance_.data(),capacitance_.size()); read(in,keep_.data(),keep_.size()); read(in,sample_.data(),sample_.size());
        require(in.peek()==EOF && row_[0]==0 && row_[n_]==m_,"wire-PC metadata length");
        entries_.resize(n_); std::vector<int> counts(n_);
        size_t expected_samples=0;
        for(int i=0;i<n_;++i) {
            require(a.RowMap().GID(i)==i && row_[i+1]>=row_[i],"wire-PC row map");
            for(int k=row_[i];k<row_[i+1];++k) {
                require(col_[k]>=0 && col_[k]<n_ && col_[k]!=i &&
                    std::isfinite(capacitance_[k]) && capacitance_[k]!=0.,"wire-PC C entry");
                require(k==row_[i] || col_[k-1]<col_[k],"wire-PC C ordering");
                require(keep_[k]<=1 && sample_[k]<=1,"wire-PC metadata flags");
                expected_samples+=sample_[k];
            }
            int count=0; double* values=nullptr; int* columns=nullptr;
            require(a.ExtractMyRowView(i,count,values,columns)==0,"wire-PC row extraction");
            for(int p=0;p<count;++p) {
                int gid=a.ColMap().GID(columns[p]);
                auto begin=col_.begin()+row_[i], end=col_.begin()+row_[i+1];
                auto found=std::lower_bound(begin,end,gid);
                int k=(found!=end && *found==gid) ? int(found-col_.begin()) : -1;
                if(k>=0 && sample_[k]) samples_.push_back({i,p,gid,capacitance_[k]});
                if(k<0 || keep_[k]) entries_[i].push_back({p,gid,k<0 ? 0. : capacitance_[k]});
            }
            counts[i]=int(entries_[i].size()); require(counts[i]>0,"empty wire-PC row");
        }
        require(samples_.size()==expected_samples && samples_.size()>=2,"wire-PC coefficient samples");
        approximation_.reset(new Epetra_CrsMatrix(Copy,a.RowMap(),counts.data()));
        for(int i=0;i<n_;++i) {
            std::vector<int> columns; std::vector<double> zeros(counts[i],0.);
            for(const auto& e:entries_[i]) columns.push_back(e.gid);
            require(approximation_->InsertGlobalValues(i,counts[i],zeros.data(),columns.data())==0,"wire-PC graph insertion");
        }
        require(approximation_->FillComplete()==0,"wire-PC FillComplete");
    }
    int solve(Epetra_LinearProblem& problem,const std::string& path) {
        auto* a=dynamic_cast<Epetra_CrsMatrix*>(problem.GetMatrix());
        require(a && a->NumGlobalRows()==n_ && path==model_ && a->Comm().NumProc()==1,"wire-PC problem identity");
        require(problem.GetRHS()->NumVectors()==1 && problem.GetLHS()->NumVectors()==1,"wire-PC requires one RHS");
        auto begin=std::chrono::steady_clock::now();
        std::vector<double> ratios; ratios.reserve(samples_.size());
        for(const auto& s:samples_) {
            int count=0; double* values=nullptr; int* columns=nullptr;
            require(a->ExtractMyRowView(s.row,count,values,columns)==0 && s.source<count &&
                a->ColMap().GID(columns[s.source])==s.gid,"wire-PC sample graph changed");
            ratios.push_back(values[s.source]/s.capacitance);
        }
        std::sort(ratios.begin(),ratios.end()); double alpha=ratios[ratios.size()/2];
        require(std::isfinite(alpha) && alpha>=0.,"wire-PC C multiplier");
        for(double ratio:ratios) require(std::abs(ratio-alpha)<=1e-9*std::max(1.,std::abs(alpha)),"wire-PC C coefficient mismatch");
        Epetra_Vector rs(a->RowMap()), cs(a->DomainMap()); cs.PutScalar(0.);
        for(int i=0;i<n_;++i) {
            int count; double* values; int* columns; require(a->ExtractMyRowView(i,count,values,columns)==0,"wire-PC row view");
            double maximum=0.; for(int j=0;j<count;++j) maximum=std::max(maximum,std::abs(values[j]));
            require(maximum>0. && std::isfinite(maximum),"wire-PC zero or invalid row"); rs[i]=1./maximum;
            for(int j=0;j<count;++j) { int gid=a->ColMap().GID(columns[j]); cs[gid]=std::max(cs[gid],rs[i]*std::abs(values[j])); }
        }
        for(int i=0;i<n_;++i) { require(cs[i]>0. && std::isfinite(cs[i]),"wire-PC zero column"); cs[i]=1./cs[i]; }
        for(int i=0;i<n_;++i) {
            int count; double* values; int* columns; require(a->ExtractMyRowView(i,count,values,columns)==0,"wire-PC row update");
            std::vector<int> gids; std::vector<double> numeric;
            for(const auto& e:entries_[i]) {
                require(e.source<count && a->ColMap().GID(columns[e.source])==e.gid,"wire-PC approximation graph changed");
                gids.push_back(e.gid); numeric.push_back(rs[i]*(values[e.source]-alpha*e.capacitance)*cs[e.gid]);
            }
            require(approximation_->ReplaceGlobalValues(i,int(gids.size()),numeric.data(),gids.data())==0,"wire-PC value replacement");
        }
        if(!inverse_) inverse_.reset(new ExactApproximation(*approximation_)); else inverse_->refactor();
        Epetra_CrsMatrix scaled(*a); require(scaled.LeftScale(rs)==0 && scaled.RightScale(cs)==0,"wire-PC scaling");
        Epetra_Vector x(a->DomainMap()), rhs(a->RangeMap()), residual(a->RangeMap()); x.PutScalar(0.);
        for(int i=0;i<n_;++i) rhs[i]=rs[i]*(*problem.GetRHS())[0][i];
        double bn=0.; rhs.Norm2(&bn); int code=0, iterations=0;
        bool seed_used=false; double seed_relative=1.;
        if(previous_physical_ && bn>0.) {
            Epetra_Vector trial(a->DomainMap()), action(a->RangeMap());
            for(int i=0;i<n_;++i) trial[i]=(*previous_physical_)[i]/cs[i];
            require(scaled.Multiply(false,trial,action)==0,"warm-start projection matvec");
            double denominator=0., numerator=0.;
            require(action.Dot(action,&denominator)==0 && action.Dot(rhs,&numerator)==0,"warm-start projection dot");
            if(std::isfinite(denominator) && denominator>0. && std::isfinite(numerator)) {
                double coefficient=numerator/denominator;
                Epetra_Vector projected_residual(rhs);
                projected_residual.Update(-coefficient,action,1.);
                double norm=0.; projected_residual.Norm2(&norm); seed_relative=norm/bn;
                if(std::isfinite(seed_relative) && seed_relative<.5) {
                    x.Update(coefficient,trial,0.); seed_used=true;
                }
            }
        }
        std::cout << "OpenPLL_wire_seed call=" << calls_+1 << " used=" << seed_used
            << " predicted_relative_residual=" << std::setprecision(17) << seed_relative << std::endl;
        if(bn>0.) {
            Epetra_LinearProblem scaled_problem(&scaled,&x,&rhs); AztecOO solver(scaled_problem);
            require(solver.SetPrecOperator(inverse_.get())==0,"wire-PC SetPrecOperator");
            solver.SetAztecOption(AZ_solver,AZ_gmres); solver.SetAztecOption(AZ_kspace,50);
            solver.SetAztecOption(AZ_output,AZ_none); solver.SetAztecOption(AZ_scaling,AZ_none); solver.SetAztecOption(AZ_conv,AZ_rhs);
            code=solver.Iterate(300,1e-12); iterations=solver.NumIters();
        }
        require(scaled.Multiply(false,x,residual)==0,"wire-PC true residual"); residual.Update(-1.,rhs,1.);
        double rn=0.; residual.Norm2(&rn); double relative=bn>0. ? rn/bn : rn;
        if(code==0 && std::isfinite(relative) && relative<=1e-12) {
            if(!previous_physical_) previous_physical_.reset(new Epetra_Vector(a->DomainMap()));
            for(int i=0;i<n_;++i) {
                (*problem.GetLHS())[0][i]=cs[i]*x[i];
                (*previous_physical_)[i]=cs[i]*x[i];
            }
        } else code=1;
        double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
        std::cout << "OpenPLL_wire_PC call=" << ++calls_ << " alpha=" << std::setprecision(17) << alpha
            << " iterations=" << iterations << " scaled_true_relative_residual=" << relative
            << " seconds=" << seconds << " status=" << code << std::endl;
        return code;
    }
};
inline int solve(Epetra_LinearProblem& problem,bool transpose) {
    try {
        require(!transpose,"wire-PC transpose solve unsupported");
        const char* path=std::getenv("OPENPLL_WIRE_PC"); require(path && *path,"wire-PC metadata missing");
        auto* matrix=dynamic_cast<Epetra_CrsMatrix*>(problem.GetMatrix()); require(matrix,"wire-PC needs explicit Epetra CRS");
        static std::unique_ptr<Cache> cache;
        if(!cache) cache.reset(new Cache(path,*matrix));
        return cache->solve(problem,path);
    } catch(const std::exception& ex) { std::cerr << "OpenPLL_wire_PC error: " << ex.what() << std::endl; return 1; }
}
}
#endif
