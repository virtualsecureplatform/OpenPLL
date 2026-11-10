"""Remove obsolete integer-rounding bias when reading floating native wire resistances."""
MODE='getenv("OPENPLL_RC_NATIVE_CAPS") != NULL && getenv("OPENPLL_RC_EXPLICIT_COUPLING") != NULL'
def transform_read(text):
    needle='(float)(0.5 + (double)rscale * atof(argv[3]))'
    if text.count(needle)!=1:raise ValueError('one native floating resistor reader required')
    return text.replace(needle,'(float)(('+MODE+' ? 0.0 : 0.5) + (double)rscale * atof(argv[3]))')
def transform_spice(text):
    needle='fprintf(esSpiceF, "R%d %s %s %g\\n", esResNum++, nodeSpiceName(hierName1, NULL),'
    if text.count(needle)!=1:raise ValueError('one native explicit-wire resistor serializer required')
    return text.replace(needle,'fprintf(esSpiceF, ('+MODE+') ? "R%d %s %s %.17g\\n" : "R%d %s %s %g\\n", esResNum++, nodeSpiceName(hierName1, NULL),')
