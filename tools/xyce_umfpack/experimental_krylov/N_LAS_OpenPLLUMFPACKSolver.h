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
#include "CheckedUMFPACK.h"
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
 CheckedUMFPACK solver_;
 bool isRoot_,reuseEnabled_,transientContext_=false;
 long calls_=0,failures_=0,DCReuseHits_=0;
 static void require(bool okay,const char *message){if(!okay)throw std::runtime_error(message);}
 void prepareRoot() {
  const int n=rootMatrix_->NumGlobalRows();
  require(rootMatrix_->RowMap().MinMyGID()==0&&rootMatrix_->RowMap().MaxMyGID()==n-1,"UMFPACK root map must be contiguous from zero");
  std::vector<int> ap(n+1,0),ai(rootMatrix_->NumMyNonzeros());std::vector<double> ax(ai.size());
  for(int i=0;i<n;i++){int count;double *v;int *idx;require(rootMatrix_->ExtractMyRowView(i,count,v,idx)==0,"UMFPACK row extraction failed");for(int k=0;k<count;k++){int col=rootMatrix_->ColMap().GID(idx[k]);require(col>=0&&col<n,"UMFPACK column index out of range");ap[col+1]++;}}
  for(int i=0;i<n;i++)ap[i+1]+=ap[i];auto next=ap;
  for(int i=0;i<n;i++){int count;double *v;int *idx;rootMatrix_->ExtractMyRowView(i,count,v,idx);for(int k=0;k<count;k++){int at=next[rootMatrix_->ColMap().GID(idx[k])]++;ai[at]=rootMatrix_->RowMap().GID(i);ax[at]=v[k];}}
  solver_.matrix(n,std::move(ap),std::move(ai),std::move(ax));
 }
