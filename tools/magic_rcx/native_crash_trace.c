/* Diagnostic signal backtrace only; never linked into a release tool. */
#define _GNU_SOURCE
#include <execinfo.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
static void trace_failure(int signal_number) {
    void *frames[48];
    static const char marker[]="OPENPLL_DIAGNOSTIC_NATIVE_CRASH\n";
    write(STDERR_FILENO,marker,sizeof(marker)-1);
    int count=backtrace(frames,48);
    backtrace_symbols_fd(frames,count,STDERR_FILENO);
    _exit(128+signal_number);
}
__attribute__((constructor)) static void install_trace(void) {
    struct sigaction action={0};
    action.sa_handler=trace_failure;action.sa_flags=SA_RESETHAND;
    sigemptyset(&action.sa_mask);
    sigaction(SIGSEGV,&action,0);sigaction(SIGABRT,&action,0);
}
