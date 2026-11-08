/* Observe raw tile-area assignments before network merging/distribution. */
static FILE *openpllResAreaFile = NULL;
static int openpllResAreaInitialized = 0;
static void openpllResAreaRecord(resNode *node, Tile *tile, const char *site,
    double before, double added, double after, int x0, int y0, int x1,
    int y1, double weight)
{
    const char *path;
    FILE *f;
    if (!openpllResAreaInitialized) {
        openpllResAreaInitialized = 1;
        path = getenv("OPENPLL_RESISTANCE_AREA_TRACE");
        if (path && *path) {
            openpllResAreaFile = fopen(path, "w");
            if (!openpllResAreaFile) perror("OPENPLL_RESISTANCE_AREA_TRACE");
        }
    }
    f = openpllResAreaFile;
    if (!f) return;
    fprintf(f, "{\"kind\":\"raw_resistance_area\",\"node_id\":\"%p\",\"site\":\"%s\",\"node_location\":[%d,%d],\"tile_box\":[%d,%d,%d,%d],\"support_box\":[%d,%d,%d,%d],\"weight_hex\":\"%a\",\"before_hex\":\"%a\",\"native_added_hex\":\"%a\",\"after_hex\":\"%a\",\"split\":%s,\"placement_qualified\":false}\n",
        (void *)node, site, node->rn_loc.p_x, node->rn_loc.p_y,
        LEFT(tile), BOTTOM(tile), RIGHT(tile), TOP(tile), x0, y0, x1, y1,
        weight, before, added, after, IsSplit(tile) ? "true" : "false");
}
#define OPENPLL_RES_AREA(node, statement, added, x0, y0, x1, y1, weight, site) do { \
    double openpll_before = (double)(node)->rn_float.rn_area; \
    statement; \
    openpllResAreaRecord(node, tile, site, openpll_before, (double)(added), \
        (double)(node)->rn_float.rn_area, x0, y0, x1, y1, weight); \
} while (0)

/* Shared by resis translation units; never invokes a node-name generator. */
void openpllResLineage(const char *kind, resNode *node, resNode *other,
    double before, double source, double after, double scale, const char *name)
{
    const char *path;
    const unsigned char *p;
    FILE *f;
    if (!openpllResAreaInitialized) {
        openpllResAreaInitialized = 1;
        path = getenv("OPENPLL_RESISTANCE_AREA_TRACE");
        if (path && *path) {
            openpllResAreaFile = fopen(path, "w");
            if (!openpllResAreaFile) perror("OPENPLL_RESISTANCE_AREA_TRACE");
        }
    }
    f = openpllResAreaFile;
    if (!f) return;
    fprintf(f, "{\"kind\":\"%s\",\"node_id\":\"%p\",\"other_id\":\"%p\",\"before_hex\":\"%a\",\"source_hex\":\"%a\",\"after_hex\":\"%a\",\"scale_hex\":\"%a\",\"name\":", kind, (void *)node, (void *)other, before, source, after, scale);
    if (!name) fputs("null", f);
    else {
        fputc('"', f);
        for (p = (const unsigned char *)name; *p; p++) {
            if (*p == '"' || *p == '\\') {fputc('\\', f); fputc(*p, f);}
            else if (*p < 32) fprintf(f, "\\u%04x", (unsigned)*p);
            else fputc(*p, f);
        }
        fputc('"', f);
    }
    fputs(",\"placement_qualified\":false}\n", f);
}
#define OPENPLL_RES_SCALE(node, factor) do { \
    double openpll_before = (double)(node)->rn_float.rn_area; \
    (node)->rn_float.rn_area *= factor; \
    openpllResLineage("res_distribution_output", node, NULL, openpll_before, \
        0.0, (double)(node)->rn_float.rn_area, (double)(factor), NULL); \
} while (0)
