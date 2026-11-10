"""Keep global substrate C attached to its original named extraction reference."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'


def once(text,needle,replacement):
    if text.count(needle)!=1:raise ValueError('one native substrate-reference site required: '+repr(needle))
    return text.replace(needle,replacement)


def transform_types(text):
    return once(text,'    unsigned short\t efnn_refc;','    bool                 efnn_rc_substrate_ref; /* Explicit original substrate record. */\n    unsigned short\t efnn_refc;')


def transform_build(text):
    text=once(text,'\tnewname->efnn_port = -1;\t/* No port assignment */','\tnewname->efnn_port = -1;\t/* No port assignment */\n        newname->efnn_rc_substrate_ref = FALSE;')
    text=once(text,'    newnn->efnn_port = -1;','    newnn->efnn_port = -1;\n    newnn->efnn_rc_substrate_ref = FALSE;')
    needle='\t\tnewnode->efnode_flags |= EF_GLOB_SUBS_NODE;'
    text=once(text,needle,needle+'\n            newname->efnn_rc_substrate_ref = TRUE;')
    needle='    if (isSubsnode == TRUE) newnode->efnode_flags |= EF_GLOB_SUBS_NODE;'
    text=once(text,needle,'''    if (isSubsnode == TRUE)
    {
        newnode->efnode_flags |= EF_GLOB_SUBS_NODE;
        newname->efnn_rc_substrate_ref = TRUE;
    }''')
    needle='''            *link = newname->efnn_next;'''
    extra='''            if (newname->efnn_rc_substrate_ref)
            {
                rcSplitFlags |= newname->efnn_node->efnode_flags &
                    (EF_GLOB_SUBS_NODE | EF_SUBS_NODE | EF_SUBS_PORT);
                newname->efnn_node->efnode_flags &= ~EF_GLOB_SUBS_NODE;
            }
'''
    text=once(text,needle,extra+needle)
    return text


def transform_flat(text):
    text=once(text,'\t    newname->efnn_port = -1;','\t    newname->efnn_port = -1;\n            newname->efnn_rc_substrate_ref = nn->efnn_rc_substrate_ref;')
    return once(text,'\t    nameGlob->efnn_port = -1;','\tnameGlob->efnn_port = -1;\n        nameGlob->efnn_rc_substrate_ref = FALSE;')
