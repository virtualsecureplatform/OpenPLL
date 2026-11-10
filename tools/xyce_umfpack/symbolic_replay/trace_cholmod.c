#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <cholmod.h>
cholmod_factor *cholmod_analyze(cholmod_sparse *a,cholmod_common *common){
 typedef cholmod_factor *(*function)(cholmod_sparse*,cholmod_common*);
 function real=(function)dlsym(RTLD_NEXT,"cholmod_analyze");if(!real)abort();
 fprintf(stderr,"OPENPLL_ORDER_TRACE begin cholmod_analyze rows=%zu entries_capacity=%zu\n",a->nrow,a->nzmax);fflush(stderr);
 cholmod_factor *result=real(a,common);
 fprintf(stderr,"OPENPLL_ORDER_TRACE end cholmod_analyze status=%d\n",common->status);fflush(stderr);return result;
}
