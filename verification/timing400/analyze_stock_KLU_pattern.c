/* Standalone symbolic analysis using the unchanged installed Trilinos KLU.
 * No numerical factorization and no modification of the simulation engine. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "trilinos_klu_decl.h"

int main(int argc, char **argv)
{
    if (argc != 2 || sizeof(int) != 4) return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 3;
    int shape[2];
    if (fread(shape, sizeof(int), 2, f) != 2 || shape[0] <= 0 || shape[1] <= 0) return 4;
    int n = shape[0], nz = shape[1];
    int *ap = malloc(((size_t)n + 1) * sizeof(int));
    int *ai = malloc((size_t)nz * sizeof(int));
    if (!ap || !ai) return 5;
    if (fread(ap, sizeof(int), (size_t)n + 1, f) != (size_t)n + 1 ||
        fread(ai, sizeof(int), nz, f) != (size_t)nz || fgetc(f) != EOF) return 6;
    fclose(f);
    if (ap[0] != 0 || ap[n] != nz) return 7;
    trilinos_klu_common common;
    if (!trilinos_klu_defaults(&common)) return 8;
    trilinos_klu_symbolic *s = trilinos_klu_analyze(n, ap, ai, &common);
    if (!s || common.status != TRILINOS_KLU_OK) return 9;
    printf("{\"n\":%d,\"nz\":%d,\"ordering\":%d,\"btf\":%d,"
           "\"blocks\":%d,\"max_block\":%d,\"estimated_L_nnz\":%.17g,"
           "\"estimated_U_nnz\":%.17g,\"estimated_flops\":%.17g,"
           "\"symbolic_peak_bytes\":%zu}\n",
           n, nz, s->ordering, s->do_btf, s->nblocks, s->maxblock,
           s->lnz, s->unz, s->est_flops, common.mempeak);
    trilinos_klu_free_symbolic(&s, &common);
    free(ap); free(ai);
    return 0;
}
