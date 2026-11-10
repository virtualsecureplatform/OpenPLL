#ifndef OPENPLL_XYCE_UMFPACK_SOLVER_H
#define OPENPLL_XYCE_UMFPACK_SOLVER_H
#include <N_LAS_Solver.h>
#include <N_LAS_EpetraProblem.h>
#include <N_LAS_TransformTool.h>
#include <N_UTL_OptionBlock.h>
#include <N_ERH_ErrorMgr.h>
#include <Epetra_CrsMatrix.h>
#include <Epetra_Comm.h>
#include <Epetra_MpiComm.h>
#include <unordered_map>
#include <cstdint>
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
 double gatherSeconds_=0,prepareSeconds_=0,solveSeconds_=0,scatterSeconds_=0;
 static double seconds(std::chrono::steady_clock::time_point t){return std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();}
 static void require(bool okay,const char *message){if(!okay)throw std::runtime_error(message);}
 std::vector<int> cachedRows_,cachedIndices_,cachedSlots_;
 void prepareRoot() {
  const int n=rootMatrix_->NumGlobalRows();
  require(rootMatrix_->RowMap().MinMyGID()==0&&rootMatrix_->RowMap().MaxMyGID()==n-1,"UMFPACK root map must be contiguous from zero");
  if(!cachedRows_.empty()) {
   require(static_cast<int>(cachedRows_.size())==n+1 && cachedRows_.back()==rootMatrix_->NumMyNonzeros(),"cached CSC dimensions changed");
   std::vector<double> values(cachedSlots_.size());
   for(int i=0;i<n;i++){int count;double *v;int *idx;require(rootMatrix_->ExtractMyRowView(i,count,v,idx)==0,"cached row extraction failed");require(count==cachedRows_[i+1]-cachedRows_[i],"cached row length changed");
    for(int k=0;k<count;k++){int at=cachedRows_[i]+k;require(idx[k]==cachedIndices_[at],"cached row index changed");values[cachedSlots_[at]]=v[k];}}
   solver_.matrixValues(std::move(values));return;
  }
  std::vector<int> ap(n+1,0),ai(rootMatrix_->NumMyNonzeros());std::vector<double> ax(ai.size());
  for(int i=0;i<n;i++){int count;double *v;int *idx;require(rootMatrix_->ExtractMyRowView(i,count,v,idx)==0,"UMFPACK row extraction failed");for(int k=0;k<count;k++){int col=rootMatrix_->ColMap().GID(idx[k]);require(col>=0&&col<n,"UMFPACK column index out of range");ap[col+1]++;}}
  for(int i=0;i<n;i++)ap[i+1]+=ap[i];auto next=ap;
  for(int i=0;i<n;i++){int count;double *v;int *idx;rootMatrix_->ExtractMyRowView(i,count,v,idx);for(int k=0;k<count;k++){int at=next[rootMatrix_->ColMap().GID(idx[k])]++;ai[at]=rootMatrix_->RowMap().GID(i);ax[at]=v[k];}}
  cachedRows_.assign(n+1,0);cachedIndices_.resize(ai.size());cachedSlots_.resize(ai.size());next=ap;
  for(int i=0;i<n;i++){int count;double *v;int *idx;rootMatrix_->ExtractMyRowView(i,count,v,idx);cachedRows_[i+1]=cachedRows_[i]+count;for(int k=0;k<count;k++){int at=cachedRows_[i]+k;cachedIndices_[at]=idx[k];cachedSlots_[at]=next[rootMatrix_->ColMap().GID(idx[k])]++;}}
  solver_.matrix(n,std::move(ap),std::move(ai),std::move(ax));
 }
 std::vector<int> valueCounts_,valueOffsets_,localRowGIDs_,localRowEnds_,localColumns_,valueSlots_;
 std::vector<double> localValues_,gatheredValues_;
 bool valueLayoutReady_=false;
 int gatherValues(Epetra_CrsMatrix &matrix) {
  const Epetra_Comm &comm=matrix.Comm();
  const auto *mpi=dynamic_cast<const Epetra_MpiComm*>(&comm);
  int okay=mpi!=nullptr && matrix.RowMap().UniqueGIDs(),allOkay=0;
  comm.MinAll(&okay,&allOkay,1);if(!allOkay)return UMFPACK_ERROR_invalid_matrix;
  int count=matrix.NumMyNonzeros();
  if(!valueLayoutReady_){
   valueCounts_.resize(comm.NumProc());comm.GatherAll(&count,valueCounts_.data(),1);
   valueOffsets_.resize(comm.NumProc());int total=0;
   for(int r=0;r<comm.NumProc();r++){valueOffsets_[r]=total;total+=valueCounts_[r];}
   std::vector<int> rows(count),columns(count);localRowEnds_.push_back(0);
   int at=0;
   for(int i=0;i<matrix.NumMyRows();i++){int n;double *v;int *idx;okay&=matrix.ExtractMyRowView(i,n,v,idx)==0;localRowGIDs_.push_back(matrix.RowMap().GID(i));
    for(int k=0;k<n;k++){rows[at]=localRowGIDs_.back();columns[at]=matrix.ColMap().GID(idx[k]);localColumns_.push_back(idx[k]);++at;}
    localRowEnds_.push_back(at);}
   okay&=at==count;comm.MinAll(&okay,&allOkay,1);if(!allOkay)return UMFPACK_ERROR_invalid_matrix;
   std::vector<int> allRows(isRoot_?total:0),allColumns(isRoot_?total:0);
   int rc=MPI_Gatherv(rows.data(),count,MPI_INT,allRows.data(),valueCounts_.data(),valueOffsets_.data(),MPI_INT,0,mpi->Comm());
   rc|=MPI_Gatherv(columns.data(),count,MPI_INT,allColumns.data(),valueCounts_.data(),valueOffsets_.data(),MPI_INT,0,mpi->Comm());
   okay=rc==MPI_SUCCESS;
   if(isRoot_){
    prepareRoot();std::unordered_map<std::uint64_t,int> slots;slots.reserve(total);
    for(int i=0;i<rootMatrix_->NumMyRows();i++){int n;double *v;int *idx;rootMatrix_->ExtractMyRowView(i,n,v,idx);
     for(int k=0;k<n;k++){auto key=(std::uint64_t(rootMatrix_->RowMap().GID(i))<<32)|std::uint32_t(rootMatrix_->ColMap().GID(idx[k]));okay&=slots.emplace(key,cachedSlots_[cachedRows_[i]+k]).second;}}
    okay&=static_cast<int>(slots.size())==total;valueSlots_.resize(total);std::vector<int> seen(total,0);
    for(int j=0;j<total;j++){auto key=(std::uint64_t(allRows[j])<<32)|std::uint32_t(allColumns[j]);auto it=slots.find(key);if(it==slots.end()){okay=0;continue;}valueSlots_[j]=it->second;okay&=++seen[it->second]==1;}
    gatheredValues_.resize(total);
   }
   comm.MinAll(&okay,&allOkay,1);if(!allOkay)return UMFPACK_ERROR_invalid_matrix;
   localValues_.resize(count);valueLayoutReady_=true;
  }
  okay=count==static_cast<int>(localColumns_.size()) && matrix.NumMyRows()==static_cast<int>(localRowGIDs_.size());
  if(okay)for(int i=0;i<matrix.NumMyRows();i++){int n;double *v;int *idx;okay&=matrix.RowMap().GID(i)==localRowGIDs_[i];okay&=matrix.ExtractMyRowView(i,n,v,idx)==0;
   if(n!=localRowEnds_[i+1]-localRowEnds_[i]){okay=0;continue;}
   for(int k=0;k<n;k++){int at=localRowEnds_[i]+k;okay&=idx[k]==localColumns_[at];localValues_[at]=v[k];}}
  comm.MinAll(&okay,&allOkay,1);if(!allOkay)return UMFPACK_ERROR_invalid_matrix;
  int rc=MPI_Gatherv(localValues_.data(),count,MPI_DOUBLE,gatheredValues_.data(),valueCounts_.data(),valueOffsets_.data(),MPI_DOUBLE,0,mpi->Comm());
  okay=rc==MPI_SUCCESS;comm.MinAll(&okay,&allOkay,1);return allOkay?0:UMFPACK_ERROR_invalid_matrix;
 }
 void prepareGatheredValues(){std::vector<double> values(gatheredValues_.size());for(size_t j=0;j<values.size();j++)values[valueSlots_[j]]=gatheredValues_[j];solver_.matrixValues(std::move(values));}
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
  std::cerr<<"OPENPLL_LINEAR_TRACE begin transform"<<std::endl;if(!Teuchos::is_null(transform_)){if(!transformed_)transformed_=&((*transform_)(*original_));transform_->fwd();problem=transformed_;}std::cerr<<"OPENPLL_LINEAR_TRACE end transform"<<std::endl;
  auto *matrix=dynamic_cast<Epetra_CrsMatrix*>(problem->GetMatrix());require(matrix,"UMFPACK requires assembled Epetra matrix");const Epetra_Comm &comm=matrix->Comm();
  if(!rootMap_){std::cerr<<"OPENPLL_LINEAR_TRACE begin root_matrix"<<std::endl;
   int n=matrix->NumGlobalRows();rootMap_.reset(new Epetra_Map(n,isRoot_?n:0,0,comm));matrixImport_.reset(new Epetra_Import(*rootMap_,matrix->RowMap()));rhsImport_.reset(new Epetra_Import(*rootMap_,problem->GetRHS()->Map()));solutionExport_.reset(new Epetra_Export(*rootMap_,problem->GetLHS()->Map()));
   rootMatrix_.reset(new Epetra_CrsMatrix(Copy,*rootMap_,0));require(rootMatrix_->Import(*matrix,*matrixImport_,Insert)==0,"UMFPACK initial gather failed");require(rootMatrix_->FillComplete(*rootMap_,*rootMap_)==0,"UMFPACK matrix finalization failed");rootMatrix_->OptimizeStorage();std::cerr<<"OPENPLL_LINEAR_TRACE end root_matrix"<<std::endl;
  }
  int vectors=problem->GetRHS()->NumVectors();if(!rootRHS_||rootRHS_->NumVectors()!=vectors){rootRHS_.reset(new Epetra_MultiVector(*rootMap_,vectors));rootSolution_.reset(new Epetra_MultiVector(*rootMap_,vectors));}
  int update=isRoot_&&(!reuse_factors||!solver_.hasNumeric());comm.Broadcast(&update,1,0);int status=0;
  auto phaseStart=std::chrono::steady_clock::now();
  std::cerr<<"OPENPLL_LINEAR_TRACE begin gather_values"<<std::endl;if(update)status=gatherValues(*matrix);std::cerr<<"OPENPLL_LINEAR_TRACE end gather_values"<<std::endl;
  require(rootRHS_->Import(*problem->GetRHS(),*rhsImport_,Insert)==0,"UMFPACK RHS gather failed");
  gatherSeconds_+=seconds(phaseStart);
  if(isRoot_&&status==0){
   try{
    phaseStart=std::chrono::steady_clock::now();
    std::cerr<<"OPENPLL_LINEAR_TRACE begin prepare_values"<<std::endl;if(update)prepareGatheredValues();std::cerr<<"OPENPLL_LINEAR_TRACE end prepare_values"<<std::endl;
    prepareSeconds_+=seconds(phaseStart); phaseStart=std::chrono::steady_clock::now();
    for(int j=0;j<vectors;j++){
     status=solver_.solve((*rootRHS_)[j],(*rootSolution_)[j],reuseEnabled_&&transientContext_,reuse_factors||j>0,transpose);
     if(status!=UMFPACK_OK)break;
     if(solver_.lastUsedReuse&&!transientContext_)DCReuseHits_++;
     for(int i=0;i<rootSolution_->MyLength();i++)if(!std::isfinite((*rootSolution_)[j][i])){status=UMFPACK_ERROR_invalid_Numeric_object;break;}
     if(status!=UMFPACK_OK)break;
    }
   solveSeconds_+=seconds(phaseStart);
   }catch(const std::exception&e){std::cerr<<"OpenPLL UMFPACK exception: "<<e.what()<<std::endl;status=UMFPACK_ERROR_internal_error;}
  }
  if(isRoot_ && calls_%100==0)std::cerr<<"OpenPLL UMFPACK progress: linear_calls="<<calls_<<" numeric_factors="<<solver_.numericCalls<<" cached_accepts="<<solver_.reuseAccepted<<" exact_hits="<<solver_.exactReuseAccepted<<" refinement_corrections="<<solver_.refinementSolves<<" DC_hits="<<DCReuseHits_<<" transient="<<transientContext_<<" krylov_steps="<<solver_.krylovSolves<<std::endl;
  phaseStart=std::chrono::steady_clock::now();
  comm.Broadcast(&status,1,0);
  if(status==UMFPACK_OK)require(problem->GetLHS()->Export(*rootSolution_,*solutionExport_,Insert)==0,"UMFPACK solution scatter failed");
  else{solver_.invalidate();problem->GetLHS()->PutScalar(0);failures_++;Report::UserWarning0()<<"UMFPACK linear solve failed (status "<<status<<"), returning zero solution to nonlinear solver.";}
  scatterSeconds_+=seconds(phaseStart);
  if(isRoot_ && calls_%100==0)std::cerr<<"OpenPLL adapter timing: calls="<<calls_<<" gather_s="<<gatherSeconds_<<" prepare_s="<<prepareSeconds_<<" solve_s="<<solveSeconds_<<" scatter_s="<<scatterSeconds_<<std::endl;
  if(!Teuchos::is_null(transform_))transform_->rvs();solutionTime_=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();return status==UMFPACK_OK?0:-1;
 }
};
}}
#endif
