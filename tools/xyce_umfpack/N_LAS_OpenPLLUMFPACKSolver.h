// Experimental exact UMFPACK backend for the assembled PLL; isolated from stock Xyce.
#ifndef OPENPLL_XYCE_UMFPACK_SOLVER_H
#define OPENPLL_XYCE_UMFPACK_SOLVER_H
#include <N_LAS_Solver.h>
#include <N_LAS_EpetraProblem.h>
#include <N_LAS_TransformTool.h>
#include <N_UTL_OptionBlock.h>
#include <N_ERH_ErrorMgr.h>
#include <Epetra_CrsMatrix.h>
#include <Epetra_Comm.h>
#include <Epetra_Map.h>
#include <Epetra_Import.h>
#include <Epetra_Export.h>
#include <Epetra_MultiVector.h>
#include <umfpack.h>
#include <chrono>
#include <memory>
#include <vector>
#include <cmath>
#include <stdexcept>
#include <iostream>
namespace Xyce { namespace Linear {
class OpenPLLUMFPACKSolver : public Solver {
 Epetra_LinearProblem *original_,*transformed_=nullptr;
 Teuchos::RCP<Transform> transform_;
 std::unique_ptr<Epetra_Map> rootMap_;
 std::unique_ptr<Epetra_Import> matrixImport_,rhsImport_;
 std::unique_ptr<Epetra_Export> solutionExport_;
 std::unique_ptr<Epetra_CrsMatrix> rootMatrix_;
 std::unique_ptr<Epetra_MultiVector> rootRHS_,rootSolution_;
 std::vector<int> ap_,ai_;
 std::vector<double> ax_;
 void *symbolic_=nullptr,*numeric_=nullptr;
 double control_[UMFPACK_CONTROL],info_[UMFPACK_INFO];
 bool isRoot_,numericValid_=false;
 long calls_=0,factors_=0,symbolics_=0,failures_=0;
 static void require(bool okay,const char *message) { if(!okay)throw std::runtime_error(message); }
 int factorRoot() {
  numericValid_=false;
  const int n=rootMatrix_->NumGlobalRows();
  require(rootMatrix_->RowMap().MinMyGID()==0 && rootMatrix_->RowMap().MaxMyGID()==n-1,"UMFPACK root map must be contiguous from zero");
  std::vector<int> ap(n+1,0),ai(rootMatrix_->NumMyNonzeros());std::vector<double> ax(ai.size());
  for(int i=0;i<n;i++) {int count;double *v;int *idx;require(rootMatrix_->ExtractMyRowView(i,count,v,idx)==0,"UMFPACK row extraction failed");for(int k=0;k<count;k++){int col=rootMatrix_->ColMap().GID(idx[k]);require(col>=0&&col<n,"UMFPACK column index out of range");ap[col+1]++;}}
  for(int i=0;i<n;i++)ap[i+1]+=ap[i];auto next=ap;
  for(int i=0;i<n;i++) {int count;double *v;int *idx;rootMatrix_->ExtractMyRowView(i,count,v,idx);for(int k=0;k<count;k++){int at=next[rootMatrix_->ColMap().GID(idx[k])]++;ai[at]=rootMatrix_->RowMap().GID(i);ax[at]=v[k];}}
  if(ap!=ap_ || ai!=ai_) {umfpack_di_free_symbolic(&symbolic_);ap_=std::move(ap);ai_=std::move(ai);}
  ax_=std::move(ax);
  if(!symbolic_) {int s=umfpack_di_symbolic(n,n,ap_.data(),ai_.data(),ax_.data(),&symbolic_,control_,info_);symbolics_++;if(s!=UMFPACK_OK)return s;}
  umfpack_di_free_numeric(&numeric_);numericValid_=false;factors_++;
  int status=umfpack_di_numeric(ap_.data(),ai_.data(),ax_.data(),symbolic_,&numeric_,control_,info_);
  numericValid_=status==UMFPACK_OK;return status;
 }
public:
 OpenPLLUMFPACKSolver(Problem &problem,const Util::OptionBlock &options):Solver(problem,false),original_(&dynamic_cast<EpetraProblem&>(problem).epetraObj()),isRoot_(original_->GetMatrix()->Comm().MyPID()==0) {umfpack_di_defaults(control_);setOptions(options);}
 ~OpenPLLUMFPACKSolver() override {umfpack_di_free_numeric(&numeric_);umfpack_di_free_symbolic(&symbolic_);if(isRoot_)std::cerr<<"OpenPLL UMFPACK adapter: calls="<<calls_<<" numeric="<<factors_<<" symbolic="<<symbolics_<<" failures="<<failures_<<std::endl;}
 bool setOptions(const Util::OptionBlock &options) override {
  if(Teuchos::is_null(transform_)) {
   Util::OptionBlock copy(options);bool amd=false,partition=false,singleton=false;
   for(auto it=copy.begin();it!=copy.end();++it){auto tag=it->uTag();amd|=tag=="TR_AMD";partition|=tag=="TR_PARTITION";singleton|=tag=="TR_SINGLETON_FILTER";}
   if(!amd)copy.addParam(Util::Param("TR_amd",0));if(!partition)copy.addParam(Util::Param("TR_partition",0));if(!singleton)copy.addParam(Util::Param("TR_singleton_filter",0));copy.addParam(Util::Param("TR_reindex",1));
   transform_=TransformTool()(copy);
  }
  return true;
 }
 int doSolve(bool reuse_factors,bool transpose=false) override {
  auto start=std::chrono::steady_clock::now();calls_++;nanEntries_.clear();
  Epetra_LinearProblem *problem=original_;
  if(!Teuchos::is_null(transform_)){if(!transformed_)transformed_=&((*transform_)(*original_));transform_->fwd();problem=transformed_;}
  auto *matrix=dynamic_cast<Epetra_CrsMatrix*>(problem->GetMatrix());
  require(matrix!=nullptr,"UMFPACK requires an assembled Epetra matrix");const Epetra_Comm &comm=matrix->Comm();
  if(!rootMap_) {
   const int n=matrix->NumGlobalRows();rootMap_.reset(new Epetra_Map(n,isRoot_?n:0,0,comm));
   matrixImport_.reset(new Epetra_Import(*rootMap_,matrix->RowMap()));rhsImport_.reset(new Epetra_Import(*rootMap_,problem->GetRHS()->Map()));solutionExport_.reset(new Epetra_Export(*rootMap_,problem->GetLHS()->Map()));
   rootMatrix_.reset(new Epetra_CrsMatrix(Copy,*rootMap_,0));require(rootMatrix_->Import(*matrix,*matrixImport_,Insert)==0,"UMFPACK initial matrix gather failed");require(rootMatrix_->FillComplete(*rootMap_,*rootMap_)==0,"UMFPACK gathered matrix finalization failed");rootMatrix_->OptimizeStorage();
  }
  const int vectors=problem->GetRHS()->NumVectors();
  if(!rootRHS_ || rootRHS_->NumVectors()!=vectors){rootRHS_.reset(new Epetra_MultiVector(*rootMap_,vectors));rootSolution_.reset(new Epetra_MultiVector(*rootMap_,vectors));}
  int needFactor=isRoot_ && (!reuse_factors || !numericValid_);comm.Broadcast(&needFactor,1,0);int status=0;
  if(needFactor){int local=rootMatrix_->Import(*matrix,*matrixImport_,Insert);int okay=local==0,allOkay=0;comm.MinAll(&okay,&allOkay,1);if(!allOkay)status=UMFPACK_ERROR_invalid_matrix;}
  require(rootRHS_->Import(*problem->GetRHS(),*rhsImport_,Insert)==0,"UMFPACK RHS gather failed");
  if(isRoot_ && status==0) {
   try {
    if(needFactor)status=factorRoot();
    if(status==UMFPACK_OK)for(int j=0;j<vectors;j++){status=umfpack_di_solve(transpose?UMFPACK_At:UMFPACK_A,ap_.data(),ai_.data(),ax_.data(),(*rootSolution_)[j],(*rootRHS_)[j],numeric_,control_,info_);if(status!=UMFPACK_OK)break;for(int i=0;i<rootSolution_->MyLength();i++)if(!std::isfinite((*rootSolution_)[j][i])){status=UMFPACK_ERROR_invalid_Numeric_object;break;}if(status!=UMFPACK_OK)break;}
   } catch(const std::exception &e){std::cerr<<"OpenPLL UMFPACK exception: "<<e.what()<<std::endl;status=UMFPACK_ERROR_internal_error;numericValid_=false;}
  }
  comm.Broadcast(&status,1,0);
  if(status!=UMFPACK_OK)numericValid_=false;
  if(status==UMFPACK_OK)require(problem->GetLHS()->Export(*rootSolution_,*solutionExport_,Insert)==0,"UMFPACK solution scatter failed");
  else {problem->GetLHS()->PutScalar(0.0);failures_++;Report::UserWarning0()<<"UMFPACK linear solve failed (status "<<status<<"), returning zero solution to nonlinear solver.";}
  if(!Teuchos::is_null(transform_))transform_->rvs();
  solutionTime_=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();return status==UMFPACK_OK?0:-1;
 }
};
}}
#endif
