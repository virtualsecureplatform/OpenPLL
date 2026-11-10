"""Carry the original C breakpoint through native merges and retain its proven alias."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'


def once(text,needle,replacement):
    if text.count(needle)!=1:raise ValueError('one native reference site required: '+repr(needle))
    return text.replace(needle,replacement)


def transform_types(text):
    text=once(text,'     char\t\t*rn_name;','     char\t\t*rn_c_reference; /* Original physical C breakpoint, not a guessed coordinate. */\n     char\t\t*rn_name;')
    return once(text,'\t  (node)->rn_name = NULL;\\\n','\t  (node)->rn_name = NULL;\\\n\t  (node)->rn_c_reference = NULL;\\\n')


def transform_basic(text):
    for target in ['node','resptr']:
        needle='\t'+('    ' if target=='node' else '')+target+'->rn_name = pl->rp_nodename;'
        block='''
        if ((MODE) && pl->rp_nodename && ResCurrentNode &&
            !strcmp(pl->rp_nodename, ResCurrentNode))
            TARGET->rn_c_reference = pl->rp_nodename;'''.replace('MODE',MODE).replace('TARGET',target)
        text=once(text,needle,needle+block)
    return text


def transform_merge(text):
    text=once(text,'#include <stdio.h>','#include <stdio.h>\n#include <string.h>')
    needle='    /* Moves name to new node, if new node does not have a name */'
    block='''    /* The native merge proves these breakpoint nodes are identical.
     * Keep the original C-reference role even when a port name wins. */
    if (MODE)
    {
        if (node1->rn_c_reference && node2->rn_c_reference &&
            strcmp(node1->rn_c_reference, node2->rn_c_reference))
        {
            TxError("OPENPLL_RC_REFERENCE_ERROR incompatible reference points\\n");
            return;
        }
        if (!node1->rn_c_reference) node1->rn_c_reference = node2->rn_c_reference;
    }

'''.replace('MODE',MODE)
    return once(text,needle,block+needle)


def transform_print(text):
    start=text.index('ResPrintExtNode(');end=text.index('\n/*',start);part=text[start:end]
    part=once(part,'    resNode *rcLargest = NULL, *rcNode;','    resNode *rcLargest = NULL, *rcNode;\n    resNode *rcPhysicalReference = NULL;')
    needle='    /* If any of the subnode names match the original node name, then'
    block='''    if (rcPrecise)
        for (snode = nodelist; snode; snode = snode->rn_more)
            if (snode->rn_c_reference && !strcmp(snode->rn_c_reference, nodename))
            {
                if (rcPhysicalReference && rcPhysicalReference != snode)
                {
                    TxError("OPENPLL_RC_REFERENCE_ERROR duplicate physical reference net=%s\\n", nodename);
                    return;
                }
                rcPhysicalReference = snode;
                DoKillNode = FALSE;
            }

'''
    part=once(part,needle,block+needle)
    needle='    if (NeedFix)'
    block='''    /* This alias is proven by native breakpoint merging, not a
     * coordinate guess or a repair of a missing terminal. */
    if (rcPrecise && (ResOptionsFlags & ResOpt_DoExtFile) && rcPhysicalReference &&
        rcPhysicalReference->rn_name && strcmp(nodename, rcPhysicalReference->rn_name))
    {
        fprintf(outextfile, "equiv \\"%s\\" \\"%s\\"\\n", nodename, rcPhysicalReference->rn_name);
        TxPrintf("OPENPLL_RC_REFERENCE_ALIAS original=%s physical=%s\\n", nodename, rcPhysicalReference->rn_name);
    }

'''
    part=once(part,needle,block+needle)
    return text[:start]+part+text[end:]
