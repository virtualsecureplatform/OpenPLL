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
    out=base/'DCO_R_node_trace_controls_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),build,
        MAGIC,isolated,gds,owner,rc,tech,original/'extract.tcl']
    pins={str(p):sha(p) for p in paths};records={};native_records={}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    for label,binary,enabled in [('installed',MAGIC,False),('isolated',isolated,False),('trace',isolated,True)]:
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
        records[label]=normalized(target/(top+'.rcx.spice'))
        native_records[label]=Counter((target/(top+'.res.ext')).read_text().splitlines())
        if label!='installed':
            same=records[label]==records['installed'];same_native=native_records[label]==native_records['installed']
            save(target/'comparison.json',dict(exported_R_C_X_ports_equal=same,native_intermediate_records_equal=same_native,
                native_record_delta=sum((native_records[label]-native_records['installed']).values()),release_qualified=False))
            assert same and same_native,label
    for p,d in pins.items():assert sha(p)==d,p
    assert (out/'trace/R_provenance.log').is_file()
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        native_CAD_runs=3,installed_default_and_R_trace_exported_R_C_X_ports_identical=True,
        installed_default_and_R_trace_native_intermediate_records_identical=True,
        private_R_provenance_file_completed=True,old_RC_C_errors_preserved_for_instrumentation_comparison=True,
        spatial_R_or_C_and_junction_or_transient_error_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='R_trace_native_controls_terminal',native_outputs_unchanged=True,release_qualified=False))
    print('Actual DCO R trace controls pass: installed/default/traced R/C/X and intermediate records unchanged. Provenance interpretation remains open.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        out=ROOT/'build/timing400/release_001/DCO_R_node_trace_controls_001'
        if out.exists():save(out/'status.json',dict(state='failed',error=repr(error),traceback=traceback.format_exc(),release_qualified=False))
        raise
