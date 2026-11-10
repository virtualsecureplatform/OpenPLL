/* Diagnostic producer: exact binary CSC capture, deliberately no simulation solve. */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <dlfcn.h>
#include <sys/stat.h>
static void failure(const char *message) { perror(message); _Exit(91); }
static void output(const char *folder,const char *name,const void *p,size_t size) {
 char path[4096]; if(snprintf(path,sizeof path,"%s/%s",folder,name)>=(int)sizeof path) failure("path too long");
 int fd=open(path,O_CREAT|O_EXCL|O_WRONLY,0600);if(fd<0)failure(path);
 const char *b=p;while(size){ssize_t n=write(fd,b,size);if(n<=0)failure("write");b+=n;size-=n;}
 if(fsync(fd)||close(fd))failure("close capture");
}
int umfpack_di_symbolic(int nr,int nc,const int *ap,const int *ai,const double *ax,void **symbolic,const double *control,double *info) {
 const char *folder=getenv("OPENPLL_CSC_CAPTURE");
 if(!folder||!*folder){
  typedef int(*function)(int,int,const int*,const int*,const double*,void**,const double*,double*);
  function real=(function)dlsym(RTLD_NEXT,"umfpack_di_symbolic");if(!real)failure("symbolic resolution");return real(nr,nc,ap,ai,ax,symbolic,control,info);
 }
 if(sizeof(int)!=4||sizeof(double)!=8||nr<=0||nc<=0||!ap||ap[0]!=0||ap[nc]<0||!ai||!ax)failure("unsupported CSC capture");
 if(mkdir(folder,0700))failure("fresh capture directory required");
 uint64_t header[]={0x4f504c4c43534331ULL,(uint64_t)nr,(uint64_t)nc,(uint64_t)ap[nc]};
 output(folder,"header.u64",header,sizeof header);output(folder,"columns.i32",ap,((size_t)nc+1)*4);output(folder,"rows.i32",ai,(size_t)ap[nc]*4);output(folder,"values.f64",ax,(size_t)ap[nc]*8);
 const char *receipt="{\"exact_binary_CSC_capture_complete\":true,\"simulation_solved\":false}\n";output(folder,"completion.json",receipt,strlen(receipt));
 fprintf(stderr,"OPENPLL_CSC_CAPTURE_COMPLETE rows=%d columns=%d entries=%d simulation_solved=false\n",nr,nc,ap[nc]);fflush(NULL);_Exit(0);
}
