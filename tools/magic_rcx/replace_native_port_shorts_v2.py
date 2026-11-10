"""Replace only generated port-alias shorts proven connected by native wire R."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'
def transform_build(text):
    a=text.index('efBuildEquiv(def, nodeName1, nodeName2, resist, isspice)');b=text.index('\n/*',a)
    part=text[a:b];needle='efBuildDevice(def, sdev, "None", &GeoNullRect, 10, argv);'
    if part.count(needle)!=1:raise ValueError('one native equiv-generated alias device required')
    part=part.replace(needle,'efBuildDevice(def, sdev, (resist && sdev == DEV_RES && '+MODE+') ? "OPENPLL_RC_IDEAL_ALIAS" : "None", &GeoNullRect, 10, argv);')
    text=text[:a]+part+text[b:]
    needle='    bool hasModel = strcmp(type, "None") ? TRUE : FALSE;'
    if text.count(needle)!=1:raise ValueError('one native device model initializer required')
    text=text.replace(needle,'    bool rcGeneratedAlias = !strcmp(type, "OPENPLL_RC_IDEAL_ALIAS");\n    bool hasModel = !rcGeneratedAlias && strcmp(type, "None") ? TRUE : FALSE;')
    text=text.replace('    newdev = (Dev *)NULL;\n    devtmp.dev_subsnode', '    if (rcGeneratedAlias) type = "None";\n    newdev = (Dev *)NULL;\n    devtmp.dev_subsnode')
    text=text.replace('        newdev->dev_class = class;', '        newdev->dev_class = class;\n        newdev->dev_rc_alias = rcGeneratedAlias;')
    return text

def transform_types(text):
    needle='    U_char\t dev_class;'
    if text.count(needle)!=1:raise ValueError('one native device class declaration required')
    return text.replace(needle, '    bool dev_rc_alias; /* Generated ideal port alias, never a physical resistor. */\n'+needle)

def transform_visit(text):
    a=text.index('int\nefVisitDevs(hc, ca)');b=text.index('\n/*',a)
    part=text[a:b]
    helpers='''/* A graph of actual native resistor records, excluding generated port shorts. */
static HashEntry *
openpllRcRoot(HashEntry *entry)
{
    HashEntry *root = entry, *parent;
    while ((parent = (HashEntry *)HashGetValue(root)) != NULL && parent != root) root = parent;
    if (parent == NULL) HashSetValue(root, (ClientData)root);
    while (entry != root)
    {
        parent = (HashEntry *)HashGetValue(entry);
        HashSetValue(entry, (ClientData)root);
        entry = parent;
    }
    return root;
}

static void
openpllRcGraph(Def *def, HashTable *graph)
{
    Connection *wire;
    for (wire = def->def_resistors; wire; wire = wire->conn_next)
    {
        HashEntry *a, *b;
        EFNodeName *na, *nb;
        if (wire->conn_res < 0 || wire->conn_1.cn_nsubs || wire->conn_2.cn_nsubs) continue;
        a = HashLookOnly(&def->def_nodes, wire->conn_name1);
        b = HashLookOnly(&def->def_nodes, wire->conn_name2);
        if (!a || !b) continue;
        na = (EFNodeName *)HashGetValue(a); nb = (EFNodeName *)HashGetValue(b);
        if (!na || !nb) continue;
        a = openpllRcRoot(HashFind(graph, (char *)na->efnn_node));
        b = openpllRcRoot(HashFind(graph, (char *)nb->efnn_node));
        if (a != b) HashSetValue(a, (ClientData)b);
    }
}

static bool
openpllRcAliasReplaced(Dev *dev, HashTable *graph)
{
    HashEntry *a, *b;
    if (dev->dev_class != DEV_RES || dev->dev_res != 0 || dev->dev_nterm != 3 ||
        !dev->dev_rc_alias) return FALSE;
    a = HashLookOnly(graph, (char *)dev->dev_terms[1].dterm_node);
    b = HashLookOnly(graph, (char *)dev->dev_terms[2].dterm_node);
    return a && b && openpllRcRoot(a) == openpllRcRoot(b);
}

'''
    needle='    HashEntry *he;'
    if part.count(needle)!=1:raise ValueError('one native device visitor required')
    part=part.replace(needle,needle+'\n    HashTable rcGraph;\n    bool rcActive = '+MODE+';')
    needle='    /* Visit our own devices */'
    part=part.replace(needle,'    if (rcActive) {HashInit(&rcGraph, 128, HT_WORDKEYS); openpllRcGraph(def, &rcGraph);}\n\n'+needle)
    needle='\tdev = (Dev *)HashGetValue(he);'
    if part.count(needle)!=1:raise ValueError('one native device traversal body required')
    part=part.replace(needle,needle+'\n        if (rcActive && openpllRcAliasReplaced(dev, &rcGraph)) continue;')
    needle='\t    return 1;'
    if part.count(needle)!=1:raise ValueError('one native callback abort required')
    part=part.replace(needle,'\t{\n            if (rcActive) HashKill(&rcGraph);\n\t    return 1;\n\t}')
    part=part.replace('    return 0;\n}', '    if (rcActive) HashKill(&rcGraph);\n    return 0;\n}')
    return text[:a]+helpers+part+text[b:]
