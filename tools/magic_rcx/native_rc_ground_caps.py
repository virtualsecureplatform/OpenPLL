"""Opt-in native ground-C import and removal of the original lump before redistribution."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'
def transform_read(text):
    marker='    node->location.p_x = atoi(argv[NODES_NODEX]);'
    if text.count(marker)!=1 or 'OPENPLL_RC_NATIVE_CAPS' in text:raise ValueError('one unmodified native node reader required')
    return text.replace(marker,'    if ('+MODE+')\n        node->capacitance += MagAtof(argv[3]);\n'+marker)
def transform_print(text):
    marker='    /* Create "rnode" entries for each subnode */'
    if text.count(marker)!=1 or 'OPENPLL_RC_NATIVE_CAPS' in text:raise ValueError('one unmodified native resistor-node printer required')
    block='''    /* Replace, rather than duplicate, the original substrate-C lump. */
    if ((ResOptionsFlags & ResOpt_DoExtFile) && MODE)
        fprintf(outextfile, "subcap \\"%s\\" %g\\n", nodename, -node->capacitance);

'''.replace('MODE',MODE)
    # Emit ordinary C string quoting, not Python string delimiters.
    return text.replace(marker,block+marker)
