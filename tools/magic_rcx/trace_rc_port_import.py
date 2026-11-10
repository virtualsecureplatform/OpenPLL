"""Trace native port metadata through rnode import without changing behavior."""


def transform(text):
    start=text.index('efBuildNode(def, isSubsnode, isDevSubsnode, isExtNode, nodeName, nodeCap,')
    end=text.index('\n/*',start);part=text[start:end]
    needle='    newname = (EFNodeName *)HashGetValue(he);'
    trace='''
    if (getenv("OPENPLL_RC_PORT_IMPORT_TRACE") != NULL)
    {
        EFNodeName *scan;
        int count = 0;
        if (newname && newname->efnn_node)
            for (scan = newname->efnn_node->efnode_name; scan; scan = scan->efnn_next) count++;
        TxPrintf("OPENPLL_RC_PORT_IMPORT stage=entry name=%s layer=%s ext=%d ac=%d port=%d flags=%d aliases=%d kills=%d\\n",
            nodeName, layerName ? layerName : "NULL", isExtNode, ac,
            newname ? newname->efnn_port : -2,
            (newname && newname->efnn_node) ? newname->efnn_node->efnode_flags : -1,
            count, def->def_kills != NULL);
    }
'''
    if part.count(needle)!=1:raise ValueError('one native name lookup required')
    part=part.replace(needle,needle+trace)
    needle='    newnode->efnode_flags = rcSplitFlags;'
    trace='''
    if (getenv("OPENPLL_RC_PORT_IMPORT_TRACE") != NULL)
        TxPrintf("OPENPLL_RC_PORT_IMPORT stage=allocated name=%s port=%d flags=%d reused=%d\\n",
            nodeName, newname->efnn_port, rcSplitFlags, rcSplitName != NULL);
'''
    if part.count(needle)!=1:raise ValueError('one native node flags initializer required')
    part=part.replace(needle,needle+trace)
    text=text[:start]+part+text[end:]
    start=text.index('efBuildPortNode(def, name, idx, x, y, layername, toplevel)')
    end=text.index('\n/*',start);part=text[start:end]
    needle='\tnn->efnn_port = idx;'
    if part.count(needle)!=1:raise ValueError('one native port record required')
    part=part.replace(needle,needle+'''
        if (getenv("OPENPLL_RC_PORT_IMPORT_TRACE") != NULL)
            TxPrintf("OPENPLL_RC_PORT_IMPORT stage=port name=%s port=%d flags=%d\\n",
                name, idx, nn->efnn_node->efnode_flags);
''')
    return text[:start]+part+text[end:]
