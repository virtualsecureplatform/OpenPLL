#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <umfpack.h>
static void *read_array(const char *folder,const char *name,size_t bytes){
 char path[4096];if(snprintf(path,sizeof path,"%s/%s",folder,name)>=(int)sizeof path)exit(2);
 FILE *f=fopen(path,"rb");if(!f){perror(path);exit(2);}void *p=malloc(bytes);if(!p||fread(p,1,bytes,f)!=bytes||fgetc(f)!=EOF){fprintf(stderr,"invalid array %s\n",path);exit(2);}fclose(f);return p;
}
int main(int argc,char **argv){
 if(argc!=2)return 2;uint64_t *h=read_array(argv[1],"header.u64",32);
 if(h[0]!=0x4f504c4c43534331ULL||h[1]!=h[2]||h[1]>2147483647||h[3]>2147483647)return 2;
 int n=(int)h[1],nnz=(int)h[3];int *ap=read_array(argv[1],"columns.i32",((size_t)n+1)*4),*ai=read_array(argv[1],"rows.i32",(size_t)nnz*4);double *ax=read_array(argv[1],"values.f64",(size_t)nnz*8);
 double control[UMFPACK_CONTROL],info[UMFPACK_INFO];umfpack_di_defaults(control);control[UMFPACK_ORDERING]=UMFPACK_ORDERING_METIS;
 void *symbolic=NULL;fprintf(stderr,"OPENPLL_REPLAY begin symbolic n=%d entries=%d ordering=METIS\n",n,nnz);fflush(stderr);
 struct timespec a,b;clock_gettime(CLOCK_MONOTONIC,&a);int status=umfpack_di_symbolic(n,n,ap,ai,ax,&symbolic,control,info);clock_gettime(CLOCK_MONOTONIC,&b);
 printf("{\"status\":%d,\"rows\":%d,\"entries\":%d,\"ordering_used\":%.0f,\"strategy_used\":%.0f,\"symbolic_seconds\":%.9f,\"numeric_factorization_performed\":false}\n",status,n,nnz,info[UMFPACK_ORDERING_USED],info[UMFPACK_STRATEGY_USED],(b.tv_sec-a.tv_sec)+(b.tv_nsec-a.tv_nsec)*1e-9);fflush(stdout);
 umfpack_di_free_symbolic(&symbolic);free(ap);free(ai);free(ax);free(h);return status==UMFPACK_OK?0:1;
}
