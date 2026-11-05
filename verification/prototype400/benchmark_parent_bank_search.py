#!/usr/bin/env python3
"""Measure the retained exhaustive KLayout search without applying CAD edits."""
import argparse
from pathlib import Path
import json
import textwrap
import time
from klayout_compat import pya
from common import ROOT,save,sha

p=argparse.ArgumentParser(description=__doc__)
for n in ('frame','localization','plan','output'):p.add_argument('--'+n,required=True,type=Path)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
frame=a.frame.resolve();loc=a.localization.resolve();plan=a.plan.resolve()
source=Path(__file__).with_name('protect_parent_antennas_v2.py')
text=source.read_text();begin=text.index('    occupied=bodies.dup();plan=[]');end=text.index('    additions=',begin)
code=textwrap.dedent(text[begin:end]);(out/'retained_search.py').write_text(code)
records=json.loads((loc/'records.json').read_text());by_net={}
for r in records:
    for port in r['macro_ports']:
        if port['net'] not in by_net or port['instance']=='oscillator':by_net[port['net']]=port
reg=lambda b:pya.Region(pya.Box(*b))
bodies=pya.Region()
for box in json.loads((frame/'assessment.json').read_text())['macro_bboxes_dbu'].values():bodies+=reg(box).sized(3000)
state=dict(pya=pya,reg=reg,bodies=bodies,by_net=by_net)
started=time.monotonic();exec(compile(code,str(out/'retained_search.py'),'exec'),state);elapsed=time.monotonic()-started
actual=json.loads((plan/'plan.json').read_text());expected=[{k:r[k] for k in actual[0]} for r in state['plan']]
assert actual==expected,'compiled and retained KLayout searches differ'
paths=[Path(__file__).resolve(),source,frame/'assessment.json',loc/'records.json',plan/'assessment.json',plan/'plan.json']
save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(out/'retained_search.py'):sha(out/'retained_search.py')},
     nets=len(actual),all_coordinates_and_ties_equal=True,retained_klayout_search_seconds=elapsed,
     scope='search only; compiled build, admission and receipt IO are separate costs',cad_geometry_validated=False,release_qualified=False))
print(json.dumps(dict(nets=len(actual),retained_klayout_search_seconds=elapsed,all_coordinates_and_ties_equal=True)))
