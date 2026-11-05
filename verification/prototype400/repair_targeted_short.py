#!/usr/bin/env python3
"""Release the one measured coarse/fine short while retaining 358 background routes."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from common import ROOT,save,sha,verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import TECH,LEF,OPENROAD
from check_bbpd_repair_identity import design,section
from build_assembly_frame import DCO


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    base=ROOT/'build/timing400/prototype_001';placed=base/'parent_targeted_001';source=base/'parent_closure_002/route'
    failed=base/'targeted_closure_002/layout/compare.json';rows=json.loads(failed.read_text())
    text=json.dumps(rows[-1]['badnets']);assert 'coarse_therm[11]' in text and 'fine_therm[11]' in text
    plan=json.loads((placed/'extra_placement_plan.json').read_text());targets={r['net'] for r in plan}|{'coarse_therm[11]'};assert len(targets)==11
    fixed=(placed/'fixed_background.def').read_text()
    name='coarse_therm[11]';pattern=r'(^\s*-\s+'+re.escape(name)+r'\s+.*?);'
    matches=list(re.finditer(pattern,fixed,re.M|re.S));assert len(matches)==1
    body=matches[0].group();assert '+ FIXED' in body
    fixed=fixed[:matches[0].start()]+body.replace('+ FIXED','+ ROUTED')+fixed[matches[0].end():]
    (out/'fixed_background.def').write_text(fixed)
    lefs=[TECH,LEF,base/'local_antenna_001/digital.lef',ROOT/f'openlane/{DCO}/runs/c1fine_range_001/final/lef/{DCO}.lef',ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/lef/IntegerPLL_BBPD.lef']
    recipe=(placed/'route.tcl').read_text().replace(str(placed/'fixed_background.def'),str(out/'fixed_background.def'))
    recipe=re.sub(r'^set targets .*$', 'set targets {'+' '.join('{'+n+'}' for n in sorted(targets))+'}',recipe,flags=re.M)
    recipe=recipe.replace('$fixed!=359','$fixed!=358').replace(str(placed)+'/route',str(out)+'/route').replace(str(placed)+'/powered.v',str(out)+'/powered.v')
    recipe=recipe.replace(str(placed)+'/vpwr_errors.rpt',str(out)+'/vpwr_errors.rpt').replace(str(placed)+'/vgnd_errors.rpt',str(out)+'/vgnd_errors.rpt')
    task=out/'route.tcl';task.write_text(recipe)
    files=[Path(__file__).resolve(),Path(OPENROAD),source/'assessment.json',source/'route.def',placed/'placed.def',placed/'fixed_background.def',placed/'extra_placement_plan.json',failed,*lefs,task,out/'fixed_background.def']
    pins={str(p):sha(p) for p in files}
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False))
    save(out/'input_manifest.json',dict(input_sha256=pins))
    with (out/'route.log').open('x') as log:
        child=subprocess.Popen([OPENROAD,'-no_init','-exit',str(task)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(out/'status.json',dict(state='targeted_short_rerouting',native_pid=child.pid,release_qualified=False))
        try:code=child.wait(timeout=43200)
        except BaseException:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            raise
    log=(out/'route.log').read_text();counts=re.findall(r'Number of violations = (\d+)',log)
    assert code==0 and counts and counts[-1]=='0' and (out/'route.drc').stat().st_size==0
    assert all(f'All shapes on net {n} are connected.' in log for n in ('VPWR','VGND'))
    oldcells,oldpins,oldnets=design(source/'route.def');cells,pins_actual,nets=design(out/'route.def');placedcells,placedpins,_=design(placed/'placed.def')
    assert cells==placedcells and pins_actual==placedpins and all(cells[n]==v for n,v in oldcells.items())
    assert all(pins_actual[k]==v for k,v in oldpins.items())
    def norm(body):return re.sub(r'\bFIXED\b','ROUTED',' '.join(body.split()))
    frozen=[n for n,body in oldnets.items() if n not in targets and re.search(r'\bROUTED\b',body)]
    assert len(frozen)==358 and all(norm(nets[n])==norm(oldnets[n]) for n in frozen)
    new_pins=re.sub(r'(-\s+(?:VPWR|VGND)\s+\+ NET (?:VPWR|VGND)) \+ SPECIAL',r'\1',section(out/'route.def','PINS'))
    assert new_pins==section(source/'route.def','PINS')
    assert norm(section(out/'route.def','SPECIALNETS'))==norm(section(source/'route.def','SPECIALNETS'))
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
         router_drc_violations=0,main_rail_database_connectivity_pass=True,exact_macro_bindings_preserved=True,
         all_protection_cell_bindings_verified=True,unchanged_background_signal_routes=358,target_nets=sorted(targets),
         full_assembled_drc_pass=False,assembled_lvs_pass=False,antenna_qualified=False,release_qualified=False))
    save(out/'status.json',dict(state='targeted_short_route_pass_pending_gds_checks',release_qualified=False))


if __name__=='__main__':
    try:main()
    except BaseException as e:
        if '--output' in sys.argv:
            out=Path(sys.argv[sys.argv.index('--output')+1])
            if out.exists():save(out/'status.json',dict(state='failed',reason=repr(e),release_qualified=False))
        raise
