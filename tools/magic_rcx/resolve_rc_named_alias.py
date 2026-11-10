"""Resolve an explicit rnode to its own name record after native equiv merging."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'


def transform(text):
    start=text.index('efBuildNode(def, isSubsnode, isDevSubsnode, isExtNode, nodeName, nodeCap,')
    end=text.index('\n/*',start);part=text[start:end]
    needle='    newname = (EFNodeName *)HashGetValue(he);'
    block='''
    /* efBuildEquiv can redirect multiple hash keys to the canonical
     * EFNodeName.  An explicit physical rnode must instead reuse the
     * matching original name record, including its own port number.
     */
    if ((MODE) && !isExtNode && ac == 0 && layerName &&
        !strcmp(layerName, "0") && newname && newname->efnn_node)
    {
        EFNode *owner = newname->efnn_node;
        EFNodeName *actual;
        for (actual = owner->efnode_name; actual; actual = actual->efnn_next)
            if (!strcmp(EFHNToStr(actual->efnn_hier), nodeName))
            {
                if (actual != newname)
                {
                    newname = actual;
                    newname->efnn_node = owner;
                    HashSetValue(he, (char *)newname);
                }
                break;
            }
    }
'''.replace('MODE',MODE)
    if part.count(needle)!=1:raise ValueError('one native rnode name lookup required')
    return text[:start]+part.replace(needle,needle+block)+text[end:]
