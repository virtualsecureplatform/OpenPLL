"""Optional model/coordinate comments bind native SPICE instances to physical EXT devices."""
def transform(text):
    needle='    fprintf(esSpiceF, "%c", devchar);'
    if text.count(needle)!=1 or 'OPENPLL_ORIGIN' in text:raise ValueError('one uninstrumented native device prefix required')
    trace='''    if (getenv("OPENPLL_RC_DEVICE_ORIGINS") != NULL && devchar == 'X' && !gate->dterm_attrs)
        fprintf(esSpiceF, "* OPENPLL_ORIGIN X%d %s %d %d %d %d\\n",
            esSbckNum, EFDevTypes[dev->dev_type], dev->dev_rect.r_xbot,
            dev->dev_rect.r_ybot, dev->dev_rect.r_xtop, dev->dev_rect.r_ytop);
'''
    return text.replace(needle,trace+needle)
