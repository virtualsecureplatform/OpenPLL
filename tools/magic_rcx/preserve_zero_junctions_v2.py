"""Preserve known-zero substrate-terminal junctions and their physical body identity."""
MODE='getenv("OPENPLL_RC_ZERO_JUNCTION") != NULL && getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'
def transform_extract(text):
    needle='    if ((whichTerm != LL_GATEATTR) && (area != 0) && (perim != 0))'
    if text.count(needle)!=1:raise ValueError('one native terminal A/P output guard required')
    return text.replace(needle,'    if ((whichTerm != LL_GATEATTR) && (((area != 0) && (perim != 0)) ||\n        (('+MODE+') && len == 0 && area == 0 && perim == 0)))')
def transform_types(text):
    needle='     char               *rs_sattr;'
    if text.count(needle)!=1:raise ValueError('one native source attribute field required')
    return text.replace(needle,'     int rs_source_edge;\n     bool rs_virtual_source;\n'+needle)
def transform_res_read(text):
    needle='    device->status = FALSE;'
    if text.count(needle)!=2:raise ValueError('both native device constructors required')
    text=text.replace(needle,needle+'\n    device->rs_source_edge = -1;\n    device->rs_virtual_source = FALSE;')
    needle='\tdevice->rs_sattr = StrDup((char **)NULL, argv[i + 2]);'
    if text.count(needle)!=1:raise ValueError('one native device source attribute import required')
    text=text.replace(needle,needle+'\n        device->rs_source_edge = atoi(argv[i + 1]);')
    needle='    device->rs_sattr = StrDup((char **)NULL, argv[FET_SOURCE_ATTR]);'
    if text.count(needle)!=1:raise ValueError('one legacy FET source import required')
    text=text.replace(needle,needle+'\n    device->rs_source_edge = atoi(argv[FET_SOURCE + 1]);')
    needle='            device->subs = openpllRcCanonical(device->subs);'
    block='''
            if (MODE && device->source && device->source == device->subs &&
                device->rs_source_edge == 0 && device->rs_sattr &&
                (!strcmp(device->rs_sattr, "0") || !strcmp(device->rs_sattr, "0,0")))
            {
                device->rs_virtual_source = TRUE;
                if (!strcmp(device->rs_sattr, "0"))
                {
                    freeMagic(device->rs_sattr);
                    device->rs_sattr = StrDup((char **)NULL, "0,0");
                }
            }
'''.replace('MODE',MODE)
    if text.count(needle)!=1:raise ValueError('post-alias canonical terminal normalization required')
    return text.replace(needle,needle+block)
def transform_print(text):
    a=text.index('ResPrintExtDev(');b=text.index('\n/*',a);part=text[a:b]
    needle='devices->source->name,'
    if part.count(needle)!=1:raise ValueError('one native source terminal output required')
    part=part.replace(needle,'(devices->rs_virtual_source && devices->subs) ? devices->subs->name : devices->source->name,')
    # Only the source width changes; the gate/drain retain native geometry.
    needle='devices->source->name,\n'
    # Find the existing width expression directly after the substituted source.
    a2=part.index('(devices->rs_virtual_source && devices->subs)')
    b2=part.index('devices->rs_sattr',a2)
    source=part[a2:b2]
    needle='devices->layout->rd_width'
    if source.count(needle)!=1:raise ValueError('one native reconstructed source edge length required')
    source=source.replace(needle,'devices->rs_virtual_source ? 0 : devices->layout->rd_width')
    part=part[:a2]+source+part[b2:]
    return text[:a]+part+text[b:]
def transform_ef_read(text):
    marker='static bool efReadDef(Def *def, bool dosubckt, bool resist, bool noscale, bool toplevel, bool isspice);'
    if text.count(marker)!=1:raise ValueError('one native flattened reader declaration required')
    helper='''
/* Old EXT "0" means no attributes.  For zero-edge MOS terminals on bulk,
 * the extractor explicitly computed zero junction area/perimeter instead.
 */
static void
openpllZeroBodyJunctions(Def *def)
{
    HashSearch search;
    HashEntry *entry;
    Dev *device;
    int n;
    if (!(MODE)) return;
    HashStartSearch(&search);
    while ((entry = HashNext(&def->def_devs, &search)))
    {
        device = (Dev *)HashGetValue(entry);
        if (!device || !device->dev_subsnode || device->dev_nterm < 3 ||
            (device->dev_class != DEV_MSUBCKT && device->dev_class != DEV_MOSFET &&
             device->dev_class != DEV_FET && device->dev_class != DEV_ASYMMETRIC) ||
            !strstr(EFDevTypes[device->dev_type], "fet_")) continue;
        for (n = 1; n < device->dev_nterm; n++)
            if (device->dev_terms[n].dterm_length == 0 &&
                device->dev_terms[n].dterm_node == device->dev_subsnode &&
                device->dev_terms[n].dterm_attrs == NULL)
                device->dev_terms[n].dterm_attrs = StrDup((char **)NULL, "0,0");
    }
}
'''.replace('MODE',MODE)
    text=text.replace(marker,marker+'\n'+helper)
    needle='    fclose(inf);\n    inf = (FILE *)NULL;'
    if text.count(needle)!=1:raise ValueError('one native EXT read completion required')
    return text.replace(needle,'    openpllZeroBodyJunctions(def);\n'+needle)
