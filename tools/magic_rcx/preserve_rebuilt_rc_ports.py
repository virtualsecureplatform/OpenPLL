"""Retain explicit port metadata when the native reader rebuilds a killed alias."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'


def transform(text):
    start=text.index('efBuildNode(def, isSubsnode, isDevSubsnode, isExtNode, nodeName, nodeCap,')
    end=text.index('\n/*',start);part=text[start:end]
    needle='    int rcSplitFlags = 0;'
    if part.count(needle)!=1:raise ValueError('one split-port context required')
    part=part.replace(needle,needle+'\n    int rcRebuiltPort = -1;')
    needle='\t\t\tEFHNFree(nodeAlias->efnn_hier, (HierName *)NULL, HN_ALLOC);'
    replacement='''            /* The regenerated physical rnode keeps its own declared
             * port number, not flags inherited from unrelated aliases. */
            if ((MODE) && !isExtNode && ac == 0 && layerName &&
                !strcmp(layerName, "0") && nodeAlias->efnn_port >= 0)
            {
                rcRebuiltPort = nodeAlias->efnn_port;
                rcSplitFlags = nodeAlias->efnn_node->efnode_flags &
                    (EF_PORT | EF_TOP_PORT);
                if (getenv("OPENPLL_RC_PORT_REBUILD_TRACE") != NULL)
                    TxPrintf("OPENPLL_RC_PORT_REBUILD name=%s port=%d flags=%d\\n",
                        nodeName, rcRebuiltPort, rcSplitFlags);
            }
'''.replace('MODE',MODE)+needle
    if part.count(needle)!=1:raise ValueError('one native killed-alias release required')
    part=part.replace(needle,replacement)
    needle='\tnewname->efnn_port = -1;\t/* No port assignment */'
    if part.count(needle)!=1:raise ValueError('one native rebuilt-name port initializer required')
    part=part.replace(needle,'\tnewname->efnn_port = rcRebuiltPort; /* -1 unless an explicit rnode port was rebuilt */')
    return text[:start]+part+text[end:]
