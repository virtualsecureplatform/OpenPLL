"""Review selected-route CDC physical binding and enabled decision timing only.

No all-crossing waiver, full-mode timing qualification or release gate is issued.
"""
import argparse,json,math,re
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_physical_rtl import source_pins


def decision_paths(text,launch,capture):
    if text.count('CONDITIONAL_DECISION_PATHS_BEGIN')!=1 or text.count('CONDITIONAL_DECISION_PATHS_END')!=1:raise ValueError('one explicit decision query required')
    text=text.split('CONDITIONAL_DECISION_PATHS_BEGIN')[1].split('CONDITIONAL_DECISION_PATHS_END')[0]
    rows=[]
    for block in text.split('Startpoint: ')[1:]:
        start=block.splitlines()[0];target=re.search(r'^Endpoint: (\S+)',block,re.M);kind=re.search(r'Path Type: (\S+)',block);slack=re.search(r'([-+0-9.eE]+)\s+slack \((MET|VIOLATED)\)',block)
        if not all((target,kind,slack)):raise ValueError('complete explicit decision path fields required')
        value=float(slack[1])
        if start not in launch or target[1]not in capture or kind[1]not in('min','max')or not math.isfinite(value)or value<0 or slack[2]!='MET':raise ValueError('decision path mismatch or violation')
        rows.append(dict(startpoint=start,endpoint=target[1],path_type=kind[1],slack_ns=value))
    if len(rows)!=4 or {(r['endpoint'],r['path_type'])for r in rows}!={(n,k)for n in capture for k in('min','max')}:raise ValueError('both capture bits require min/max coverage')
    return rows


def run(stages,trace,physical,screens,output):
    if output.exists():raise FileExistsError(output)
    pins=source_pins();receipts=[]
    for directory in(stages,trace,physical):
        p=directory/'assessment.json';a=json.loads(p.read_text());verify(a['input_sha256']);verify(a['artifacts']);pins[str(p)]=sha(p);receipts.append(a)
    s,t,b=receipts
    if not s['all_synchronizer_stages_bound_to_routed_database']or not t['all_routed_synchronizer_interstage_paths_traced']or not b['all_interstage_cells_pins_and_nets_physically_bound']or not b['all_interstage_nets_continuous_with_unique_expected_drivers']:raise ValueError('complete physical path binding required')
    if t['chains']!=13 or b['synchronizers']!=13 or b['physical_cells']!=26+b['intermediate_cells']or b['intermediate_cells']!=t['intermediate_cells']:raise ValueError('selected complete stage/path inventory required')
    if t['input_sha256'].get(str(stages/'assessment.json'))!=sha(stages/'assessment.json')or b['input_sha256'].get(str(trace/'assessment.json'))!=sha(trace/'assessment.json'):raise ValueError('stage/trace/physical lineage mismatch')
    proof=ROOT/'build/signoff400/prototype_v3_integrated_decision_phase_proof_001/assessment.json';pr=json.loads(proof.read_text());pins[str(proof)]=sha(proof)
    selected={Path(p).name:h for p,h in pins.items()if p.endswith('.v')}
    original={Path(p).name:h for p,h in pr['input_sha256'].items()if p.endswith('.v')}
    if original!=selected:raise ValueError('phase proof differs from exact selected RTL')
    seen=set();rows=[]
    for screen in screens:
        p=screen/'assessment.json';a=json.loads(p.read_text());verify(a['input_sha256']);verify(a['artifacts']);pins[str(p)]=sha(p)
        corner=a['native_model_corner']
        if corner not in('tt','ff','ss','sf','fs')or corner in seen:raise ValueError('unique five-corner results required')
        seen.add(corner)
        if a['input_sha256'].get(str(proof))!=sha(proof)or a['continually_enabled_capture_and_filter_assumed']is not False or a['all_setup_checks_retained']is not True or a['conditional_source_hold_shift_cycles']!=1 or a['physical_launch_clock_latency_retained']is not True:raise ValueError('integrated phase proof and retained setup/clock latency required')
        log=screen/'screen.log';pins[str(log)]=sha(log)
        launch={n.rsplit('/',1)[0]for n in a['decision_launch_pins']};capture={n.rsplit('/',1)[0]for n in a['decision_capture_pins']}
        if len(launch)!=2 or len(capture)!=2:raise ValueError('two actual source/capture bits required')
        paths=decision_paths(log.read_text(),launch,capture)
        rows.append(dict(corner=corner,source_period_ns=a['source_clock_period_ns'],paths=paths))
    if seen!={'tt','ff','ss','sf','fs'}:raise ValueError('complete five-corner set required')
    pins[str(Path(__file__).resolve())]=sha(Path(__file__).resolve());verify(pins)
    save(output,dict(input_sha256=pins,synchronizers=13,physical_stage_registers=26,intermediate_cells=b['intermediate_cells'],total_physically_bound_cells=b['physical_cells'],
        interstage_nets_continuous_with_unique_expected_drivers=True,enabled_decision_paths=rows,
        minimum_enabled_decision_setup_slack_ns=min(p['slack_ns']for r in rows for p in r['paths']if p['path_type']=='max'),
        minimum_enabled_decision_hold_slack_ns=min(p['slack_ns']for r in rows for p in r['paths']if p['path_type']=='min'),
        scope='Selected-route structural path binding and sampled enabled-decision phase timing under supplied load/native timing views and nominal routed R/C. Remaining synchronizer first-stage apertures and disabled/reset/startup masking remain open.',
        diagnostic=True,all_crossings_reviewed=False,actual_startup_clock_range_qualified=False,physical_recovery_removal_qualified=False,full_mode_timing_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('stages','trace','physical','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--screens',nargs=5,type=Path,required=True);a=p.parse_args()
    run(a.stages.resolve(),a.trace.resolve(),a.physical.resolve(),[x.resolve()for x in a.screens],a.output.resolve())
