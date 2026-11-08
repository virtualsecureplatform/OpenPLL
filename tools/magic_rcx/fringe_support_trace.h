/* Per-rule fringe diagnostics. Does not alter native arithmetic. */
static unsigned long openpllFringeId = 0;
static void openpllFringeSupport(const char *kind, NodeRegion *a,
    NodeRegion *b, Boundary *bp, const Rect *box, int reference_length,
    int span, int plane1, int plane2, double cmult, double smult,
    double cfrac, double sfrac, double cshield, double sshield,
    double coefficient, int split)
{
    FILE *f = openpllTraceFile;
    Rect *edge = &bp->b_segment;
    if (!f) return;
    fprintf(f, "{\"kind\":\"%s\",\"cell\":", kind);
    openpllTraceString(f, openpllTraceCell);
    fprintf(f, ",\"epoch\":%lu,\"fringe_id\":%lu,\"node1_id\":\"%p\",\"node2_id\":\"%p\",\"box\":[%d,%d,%d,%d],\"boundary\":[%d,%d,%d,%d],\"direction\":%d,\"reference_length\":%d,\"span\":%d,\"plane1\":%d,\"plane2\":%d,\"coupling_multiplier_hex\":\"%a\",\"substrate_multiplier_hex\":\"%a\",\"coupling_fraction_hex\":\"%a\",\"substrate_fraction_hex\":\"%a\",\"coupling_shield_hex\":\"%a\",\"substrate_shield_hex\":\"%a\",\"coefficient_hex\":\"%a\",\"split\":%s,\"pointwise_placement_qualified\":false}\n",
        openpllTraceEpoch, openpllFringeId, (void *)a, (void *)b,
        box->r_xbot, box->r_ybot, box->r_xtop, box->r_ytop,
        edge->r_xbot, edge->r_ybot, edge->r_xtop, edge->r_ytop,
        bp->b_direction, reference_length, span, plane1, plane2,
        cmult, smult, cfrac, sfrac, cshield, sshield, coefficient,
        split ? "true" : "false");
}
