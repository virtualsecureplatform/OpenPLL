"""Diagnostic source/driver copy selection; copy-only cases never qualify RC."""


def transform(text):
    needle = '#include <stdio.h>'
    if text.count(needle) != 1:
        raise ValueError('one native stdio include required')
    text = text.replace(needle, needle + '\n#include <time.h>')
    start = text.index('ResExtractNet(node, resisdata, cellname)')
    end = text.index('\n/*', start)
    part = text[start:end]
    needle = '    devPtr\t\t*tptr;'
    if part.count(needle) != 1:
        raise ValueError('one native copy-context declaration required')
    part = part.replace(needle, needle + '\n    Point rcCopyPoint;\n    TileType rcCopyType;\n    clock_t rcCopyStarted;')
    needle = '''    scx.scx_area.r_ll.p_x = node->location.p_x - 2;
    scx.scx_area.r_ll.p_y = node->location.p_y - 2;
    scx.scx_area.r_ur.p_x = node->location.p_x + 2;
    scx.scx_area.r_ur.p_y = node->location.p_y + 2;
    startpoint = node->location;'''
    replacement = '''    rcCopyPoint = node->location;
    rcCopyType = node->type;
    if (getenv("OPENPLL_RC_COPY_FROM_DRIVER") != NULL &&
        (resisdata->rg_status & DRIVEONLY))
    {
        rcCopyPoint = *resisdata->rg_devloc;
        rcCopyType = resisdata->rg_ttype;
    }
    if (getenv("OPENPLL_RC_COPY_TRACE") != NULL)
    {
        TxPrintf("OPENPLL_RC_COPY_TRACE stage=start net=%s seed=%d,%d seed_type=%s drive=%d,%d drive_type=%s\\n",
            node->name, rcCopyPoint.p_x, rcCopyPoint.p_y, DBTypeLongNameTbl[rcCopyType],
            resisdata->rg_devloc->p_x, resisdata->rg_devloc->p_y,
            DBTypeLongNameTbl[resisdata->rg_ttype]);
        TxFlushOut();
    }
    rcCopyStarted = clock();
    scx.scx_area.r_ll.p_x = rcCopyPoint.p_x - 2;
    scx.scx_area.r_ll.p_y = rcCopyPoint.p_y - 2;
    scx.scx_area.r_ur.p_x = rcCopyPoint.p_x + 2;
    scx.scx_area.r_ur.p_y = rcCopyPoint.p_y + 2;
    startpoint = rcCopyPoint;'''
    if part.count(needle) != 1:
        raise ValueError('one original native geometry copy seed required')
    part = part.replace(needle, replacement)
    part = part.replace('if (node->type != TT_SPACE)', 'if (rcCopyType != TT_SPACE)')
    part = part.replace('&DBConnectTbl[node->type]', '&DBConnectTbl[rcCopyType]')
    needle = '    TTMaskZero(&ResSDTypesBitMask);'
    probe = '''    if (getenv("OPENPLL_RC_COPY_TRACE") != NULL)
    {
        Tile *probeTile;
        Point probePoint = *resisdata->rg_devloc;
        int plane = DBPlane(resisdata->rg_ttype);
        probeTile = PlaneGetHint(ResUse->cu_def->cd_planes[plane]);
        GOTOPOINT(probeTile, &probePoint);
        TxPrintf("OPENPLL_RC_COPY_TRACE stage=end net=%s cpu_s=%g drive=%d,%d expected=%s found_left=%s found_right=%s\\n",
            node->name, (double)(clock()-rcCopyStarted)/CLOCKS_PER_SEC,
            probePoint.p_x, probePoint.p_y, DBTypeLongNameTbl[resisdata->rg_ttype],
            DBTypeLongNameTbl[TiGetLeftType(probeTile)], DBTypeLongNameTbl[TiGetRightType(probeTile)]);
        TxFlushOut();
        if (getenv("OPENPLL_RC_COPY_PREFLIGHT_ONLY") != NULL)
        {
            ExtResetTiles(scx.scx_use->cu_def, CLIENTDEFAULT);
            return TRUE;
        }
    }

'''
    if part.count(needle) != 1:
        raise ValueError('one native post-copy diagnostic location required')
    part = part.replace(needle, probe + needle)
    return text[:start] + part + text[end:]
