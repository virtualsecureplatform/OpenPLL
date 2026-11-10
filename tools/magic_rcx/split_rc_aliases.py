"""Opt-in separation of explicitly reconstructed rnode aliases, preserving port names."""
def transform(text):
    start=text.index('efBuildNode(def, isSubsnode, isDevSubsnode, isExtNode, nodeName, nodeCap,')
    end=text.index('\n/*',start)
    part=text[start:end]
    marker='    int tnew = 0;'
    if part.count(marker)!=1 or 'OPENPLL_RC_NATIVE_CAPS' in part:raise ValueError('unmodified native node builder required')
    part=part.replace(marker,marker+'\n    EFNodeName *rcSplitName = NULL;\n    int rcSplitFlags = 0;')
    marker='    if (newname && (def->def_kills != NULL))'
    block='''    /* Explicit resistor nodes represent distinct physical points even
     * when the original ideal conductor named them as aliases.
     * Reuse the name record to preserve its port number and references.
     */
    if (getenv("OPENPLL_RC_NATIVE_CAPS") != NULL &&
        getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL &&
        !isExtNode && ac == 0 && layerName && !strcmp(layerName, "0") &&
        newname && newname->efnn_node &&
        !(newname->efnn_node->efnode_flags & EF_KILLED) &&
        newname->efnn_node->efnode_name &&
        newname->efnn_node->efnode_name->efnn_next)
    {
        EFNodeName **link = &newname->efnn_node->efnode_name;
        while (*link && *link != newname) link = &(*link)->efnn_next;
        if (*link == newname)
        {
            rcSplitFlags = newname->efnn_node->efnode_flags & (EF_PORT | EF_TOP_PORT);
            *link = newname->efnn_next;
            newname->efnn_next = NULL;
            rcSplitName = newname;
            newname = NULL;
        }
    }

'''
    if part.count(marker)!=1:raise ValueError('unique existing killed-node guard required')
    part=part.replace(marker,block+marker)
    marker='    if (!newname)\n    {\n\t/* Allocate a new node'
    if part.count(marker)!=1:raise ValueError('unique native name allocator required')
    part=part.replace(marker,'    if (rcSplitName) newname = rcSplitName;\n\n'+marker)
    part=part.replace('    newnode->efnode_flags = 0;','    newnode->efnode_flags = rcSplitFlags;')
    return text[:start]+part+text[end:]
