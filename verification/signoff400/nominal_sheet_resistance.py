"""Read documented nominal Magic sheet values without choosing PVT scaling."""
from fractions import Fraction as F
import re
SELECTORS={'poly':'(allpolynonres)/active','locali':'(allli)/locali',**{'metal'+str(i):'(allm'+str(i)+')/metal'+str(i) for i in range(1,6)}}
def parse(text):
    if 'Resistances are in milliohms per square' not in text:raise ValueError('explicit resistance unit declaration required')
    extraction=False;ngspice=False;variants=set();found={};inverse={v:k for k,v in SELECTORS.items()}
    for raw in text.splitlines():
        line=raw.split('#',1)[0].strip()
        if line=='extract':extraction=True;continue
        if not extraction:continue
        if line=='end':extraction=False;continue
        if line.startswith('style '):ngspice=line.split()[1]=='ngspice';continue
        if line.startswith('variants '):variants=set(re.findall(r'\((.*?)\)',line));continue
        words=line.split()
        if not ngspice or variants!={'','orig','si'} or not words or words[0]!='resist' or words[1] not in inverse:continue
        if len(words)!=3:raise ValueError('unmodeled nominal sheet adjustment')
        material=inverse[words[1]]
        if material in found:raise ValueError('ambiguous nominal sheet declaration')
        found[material]=F(words[2])
        if found[material]<=0:raise ValueError('positive sheet resistance required')
    if set(found)!=set(SELECTORS):raise ValueError('complete nominal non-device sheet table required')
    return found