public:
 OpenPLLUMFPACKSolver(Problem &problem,const Util::OptionBlock &options,bool reuse=false):Solver(problem,false),original_(&dynamic_cast<EpetraProblem&>(problem).epetraObj()),isRoot_(original_->GetMatrix()->Comm().MyPID()==0),reuseEnabled_(reuse){setOptions(options);}
 ~OpenPLLUMFPACKSolver() override {
  if(isRoot_)std::cerr<<"OpenPLL UMFPACK adapter: calls="<<calls_<<" numeric="<<solver_.numericCalls<<" symbolic="<<solver_.symbolicCalls<<" failures="<<failures_<<" reuse_attempts="<<solver_.reuseAttempts<<" reuse_accepted="<<solver_.reuseAccepted<<" exact_reuse="<<solver_.exactReuseAccepted<<" refinement_solves="<<solver_.refinementSolves<<" DC_reuse="<<DCReuseHits_<<" krylov_solves="<<solver_.krylovSolves<<std::endl;
 }
 void setTransientContext(bool active){transientContext_=active;}
 bool setOptions(const Util::OptionBlock &options) override {
  if(Teuchos::is_null(transform_)){
   Util::OptionBlock copy(options);bool amd=false,partition=false,singleton=false;
   for(auto it=copy.begin();it!=copy.end();++it){auto tag=it->uTag();amd|=tag=="TR_AMD";partition|=tag=="TR_PARTITION";singleton|=tag=="TR_SINGLETON_FILTER";}
   if(!amd)copy.addParam(Util::Param("TR_amd",0));if(!partition)copy.addParam(Util::Param("TR_partition",0));if(!singleton)copy.addParam(Util::Param("TR_singleton_filter",0));copy.addParam(Util::Param("TR_reindex",1));transform_=TransformTool()(copy);
  }
  return true;
 }
 int doSolve(bool reuse_factors,bool transpose=false) override {
  auto start=std::chrono::steady_clock::now();calls_++;nanEntries_.clear();Epetra_LinearProblem *problem=original_;
  if(!Teuchos::is_null(transform_)){if(!transformed_)transformed_=&((*transform_)(*original_));transform_->fwd();problem=transformed_;}
  auto *matrix=dynamic_cast<Epetra_CrsMatrix*>(problem->GetMatrix());require(matrix,"UMFPACK requires assembled Epetra matrix");const Epetra_Comm &comm=matrix->Comm();
  if(!rootMap_){
   int n=matrix->NumGlobalRows();rootMap_.reset(new Epetra_Map(n,isRoot_?n:0,0,comm));matrixImport_.reset(new Epetra_Import(*rootMap_,matrix->RowMap()));rhsImport_.reset(new Epetra_Import(*rootMap_,problem->GetRHS()->Map()));solutionExport_.reset(new Epetra_Export(*rootMap_,problem->GetLHS()->Map()));
   rootMatrix_.reset(new Epetra_CrsMatrix(Copy,*rootMap_,0));require(rootMatrix_->Import(*matrix,*matrixImport_,Insert)==0,"UMFPACK initial gather failed");require(rootMatrix_->FillComplete(*rootMap_,*rootMap_)==0,"UMFPACK matrix finalization failed");rootMatrix_->OptimizeStorage();
  }
  int vectors=problem->GetRHS()->NumVectors();if(!rootRHS_||rootRHS_->NumVectors()!=vectors){rootRHS_.reset(new Epetra_MultiVector(*rootMap_,vectors));rootSolution_.reset(new Epetra_MultiVector(*rootMap_,vectors));}
  int update=isRoot_&&(!reuse_factors||!solver_.hasNumeric());comm.Broadcast(&update,1,0);int status=0;
  if(update){int local=rootMatrix_->Import(*matrix,*matrixImport_,Insert);int okay=local==0,allOkay=0;comm.MinAll(&okay,&allOkay,1);if(!allOkay)status=UMFPACK_ERROR_invalid_matrix;}
  require(rootRHS_->Import(*problem->GetRHS(),*rhsImport_,Insert)==0,"UMFPACK RHS gather failed");
  if(isRoot_&&status==0){
   try{
    if(update)prepareRoot();
    for(int j=0;j<vectors;j++){
     status=solver_.solve((*rootRHS_)[j],(*rootSolution_)[j],reuseEnabled_&&transientContext_,reuse_factors||j>0,transpose);
     if(status!=UMFPACK_OK)break;
     if(solver_.lastUsedReuse&&!transientContext_)DCReuseHits_++;
     for(int i=0;i<rootSolution_->MyLength();i++)if(!std::isfinite((*rootSolution_)[j][i])){status=UMFPACK_ERROR_invalid_Numeric_object;break;}
     if(status!=UMFPACK_OK)break;
    }
   }catch(const std::exception&e){std::cerr<<"OpenPLL UMFPACK exception: "<<e.what()<<std::endl;status=UMFPACK_ERROR_internal_error;}
  }
  if(isRoot_ && calls_%100==0)std::cerr<<"OpenPLL UMFPACK progress: linear_calls="<<calls_<<" numeric_factors="<<solver_.numericCalls<<" cached_accepts="<<solver_.reuseAccepted<<" exact_hits="<<solver_.exactReuseAccepted<<" refinement_corrections="<<solver_.refinementSolves<<" DC_hits="<<DCReuseHits_<<" transient="<<transientContext_<<" krylov_steps="<<solver_.krylovSolves<<std::endl;
  comm.Broadcast(&status,1,0);
  if(status==UMFPACK_OK)require(problem->GetLHS()->Export(*rootSolution_,*solutionExport_,Insert)==0,"UMFPACK solution scatter failed");
  else{solver_.invalidate();problem->GetLHS()->PutScalar(0);failures_++;Report::UserWarning0()<<"UMFPACK linear solve failed (status "<<status<<"), returning zero solution to nonlinear solver.";}
  if(!Teuchos::is_null(transform_))transform_->rvs();solutionTime_=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();return status==UMFPACK_OK?0:-1;
 }
};
}}
#endif
