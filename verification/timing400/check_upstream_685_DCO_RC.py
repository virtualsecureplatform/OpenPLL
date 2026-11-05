#!/usr/bin/env python3
"""Test whether unmodified upstream685 preserves DCO charge through native full R.

Use its own native RC-substrate context for both original C-only export and
full-R backannotation. Export all capacitors at zero threshold. Compare zero-
wire-R matrices and MOS parameters; no long analog work or model adoption.
"""
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import json,os,signal,subprocess,time
from audit_active_dco_rc_capacitance import parse,compare,terminals
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def local_rounding(before,after):
    parent={}
    def find(n):
        parent.setdefault(n,n)
        while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
        return n
    for a,b,r in after['R']:assert r>=0;parent[find(a)]=find(b)
    labels={}
    def bind(n,label):
        root=find(n)
        if root in labels:assert labels[root]==label,(root,labels[root],label)
        labels[root]=label
    for n in before['ports']:bind(n,n)
    for name,row in before['X'].items():
        other=after['X'][name];count=terminals(row)
        assert count==terminals(other) and row[count]==other[count]
        for a,b in zip(row[:count],other[:count]):bind(b,a)
    original_nodes={n for a,b,c in before['C'] for n in [a,b]}
    for a,b,c in after['C']:
        for n in [a,b]:
            if n in original_nodes:bind(n,n)
    from collections import defaultdict
    def matrix(rows,resolve):
        values=defaultdict(Decimal);allow=defaultdict(Decimal)
        for a,b,c in rows:
            a,b=resolve(a),resolve(b)
            if a==b:continue
            k=tuple(sorted([a,b]));values[k]+=c
            if c:allow[k]+=Decimal(10)**(abs(c).adjusted()-5)/2
        return values,allow
    a,ap=matrix(before['C'],lambda n:n);b,bp=matrix(after['C'],lambda n:labels[find(n)])
    differences=[]
    for k in a.keys()|b.keys():
        delta=b[k]-a[k];allowance=ap[k]+bp[k]
        if abs(delta)>allowance:differences.append(dict(nodes=list(k),before_ff=str(a[k]*Decimal('1e15')),
            after_zero_wire_R_ff=str(b[k]*Decimal('1e15')),delta_ff=str(delta*Decimal('1e15')),print_allowance_ff=str(allowance*Decimal('1e15'))))
    return differences


def main():
    base=ROOT/'build/timing400/release_001';build=base/'magic_upstream_685_build_002/assessment.json'
    assert verify(build)['isolated_stock_build_completed']
    binary=ROOT/'build/timing400/magic_upstream_685_002/bin/magic';assert binary.is_file()
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds=ROOT/f'openlane/{top}/runs/c1fine_range_001/final/gds/{top}.gds'
    assert sha(gds)=='0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    private=ROOT/'build/timing450/pdk/sky130A';rc=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    out=base/'upstream_685_DCO_RC_charge_control_001';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),original_owner=str(owner_path),
        deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    task=out/'extract.tcl';task.write_text(f'''crashbackups disable
locking disable
drc off
if {{[catch {{
gds read {gds}
load {top}
select top cell
flatten flat
load flat
cellname delete {top}
cellname rename flat {top}
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do resistance
extract do coupling
extract do adjust
extract do unique
extract warn all
extresist simplify off
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist off
ext2spice -f ngspice -o {out}/before.spice {top}.ext
extresist all
ext2spice extresist on
ext2spice -f ngspice -o {out}/after.spice {top}.ext
feedback save {out}/feedback.txt
puts "UPSTREAM_DCO_RC_CHARGE_COMPLETE"
}} error]}} {{puts stderr $error;exit 1}}
exit 0
''')
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),build,binary,gds,rc,tech,owner_path,task]
    pins={str(p):sha(p) for p in paths};env=dict(os.environ,PDK_ROOT=str(private.parent))
    for key in list(env):
        if key.startswith('OPENPLL_CAP_') or key.startswith('OPENPLL_R_NODE_'):env.pop(key,None)
    with (out/'extract.log').open('x') as log,(out/'diagnostics.log').open('x') as diagnostics:
        child=subprocess.Popen([str(binary),'-dnull','-noconsole','-rcfile',str(rc),str(task)],cwd=out,
            env=env,stdout=log,stderr=diagnostics,start_new_session=True)
        save(out/'status.json',dict(state='native_upstream_DCO_charge_control_running',native_pid=child.pid,release_qualified=False))
        try:code=child.wait(timeout=min(900,max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
    assert code==0 and 'UPSTREAM_DCO_RC_CHARGE_COMPLETE' in (out/'extract.log').read_text(),code
    before,after=parse(out/'before.spice'),parse(out/'after.spice')
    summary=compare(before,after);differences=local_rounding(before,after)
    save(out/'comparison.json',summary);save(out/'per_pair_C_differences.json',differences)
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ['owner.json','status.json']},
        native_CAD_runs=1,unmodified_upstream_version='8.3.685',native_same_RC_substrate_context_used_before_and_after=True,
        zero_threshold_all_C_exported=True,MOS=8618,intrinsic_resistor_wrappers=2,wire_R=len(after['R']),
        original_C_records=len(before['C']),backannotated_C_records=len(after['C']),
        MOS_models_parameters_and_zero_wire_R_connections_preserved=summary['transistor_models_parameters_and_collapsed_connections_preserved'],
        capacitor_matrix_preserved_within_per_pair_print_intervals=not differences,changed_C_pairs_outside_print_intervals=len(differences),
        spatial_RC_or_transient_error_qualified=False,physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='upstream_DCO_charge_control_terminal',changed_C_pairs=len(differences),release_qualified=False))
    print('Unmodified685 DCO charge control:',len(differences),'changed C pairs; device parameters preserved:',summary['transistor_models_parameters_and_collapsed_connections_preserved'],'; no model adoption.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        out=ROOT/'build/timing400/release_001/upstream_685_DCO_RC_charge_control_001'
        if out.exists():save(out/'status.json',dict(state='failed',error=repr(error),traceback=traceback.format_exc(),release_qualified=False))
        raise
