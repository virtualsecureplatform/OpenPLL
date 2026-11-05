"""Review completed route rejected solely for a newly used, characterized size.

Preserve the original failed build. Publish byte-identical views in a separate
verification root only after checking the planned sizes, native libraries,
router DRC, power connectivity and the frozen build inputs.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify

def run(source,plan,views,output):
    status=source/'status.json';state=json.loads(status.read_text())
    if state.get('reason')!="ValueError('unsupported master introduced during repair')":raise ValueError('unexpected build failure')
    manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    pp=plan/'plan.json';p=json.loads(pp.read_text());verify(p['input_sha256'])
    if m['input_sha256'].get(str(pp))!=sha(pp):raise ValueError('different plan')
    parents=[Path(n) for n in m['input_sha256'] if n.endswith('/assessment.json') and Path(n).parent/'route.odb' in [Path(k) for k in m['input_sha256']]]
    if len(parents)!=1:raise ValueError('unique physical source required')
    parent=json.loads(parents[0].read_text());counts=Counter((source/'masters.txt').read_text().splitlines())
    new=set(counts)-set(parent['cell_inventory']);planned={t['replacement_master'] for t in p['targets']}
    if not new or not new<=planned:raise ValueError('unplanned masters')
    libraries=[views/f'{c}_{v}.lib' for c in ('tt','ff','ss','sf','fs') for v in ('early','late')]
    for lib in libraries:
        if m['input_sha256'].get(str(lib))!=sha(lib):raise ValueError('native library mismatch')
        masters=set(re.findall(r'cell \(([^)]+)\)',lib.read_text()))
        if not new<=masters:raise ValueError('new size lacks complete native characterization')
    log=source/'repair.log';text=log.read_text();drc=source/'route.drc'
    if 'POST_ROUTE_TIMING_REPAIR_COMPLETE' not in text or drc.stat().st_size or re.findall(r'Number of violations = (\d+)',text)[-1]!='0':raise ValueError('router incomplete/nonpass')
    if not all(f'All shapes on net {n} are connected.' in text for n in ('VDD','VSS')):raise ValueError('power-grid failure')
    names=['route.odb','route.def','route.v','powered.v','digital.lef','route.nom.spef','route.drc','masters.txt']
    inputs={**m['input_sha256'],**{str(x):sha(x) for x in (status,manifest,log,*[source/n for n in names],Path(__file__).resolve())}}
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    for name in names:(output/name).symlink_to(source/name)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(output/n):sha(output/n) for n in names},candidate_source_sha256=parent['candidate_source_sha256'],cell_inventory=dict(counts),digital_routing_completed=True,nominal_rc_extracted=True,router_drc_violations=0,database_power_grid_connected=True,characterized_sizes_missing_from_predecessor_inventory=sorted(new),original_rejected_build_preserved=True,byte_identical_completed_native_views=True,independent_equivalence_and_layout_checks_pending=True,physical_timing_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','plan','views','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.plan.resolve(),a.views.resolve(),a.output.resolve())
