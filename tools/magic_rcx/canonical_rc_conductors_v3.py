"""Resolve EXT equiv records before extracting each physical conductor once."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'
def transform_read(text):
    marker='int\nResReadExt(CellDef *def)'
    helper='''void ResNodeAddDevice(ResExtNode *, RDev *, int);

static ResExtNode *
openpllRcCanonical(ResExtNode *node)
{
    while (node && (node->status & FORWARD)) node = node->forward;
    return node;
}

static void
openpllRcEquiv(char *first, char *second)
{
    ResExtNode *keep = ResExtInitNode(HashFind(&ResNodeTable, first));
    ResExtNode *alias = ResExtInitNode(HashFind(&ResNodeTable, second));
    devPtr *tail;
    if (keep == alias) return;
    if (alias->firstDev)
    {
        for (tail = alias->firstDev; tail->nextDev; tail = tail->nextDev);
        tail->nextDev = keep->firstDev; keep->firstDev = alias->firstDev;
        alias->firstDev = NULL;
    }
    keep->capacitance += alias->capacitance;
    keep->cap_couple += alias->cap_couple;
    alias->capacitance = alias->cap_couple = 0;
    /* Each alias retains its own port geometry for ResMakePortBreakpoints. */
    if (!(keep->status & DRIVELOC) && (alias->status & DRIVELOC))
    {
        keep->drivepoint = alias->drivepoint;
        keep->rs_ttype = alias->rs_ttype;
        keep->status |= DRIVELOC;
    }
    keep->status |= alias->status & FORCE;
    alias->forward = keep;
    alias->status |= FORWARD;
}

'''
    if text.count(marker)!=1:raise ValueError('unique native EXT reader required')
    text=text.replace(marker,helper+marker)
    needle='\t    case MERGE:'
    if text.count(needle)!=1:raise ValueError('unique native reader merge case required')
    text=text.replace(needle,'\t    case EQUIV:\n                if ('+MODE+') openpllRcEquiv(argv[1], argv[2]);\n                break;\n'+needle)
    needle='    fclose(fp);\n    return(result);'
    normalize='''    if (MODE)
    {
        RDev *device;
        ResExtNode *net;
        devPtr *entry, *next;
        /* Device records may precede or follow equiv records.  Rebuild
         * adjacency after all terminal pointers have canonical owners.
         */
        for (net = ResOriginalNodes; net; net = net->nextnode)
        {
            for (entry = net->firstDev; entry; entry = next)
            {next = entry->nextDev; freeMagic(entry);}
            net->firstDev = NULL;
        }
        for (device = ResRDevList; device; device = device->nextDev)
        {
            device->gate = openpllRcCanonical(device->gate);
            device->source = openpllRcCanonical(device->source);
            device->drain = openpllRcCanonical(device->drain);
            device->subs = openpllRcCanonical(device->subs);
            if (device->gate) ResNodeAddDevice(device->gate, device, GATE);
            if (device->source) ResNodeAddDevice(device->source, device, SOURCE);
            if (device->drain) ResNodeAddDevice(device->drain, device, DRAIN);
            if (device->subs) ResNodeAddDevice(device->subs, device, SUBS);
        }
    }
'''.replace('MODE',MODE)
    if text.count(needle)!=1:raise ValueError('unique native EXT reader completion required')
    return text.replace(needle,'    fclose(fp);\n'+normalize+'    return(result);')

def transform_rex(text):
    marker='int\nResProcessNode('
    helper='''/* Preserve explicit include/ignore selection through conductor aliases. */
static bool
openpllRcScopeContains(HashTable *scope, ResExtNode *node)
{
    HashSearch search;
    HashEntry *entry, *netentry;
    ResExtNode *selected;
    if (!(MODE)) return FALSE;
    HashStartSearch(&search);
    while ((entry = HashNext(scope, &search)))
    {
        netentry = HashLookOnly(&ResNodeTable, entry->h_key.h_name);
        if (!netentry) continue;
        selected = (ResExtNode *)HashGetValue(netentry);
        while (selected && (selected->status & FORWARD)) selected = selected->forward;
        if (selected == node) return TRUE;
    }
    return FALSE;
}

'''.replace('MODE',MODE)
    if text.count(marker)!=1:raise ValueError('unique native resistance network processor required')
    text=text.replace(marker,helper+marker)
    for before,after in [('if (he == NULL) return 0;','if (he == NULL && !openpllRcScopeContains(&ResIncludeTable, node)) return 0;'),('if (he != NULL) return 0;','if (he != NULL || openpllRcScopeContains(&ResIgnoreTable, node)) return 0;')]:
        a=text.index(marker);b=text.index('\n/*',a);part=text[a:b]
        if part.count(before)!=1:raise ValueError('one native selection guard required')
        text=text[:a]+part.replace(before,after)+text[b:]
    return text
