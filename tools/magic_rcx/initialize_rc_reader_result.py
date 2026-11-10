"""Initialize every EXT record result before dispatch, including header/node records."""
def transform(text):
    needle='    while ((argc = efReadLine(&line, &size, fp, argv)) >= 0)\n    {'
    if text.count(needle)!=1:raise ValueError('one native EXT record dispatch loop required')
    text=text.replace(needle,needle+'\n        locresult = 0;')
    needle='\t\tcurnode = ResReadNode(argc, argv);'
    if text.count(needle)!=1:raise ValueError('one native original-node reader case required')
    return text.replace(needle,needle+'\n                locresult = (curnode == NULL);')
