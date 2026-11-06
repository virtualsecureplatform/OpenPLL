"""Prepare the actual layout-bound candidate identity; never promote diagnostics to gates."""
import argparse,json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins,BINDING
from audit_prototype_v3 import CHECKS,PROFILE


def run(output):
    if output.exists():raise FileExistsError(output)
    pins=source_pins();binding=json.loads(BINDING.read_text());profile=json.loads(PROFILE.read_text())
    physical=ROOT/binding['physical_gds']['path'];sources={p:d for p,d in pins.items() if p.endswith('.v')}
    if len(sources)!=9 or set(profile['gates'])!=set(CHECKS):raise ValueError('complete selected RTL and current five-gate profile required')
    candidate=dict(name='selected_filled_layout_019',source_sha256=sources,physical_sha256={str(physical):sha(physical)},RTL_binding_sha256=sha(BINDING))
    files=[Path(__file__).resolve(),Path(__file__).with_name('selected_physical_rtl.py'),PROFILE,Path(__file__).with_name('audit_prototype_v3.py')];pins.update({str(p):sha(p) for p in files});verify(pins)
    save(output,dict(schema_version=3,status='qualification_pending',profile_sha256=sha(PROFILE),candidate=candidate,input_sha256=pins,evidence={gate:[] for gate in profile['gates']},required_checks={gate:sorted(CHECKS[gate]) for gate in profile['gates']},scope='candidate identity and unfilled qualification slots; diagnostic receipts are deliberately not gate evidence',release_ready=False))
    print('prepared candidate identity:',len(sources),'RTL files; all five qualification gates unfilled')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
