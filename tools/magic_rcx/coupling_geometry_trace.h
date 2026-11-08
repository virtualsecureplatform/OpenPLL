/* Diagnostic coupling geometry only. No capacitance arithmetic is changed.
 * Boxes describe native search support; unresolved shielding is not a pointwise
 * capacitance-placement model. Set OPENPLL_COUPLING_TRACE before tool startup.
 */
#ifndef OPENPLL_COUPLING_GEOMETRY_TRACE_H
#define OPENPLL_COUPLING_GEOMETRY_TRACE_H
#include <stdlib.h>
static FILE *openpllTraceFile = NULL;
static int openpllTraceInitialized = 0;
static const char *openpllTraceCell = NULL;
static unsigned long openpllTraceEpoch = 0;
static char openpllTraceBuffer[1048576];
static void openpllTraceString(FILE *f, const char *s)
{
    const unsigned char *p = (const unsigned char *)s;
    fputc('"', f);
    for (; p && *p; p++) {
        if (*p == '"' || *p == '\\') {fputc('\\', f); fputc(*p, f);}
        else if (*p < 32) fprintf(f, "\\u%04x", (unsigned)*p);
        else fputc(*p, f);
    }
    fputc('"', f);
}
static void openpllTraceEvent(NodeRegion *a, NodeRegion *b, CapValue cap,
    const char *kind, int plane1, int plane2, const Rect *box1,
    const Rect *box2, int direction, int measure, int separation)
{
    const char *path;
    FILE *f;
    if (!openpllTraceInitialized) {
        openpllTraceInitialized = 1;
        path = getenv("OPENPLL_COUPLING_TRACE");
        if (path && *path) {
            openpllTraceFile = fopen(path, "w");
            if (!openpllTraceFile) perror("OPENPLL_COUPLING_TRACE");
            else setvbuf(openpllTraceFile, openpllTraceBuffer, _IOFBF,
                         sizeof(openpllTraceBuffer));
        }
    }
    f = openpllTraceFile;
    if (!f || cap == 0) return;
    fprintf(f, "{\"kind\":\"%s\",\"cell\":", kind);
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"cap_native_hex\":\"%a\",\"cap_scale_hex\":\"%a\",\"node1_id\":\"%p\",\"node2_id\":\"%p\"",
            openpllTraceEpoch, (double)cap, (double)ExtCurStyle->exts_capScale,
            (void *)a, (void *)b);
    fprintf(f, ",\"plane1\":%d,\"plane2\":%d,\"box1\":[%d,%d,%d,%d],\"box2\":[%d,%d,%d,%d],\"direction\":%d,\"native_measure\":%d,\"separation\":%d,\"pointwise_placement_qualified\":false}\n",
            plane1, plane2, box1->r_xbot, box1->r_ybot,
            box1->r_xtop, box1->r_ytop, box2->r_xbot, box2->r_ybot,
            box2->r_xtop, box2->r_ytop, direction, measure, separation);
}
/* Names are observed only where the original writer already obtains them. */
static void openpllTraceNodeName(NodeRegion *node, const char *name)
{
    FILE *f = openpllTraceFile;
    if (!f) return;
    fprintf(f, "{\"kind\":\"node_name\",\"cell\":");
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"node_id\":\"%p\",\"name\":",
            openpllTraceEpoch, (void *)node);
    openpllTraceString(f, name);
    fprintf(f, "}\n");
}

#endif
