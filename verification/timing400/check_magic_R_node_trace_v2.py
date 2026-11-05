#!/usr/bin/env python3
"""Validate native R provenance tracing on the actual DCO without analog adoption.

Three identical-layout CAD runs: installed, isolated tracing-off, isolated with
private provenance. Require exact exported R/C/X and native intermediate record
multisets. Preserve old RC-capacitance errors: this controls instrumentation,
not physical eligibility of the output. Inspect origins/materials only after
unchanged-output proof.
"""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import json,os,signal,subprocess,time
from audit_active_dco_rc_capacitance import parse
from check_compact_clock_tree import verify
from compare_native_R_networks_v4 import compare
from check_magic_cap_clip_windows import native
from check_isolated_magic_stock_v3 import devices
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def normalized(path):
    d=parse(path)
    return dict(ports=d['ports'],X=d['X'],R=Counter((tuple(sorted([a,b])),v) for a,b,v in d['R']),
        C=Counter((tuple(sorted([a,b])),v) for a,b,v in d['C']))


def main():
    base=ROOT/'build/timing400/release_001';build=base/'magic_R_node_trace_build_001/assessment.json'
    assert verify(build)['full_geometry_trace_build_completed']
    isolated=ROOT/'build/timing400/magic_R_node_trace_623_001/bin/magic'
    original=ROOT/'build/timing450/dco_c1_fine_load_001/rcx_160'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds=ROOT/f'openlane/{top}/runs/c1fine_range_001/final/gds/{top}.gds'
    assert sha(gds)=='0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    owner=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    private=ROOT/'build/timing450/pdk/sky130A';rc=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    out=base/'DCO_R_node_trace_controls_002';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),build,
        MAGIC,isolated,gds,owner,rc,tech,original/'extract.tcl']
    reference=base/'DCO_R_node_trace_controls_001/installed'
    prior=base/'DCO_R_default_network_renaming_audit_004/assessment.json';verify(prior)
    prior_compare=json.loads((prior.parent/'comparison.json').read_text())
    assert prior_compare['bijective_mapping_proven'] and not prior_compare['R_C_differences']['R']
    paths.extend([prior,prior.parent/'comparison.json',Path(__file__).with_name('compare_native_R_networks_v4.py'),
        Path(__file__).with_name('compare_native_R_networks.py'),Path(__file__).with_name('check_magic_cap_clip_windows.py'),
        *[p for p in reference.glob('*') if p.suffix in ['.spice','.ext']]])
    pins={str(p):sha(p) for p in paths};records={};native_records={}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    for label,binary,enabled in [('trace',isolated,True)]:
        target=out/label;target.mkdir();task=target/'extract.tcl'
        # Retain the original native sequence, including automatic then explicit all-net R passes.
        text=(original/'extract.tcl').read_text().replace(str(original),str(target))
        text=text.replace('feedback save ', 'puts "R_NODE_TRACE_EXTRACTION_COMPLETE"\nfeedback save ')
        task.write_text(text);pins[str(task)]=sha(task)
        env=dict(os.environ,PDK_ROOT=str(private.parent))
        for flag in ['OPENPLL_CAP_RC_SUBSTRATE','OPENPLL_CAP_TRACE_SUPPORT','OPENPLL_CAP_TRACE_FILE','OPENPLL_CAP_CLIP_INTERNAL','OPENPLL_R_NODE_TRACE_FILE']:env.pop(flag,None)
        if enabled:env['OPENPLL_R_NODE_TRACE_FILE']=str(target/'R_provenance.log')
        with (target/'extract.log').open('x') as log,(target/'diagnostics.log').open('x') as errors:
            child=subprocess.Popen([str(binary),'-dnull','-noconsole','-rcfile',str(rc),str(task)],cwd=target,
                stdout=log,stderr=errors,env=env,start_new_session=True)
            save(out/'status.json',dict(state='native_R_trace_control_running',tool=label,native_pid=child.pid,release_qualified=False))
            try:code=child.wait(timeout=min(600,max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                save(out/'status.json',dict(state='timeout_inconclusive',tool=label,release_qualified=False));return
        assert code==0 and 'R_NODE_TRACE_EXTRACTION_COMPLETE' in (target/'extract.log').read_text(),(label,code)
        result=compare(reference,target)
        mapping=result.pop('node_mapping',{})
        save(target/'network_comparison.json',result);save(target/'node_mapping.json',mapping)
        assert result.get('bijective_mapping_proven') and result['unchanged_device_parameters_and_mapped_terminals']
        assert result['exact_mapped_R_branch_multiplicity_preserved'] and not result['R_C_differences']['R']
        first,fa,_=native(reference/(top+'.ext'));second,sa,_=native(target/(top+'.ext'))
        differences=[]
        for k in first.keys()|second.keys():
            delta=second.get(k,0)-first.get(k,0);allowance=fa.get(k,0)+sa.get(k,0)
            if abs(delta)>allowance:differences.append(dict(nodes=list(k),delta_ff=str(delta),allowance_ff=str(allowance)))
        save(target/'pre_RC_C_comparison.json',differences)
        assert not differences and devices(reference/(top+'.ext'))==devices(target/(top+'.ext'))
    for p,d in pins.items():assert sha(p)==d,p
    assert (out/'trace/R_provenance.log').is_file()
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        native_CAD_runs_added=1,prior_native_reference_runs_reused=2,
        R_graph_values_and_MOS_terminals_preserved_under_bijective_renaming=True,
        pre_RC_C_matrix_preserved_within_native_print_intervals=True,native_pre_RC_devices_identical=True,
        backannotated_C_equivalence_not_claimed=True,backannotated_C_not_used_for_replacement=True,
        private_R_provenance_file_completed=True,old_RC_C_errors_preserved_for_instrumentation_comparison=True,
        spatial_R_or_C_and_junction_or_transient_error_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='R_trace_native_controls_terminal',R_and_pre_RC_C_preserved=True,release_qualified=False))
    print('DCO R trace: R/MOS graph preserved under renaming; original pre-RC C/devices preserved. Invalid backannotated C excluded; provenance interpretation remains open.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        out=ROOT/'build/timing400/release_001/DCO_R_node_trace_controls_002'
        if out.exists():save(out/'status.json',dict(state='failed',error=repr(error),traceback=traceback.format_exc(),release_qualified=False))
        raise
