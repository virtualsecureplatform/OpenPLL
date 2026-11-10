"""Keep formal-port flags on actual port names when splitting native aliases."""


def transform(text):
    needle = 'rcSplitFlags = newname->efnn_node->efnode_flags & (EF_PORT | EF_TOP_PORT);'
    replacement = '''rcSplitFlags = (newname->efnn_port >= 0) ?
                newname->efnn_node->efnode_flags & (EF_PORT | EF_TOP_PORT) : 0;'''
    if text.count(needle) != 1:
        raise ValueError('one native RC alias port flag transfer required')
    text = text.replace(needle, replacement)
    needle = '''            *link = newname->efnn_next;
            newname->efnn_next = NULL;'''
    replacement = '''            *link = newname->efnn_next;
            {
                EFNodeName *remaining;
                bool hasPort = FALSE;
                for (remaining = newname->efnn_node->efnode_name;
                        remaining; remaining = remaining->efnn_next)
                    if (remaining->efnn_port >= 0) {hasPort = TRUE; break;}
                if (!hasPort)
                    newname->efnn_node->efnode_flags &= ~(EF_PORT | EF_TOP_PORT);
            }
            newname->efnn_next = NULL;'''
    if text.count(needle) != 1:
        raise ValueError('one native RC alias detachment required')
    return text.replace(needle, replacement)
