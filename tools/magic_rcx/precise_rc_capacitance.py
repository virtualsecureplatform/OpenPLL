"""Preserve native capacitance magnitude and conserved distributed totals."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'
def transform_ef_types(text):
    needle='typedef float EFCapValue;'
    if text.count(needle)!=1:raise ValueError('one native EF capacitance typedef required')
    return text.replace(needle,'typedef double EFCapValue;')
def transform_res_types(text):
    needle='    float\t\tcapacitance;'
    if text.count(needle)!=1:raise ValueError('one native original-node capacitance field required')
    return text.replace(needle,'    double\t\tcapacitance;')
def transform_spice(text):
    needle='esSIvalue(esSpiceF, 1.0E-15 * cap);'
    if text.count(needle)!=2:raise ValueError('exactly two native capacitor serializers required')
    return text.replace(needle,'if ('+MODE+')\n            fprintf(esSpiceF, "%.17g", 1.0E-15 * cap);\n        else '+needle)
def transform_print(text):
    a=text.index('ResPrintExtNode(');b=text.index('\n/*',a);part=text[a:b]
    needle='    resNode\t*snode;'
    if part.count(needle)!=1:raise ValueError('unique resistor-node writer declarations required')
    part=part.replace(needle,needle+'\n    bool rcPrecise = '+MODE+';\n    double rcWeight = 0, rcTarget = 0, rcOther = 0, rcCap;\n    resNode *rcLargest = NULL, *rcNode;')
    part=part.replace('"subcap \\"%s\\" %g\\n"','"subcap \\"%s\\" %.17g\\n"')
    needle='    /* Create "rnode" entries for each subnode */'
    setup='''    /* Normalize positive geometric weights to the original double C.
     * Assign the final floating-point residual to the largest weight.
     */
    if (rcPrecise)
    {
        for (rcNode = nodelist; rcNode; rcNode = rcNode->rn_more)
        {
            double weight = rcNode->rn_float.rn_area;
            if (!isfinite(weight) || weight < 0)
            {TxError("OPENPLL_RC_BAD_AREA net=%s\\n", nodename); return;}
            rcWeight += weight;
            if (!rcLargest || weight > rcLargest->rn_float.rn_area) rcLargest = rcNode;
        }
        rcTarget = node->capacitance / ExtCurStyle->exts_capScale;
        if (!isfinite(rcTarget) || rcTarget < 0 || (rcTarget > 0 && rcWeight <= 0))
        {TxError("OPENPLL_RC_BAD_CAP_BUDGET net=%s\\n", nodename); return;}
        if (rcWeight > 0)
            for (rcNode = nodelist; rcNode; rcNode = rcNode->rn_more)
                if (rcNode != rcLargest)
                    rcOther += (rcNode->rn_float.rn_area / rcWeight) * rcTarget;
    }

'''
    if part.count(needle)!=1:raise ValueError('unique native rnode loop required')
    part=part.replace(needle,setup+needle)
    needle='    \t    fprintf(outextfile, "rnode \\"%s\\" 0 %g %d %d %d\\n",'
    replacement='''            rcCap = snode->rn_float.rn_area / ExtCurStyle->exts_capScale;
            if (rcPrecise)
                rcCap = (snode == rcLargest) ? rcTarget - rcOther :
                    ((rcWeight > 0) ? (snode->rn_float.rn_area / rcWeight) * rcTarget : 0);
            fprintf(outextfile, rcPrecise ? "rnode \\"%s\\" 0 %.17g %d %d %d\\n" : "rnode \\"%s\\" 0 %g %d %d %d\\n",'''
    if part.count(needle)!=1:raise ValueError('unique native rnode numeric formatter required')
    part=part.replace(needle,replacement)
    needle='(snode->rn_float.rn_area / ExtCurStyle->exts_capScale),'
    if part.count(needle)!=1:raise ValueError('unique native rnode C value required')
    part=part.replace(needle,'rcCap,')
    return text[:a]+part+text[b:]
