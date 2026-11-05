// Reuse storage only: update every scaled coefficient from original A.
#ifndef OPENPLL_SCALED_CRS_CACHE_H
#define OPENPLL_SCALED_CRS_CACHE_H
#include <Epetra_CrsMatrix.h>
#include <Epetra_Vector.h>
#include <stdexcept>

namespace OpenPLLScaledCrs {
class Cache {
    Epetra_CrsMatrix scaled_;
    int* offsets_=nullptr;int* columns_=nullptr;double* values_=nullptr;
    static void check(bool ok,const char* message) {
        if(!ok) throw std::runtime_error(message);
    }
public:
    explicit Cache(const Epetra_CrsMatrix& original):scaled_(original) {
        check(original.Comm().NumProc()==1,"scaled cache requires serial maps");
        check(scaled_.OptimizeStorage()==0,"scaled cache packing");
        check(scaled_.ExtractCrsDataPointers(offsets_,columns_,values_)==0,"scaled cache CSR view");
    }
    Epetra_CrsMatrix& update(const Epetra_CrsMatrix& original,
                            const Epetra_Vector& row_scale,const Epetra_Vector& column_scale) {
        check(original.NumMyRows()==scaled_.NumMyRows() &&
              original.NumMyNonzeros()==scaled_.NumMyNonzeros() &&
              original.RowMap().SameAs(scaled_.RowMap()) &&
              original.ColMap().SameAs(scaled_.ColMap()) &&
              row_scale.Map().SameAs(scaled_.RowMap()) &&
              column_scale.Map().SameAs(scaled_.DomainMap()),"scaled cache maps changed");
        for(int i=0;i<original.NumMyRows();++i) {
            int count=0;double* source_values=nullptr;int* source_columns=nullptr;
            check(original.ExtractMyRowView(i,count,source_values,source_columns)==0,
                  "scaled cache source row");
            check(count==offsets_[i+1]-offsets_[i],"scaled cache row graph changed");
            for(int j=0;j<count;++j) {
                int target=offsets_[i]+j;
                check(columns_[target]==source_columns[j],"scaled cache column graph changed");
                int gid=original.ColMap().GID(source_columns[j]);
                // Match Epetra LeftScale followed by RightScale, without
                // retaining any coefficient from the preceding solve.
                values_[target]=(source_values[j]*row_scale[i])*column_scale[gid];
            }
        }
        return scaled_;
    }
};
}
#endif
