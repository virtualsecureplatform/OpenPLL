"""Opt-in native RC reference breakpoint; no arbitrary first-node attachment."""

def transform_main(text):
    before='    ResMakePortBreakpoints(ResUse->cu_def);'
    after='''    /* Preserve the physical extraction reference point for lumped C.
     * Only the private resistance workspace gains this breakpoint.
     */
    {
        bool addref = (getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL)
            && !(node->status & PORTNODE)
            && node->location.p_x > MINFINITY && node->location.p_x < INFINITY
            && node->location.p_y > MINFINITY && node->location.p_y < INFINITY;
        int saved_status = node->status;
        TileType saved_type = node->rs_ttype;
        Rect saved_box = node->rs_bbox;
        Point saved_drive = node->drivepoint;
        if (addref)
        {
            node->rs_bbox.r_ll = node->location;
            node->rs_bbox.r_ur.p_x = node->location.p_x + 1;
            node->rs_bbox.r_ur.p_y = node->location.p_y + 1;
            node->drivepoint = node->location;
            node->rs_ttype = node->type;
            node->status |= PORTNODE;
        }
        ResMakePortBreakpoints(ResUse->cu_def);
        if (addref)
        {
            node->status = saved_status;
            node->rs_ttype = saved_type;
            node->rs_bbox = saved_box;
            node->drivepoint = saved_drive;
        }
    }'''
    if text.count(before)!=1 or 'OPENPLL_RC_EXPLICIT_COUPLING' in text:raise ValueError('one unmodified native breakpoint call required')
    return text.replace(before,after)

def transform_read(text):
    before='    if (ResOptionsFlags & ResOpt_Signal)\n    {\n        node1->capacitance += MagAtof(argv[COUPLEVALUE]);'
    after='    if ((ResOptionsFlags & ResOpt_Signal) &&\n            getenv("OPENPLL_RC_EXPLICIT_COUPLING") == NULL)\n    {\n        node1->capacitance += MagAtof(argv[COUPLEVALUE]);'
    if text.count(before)!=1:raise ValueError('one native coupling import branch required')
    return text.replace(before,after)
