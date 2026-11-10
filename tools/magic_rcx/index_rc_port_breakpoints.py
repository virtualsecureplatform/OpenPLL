"""Index the fixed original port population once per native EXT read."""
MODE = 'getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'


def transform_main(text):
    marker = 'void\nResMakePortBreakpoints(def)\n    CellDef *def;'
    setup = '''static ResExtNode **openpllRcPorts = NULL;
static int openpllRcPortCount = 0;

void
OpenpllRCIndexPorts(void)
{
    HashSearch search;
    HashEntry *entry;
    ResExtNode *node;
    int count = 0;
    if (openpllRcPorts) freeMagic(openpllRcPorts);
    openpllRcPorts = NULL;
    HashStartSearch(&search);
    while ((entry = HashNext(&ResNodeTable, &search)))
    {
        node = (ResExtNode *)HashGetValue(entry);
        if (node->status & PORTNODE) count++;
    }
    openpllRcPortCount = count;
    if (count) openpllRcPorts = (ResExtNode **)mallocMagic(count * sizeof(ResExtNode *));
    count = 0;
    HashStartSearch(&search);
    while ((entry = HashNext(&ResNodeTable, &search)))
    {
        node = (ResExtNode *)HashGetValue(entry);
        if (node->status & PORTNODE) openpllRcPorts[count++] = node;
    }
    TxPrintf("OPENPLL_RC_PORT_INDEX ports=%d\\n", count);
}

'''
    if text.count(marker) != 1:
        raise ValueError('one native port breakpoint function required')
    text = text.replace(marker, setup + 'void\nResMakePortBreakpoints(def, rcExtra)\n    CellDef *def;\n    ResExtNode *rcExtra;')
    start = text.index('void\nResMakePortBreakpoints(def, rcExtra)')
    end = text.index('\n/*', start)
    part = text[start:end]
    needle = '    ResExtNode  *node;'
    if part.count(needle) != 1:
        raise ValueError('one native port-loop node declaration required')
    part = part.replace(needle, needle + '\n    int rcCursor = 0;\n    bool rcIndexed = ' + MODE + ';')
    needle = '''    HashStartSearch(&hs);
    while((entry = HashNext(&ResNodeTable, &hs)) != NULL)
    {
\tnode = (ResExtNode *)HashGetValue(entry);'''
    replacement = '''    if (!rcIndexed) HashStartSearch(&hs);
    while (TRUE)
    {
        if (rcIndexed)
        {
            if (rcCursor < openpllRcPortCount)
                node = openpllRcPorts[rcCursor++];
            else if (rcCursor++ == openpllRcPortCount && rcExtra)
            {
                int k;
                bool alreadyIndexed = FALSE;
                for (k = 0; k < openpllRcPortCount; k++)
                    if (openpllRcPorts[k] == rcExtra) {alreadyIndexed = TRUE; break;}
                if (alreadyIndexed) break;
                node = rcExtra;
            }
            else break;
        }
        else
        {
            entry = HashNext(&ResNodeTable, &hs);
            if (!entry) break;
            node = (ResExtNode *)HashGetValue(entry);
        }'''
    if part.count(needle) != 1:
        raise ValueError('one native full port scan required')
    text = text[:start] + part.replace(needle, replacement) + text[end:]
    needle = 'ResMakePortBreakpoints(ResUse->cu_def);'
    if text.count(needle) != 1:
        raise ValueError('one native port call with current reference node required')
    return text.replace(needle, 'ResMakePortBreakpoints(ResUse->cu_def, node);')


def transform_read(text):
    marker = 'int\nResReadExt(CellDef *def)'
    if text.count(marker) != 1 or text.count('    return(result);') != 1:
        raise ValueError('one native EXT reader and completion required')
    text = text.replace(marker, 'extern void OpenpllRCIndexPorts(void);\n\n' + marker)
    return text.replace('    return(result);', '    if (' + MODE + ') OpenpllRCIndexPorts();\n    return(result);')
