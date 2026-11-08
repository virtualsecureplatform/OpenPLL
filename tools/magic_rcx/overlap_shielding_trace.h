/* Diagnostic overlap support; split tiles remain explicitly unqualified. */
static unsigned long openpllOverlapId = 0;
static void openpllOverlapSupport(const char *kind, NodeRegion *a,
    NodeRegion *b, const Rect *box, int area, int plane1, int plane2,
    int split, int direction, int side, double coefficient)
{
    FILE *f = openpllTraceFile;
    if (!f) return;
    fprintf(f, "{\"kind\":\"%s\",\"cell\":", kind);
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"overlap_id\":%lu,\"node1_id\":\"%p\",\"node2_id\":\"%p\",\"box\":[%d,%d,%d,%d],\"native_area\":%d,\"plane1\":%d,\"plane2\":%d,\"split\":%s,\"split_direction\":%d,\"split_side\":%d,\"coefficient_hex\":\"%a\",\"pointwise_placement_qualified\":false}\n",
        openpllTraceEpoch, openpllOverlapId, (void *)a, (void *)b,
        box->r_xbot, box->r_ybot, box->r_xtop, box->r_ytop,
        area, plane1, plane2, split ? "true" : "false", direction,
        side, coefficient);
}
