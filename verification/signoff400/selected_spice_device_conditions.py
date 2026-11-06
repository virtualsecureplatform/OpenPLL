"""Read explicit PDK corner and device temperature from a pinned native deck."""
import re
from pathlib import Path
from common_v3 import sha


def read(deck):
    text=Path(deck).read_text()
    corners=re.findall(r'^\s*\.lib\s+.+\s+(tt|ff|ss|sf|fs)\s*$',text,re.MULTILINE|re.IGNORECASE)
    temperatures=re.findall(r'^\s*\.options\s+device\s+temp\s*=\s*([-+0-9.eE]+)\s*$',text,re.MULTILINE|re.IGNORECASE)
    if len(corners)!=1 or len(temperatures)!=1:raise ValueError('one explicit PDK corner and device temperature required')
    temperature=float(temperatures[0])
    if temperature!=27:raise ValueError('prototype native comparison requires 27 C')
    return dict(corner=corners[0].lower(),temperature_c=temperature)


def matching(candidate,reference):
    a,b=read(candidate),read(reference)
    if a!=b:raise ValueError('native candidate and full reference device conditions differ')
    return a


def reference_deck(provenance):
    paths=[Path(p) for p in provenance['native_input_sha256'] if p.endswith('/profile.spice')]
    if len(paths)!=1 or sha(paths[0])!=provenance['native_input_sha256'][str(paths[0])]:raise ValueError('unique unchanged full-native profile deck required')
    return paths[0]
