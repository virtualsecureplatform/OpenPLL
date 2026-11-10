"""Keep labels as anonymous geometry breakpoints and names at physical anchors."""
MODE = 'getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'


def transform_main(text):
    start = text.index('void\nResMakePortBreakpoints(def)')
    end = text.index('\n/*', start)
    part = text[start:end]
    part = part.replace('    Rect\t*rect;', '    Rect\t*rect;\n    Rect rcPointBox;')
    needle = '\t    rect  = &(node->rs_bbox);'
    replacement = needle + '''
            if (MODE)
            {
                rcPointBox.r_ll = node->drivepoint;
                rcPointBox.r_ur.p_x = node->drivepoint.p_x + 1;
                rcPointBox.r_ur.p_y = node->drivepoint.p_y + 1;
                rect = &rcPointBox;
            }'''.replace('MODE', MODE)
    if part.count(needle) != 1:
        raise ValueError('one native named-port rectangle required')
    part = part.replace(needle, replacement)
    if 'Rect rcPointBox;' not in part:
        raise ValueError('native named-port rectangle declaration missing')
    text = text[:start] + part + text[end:]
    start = text.index('void\nResMakeLabelBreakpoints(def, resisdata)')
    end = text.index('\n/*', start)
    part = text[start:end]
    needle = '    ResExtNode  *node;'
    if part.count(needle) != 1:
        raise ValueError('one native label node declaration required')
    part = part.replace(needle, needle + '\n    ResExtNode rcAnonymousLabel;')
    needle = '''\tentry = HashFind(&ResNodeTable, slab->lab_text);
\tnode = ResExtInitNode(entry);'''
    replacement = '''        if (MODE)
        {
            memset(&rcAnonymousLabel, 0, sizeof(rcAnonymousLabel));
            node = &rcAnonymousLabel;
            /* NULL names retain geometry breakpoints without making all
             * repetitions of a logical layout label equipotential. */
            node->name = NULL;
        }
        else
        {
            entry = HashFind(&ResNodeTable, slab->lab_text);
            node = ResExtInitNode(entry);
        }'''.replace('MODE', MODE)
    if part.count(needle) != 1:
        raise ValueError('one native label lookup required')
    return text[:start] + part.replace(needle, replacement) + text[end:]


def transform_types(text):
    needle = '\trp->rp_nodename = node->name; \\\n'
    extra = '''\tif ((MODE) && node->name != NULL) { \\
\t    rp->rp_bbox.r_ll = rp->rp_loc; \\
\t    rp->rp_bbox.r_ur = rp->rp_loc; \\
\t} \\
'''.replace('MODE', MODE)
    if text.count(needle) != 1:
        raise ValueError('one native breakpoint name assignment required')
    return text.replace(needle, extra + needle)
