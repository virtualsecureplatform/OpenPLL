/* Diagnostic signal backtrace only; never linked into a release tool. */
#define _GNU_SOURCE
#include <execinfo.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
#include <ucontext.h>
#include <stdio.h>
static void trace_failure(int signal_number, siginfo_t *info, void *context) {
    ucontext_t *state=context;
    if (info->si_addr==(void*)0x2c) {
        char *frame=(char*)state->uc_mcontext.gregs[REG_RBP];
        int *rect=*(int**)(frame-0x68);
        char *tile=*(char**)(frame-0x40);
        dprintf(STDERR_FILENO,"SEARCH_RECT=%d,%d,%d,%d TILE_BOTTOM=%d TILE_RIGHT_TOP=%p\n",rect[0],rect[1],rect[2],rect[3],*(int*)(tile+0x2c),*(void**)(tile+0x20));
    }
    dprintf(STDERR_FILENO,"FAULT_ADDRESS=%p RIP=%llx RBP=%llx RSP=%llx RAX=%llx RBX=%llx RCX=%llx RDX=%llx RSI=%llx RDI=%llx\n",info->si_addr,(unsigned long long)state->uc_mcontext.gregs[REG_RIP],(unsigned long long)state->uc_mcontext.gregs[REG_RBP],(unsigned long long)state->uc_mcontext.gregs[REG_RSP],(unsigned long long)state->uc_mcontext.gregs[REG_RAX],(unsigned long long)state->uc_mcontext.gregs[REG_RBX],(unsigned long long)state->uc_mcontext.gregs[REG_RCX],(unsigned long long)state->uc_mcontext.gregs[REG_RDX],(unsigned long long)state->uc_mcontext.gregs[REG_RSI],(unsigned long long)state->uc_mcontext.gregs[REG_RDI]);
    void *frames[48];
    static const char marker[]="OPENPLL_DIAGNOSTIC_NATIVE_CRASH\n";
    write(STDERR_FILENO,marker,sizeof(marker)-1);
    int count=backtrace(frames,48);
    backtrace_symbols_fd(frames,count,STDERR_FILENO);
    _exit(128+signal_number);
}
__attribute__((constructor)) static void install_trace(void) {
    struct sigaction action={0};
    action.sa_sigaction=trace_failure;action.sa_flags=SA_RESETHAND|SA_SIGINFO;
    sigemptyset(&action.sa_mask);
    sigaction(SIGSEGV,&action,0);sigaction(SIGABRT,&action,0);
}
