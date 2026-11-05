"""Extract minimum, nominal and maximum wire RC for an independently checked digital route."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from prototype_spef_v2 import parse
from extract_prototype_parent_spef_v2 import check_network,OPENROAD
from compiled_charge import execute
from resources import lease


def run(route,output):
    rr=route/'assessment.json';sr=route/'signoff/assessment.json'
    r,s=[json.loads(p.read_text()) for p in (rr,sr)]
    verify(r['input_sha256']);verify(r['artifacts']);verify(s['sha256'])
    if not r['digital_routing_completed'] or not s['diagnostic_physical_pass'] or not s['lvs_unique_match']:
        raise ValueError('independently checked digital source required')
    if s['sha256'].get(str(route/'route.odb'))!=sha(route/'route.odb'):
        raise ValueError('physical audit belongs to another database')
    baseline=route/'route.nom.spef'
    original=parse(baseline.read_text())
    normalize=lambda name: re.sub(r'\\(.)',r'\1',name)
    expected={normalize(n['name']):{(normalize(c['node']),c['kind']) for c in n['connections']} for n in original['nets']}
    inputs={str(p):sha(p) for p in (rr,sr,route/'route.odb',baseline,Path(OPENROAD),Path(__file__).resolve(),
        Path(__file__).with_name('prototype_spef_v2.py'),Path(__file__).with_name('extract_prototype_parent_spef_v2.py'),
        Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('compiled_charge.py'))}
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='4')
    artifacts={};results=[]
    for corner in ('min','nom','max'):
        model=ROOT/f'build/timing450/pdk/sky130A/libs.tech/librelane/rules.openrcx.sky130A.{corner}.magic'
        target=output/(corner+'.spef');script=output/(corner+'.tcl');log=output/(corner+'.log')
        script.write_text(f'read_db {{{route/"route.odb"}}}\nset_thread_count 4\ndefine_process_corner -ext_model_index 0 RCX_{corner.upper()}\nextract_parasitics -ext_model_file {{{model}}} -corner 0\nwrite_spef {{{target}}}\nexit\n')
        inputs.update({str(p):sha(p) for p in (model,script)});verify(inputs)
        save(output/'status.json',dict(state='extracting_'+corner,release_ready=False))
        with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',script],log,deadline,8)
        parsed=parse(target.read_text())
        found={normalize(n['name']):{(normalize(c['node']),c['kind']) for c in n['connections']} for n in parsed['nets']}
        if found!=expected or not parsed['pin_capacitance_excluded']:
            raise ValueError('wire-view net/terminal inventory or capacitance scope changed')
        networks=[check_network(net) for net in parsed['nets']]
        detail=output/(corner+'.json');save(detail,parsed)
        results.append(dict(corner=corner,networks=networks))
        artifacts.update({str(p):sha(p) for p in (target,detail,log)})
    verify(inputs);report=output/'networks.json';save(report,results);artifacts[str(report)]=sha(report)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts=artifacts,
        candidate_source_sha256=r['candidate_source_sha256'],wire_views=['min','nom','max'],
        signal_nets=len(expected),all_terminal_inventories_match_routed_nominal=True,
        all_wire_terminals_resistively_connected=True,cell_pin_capacitance_excluded=True,
        digital_timing_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='wire_views_extracted_timing_pending',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.route.resolve(),a.output.resolve())
