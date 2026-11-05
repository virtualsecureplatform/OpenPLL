#!/usr/bin/env python3
"""Check full-DCO tracing against installed native extraction at all three RC corners.

No analog jobs or RC model adoption. Require the four physical trace controls,
then compare installed/default/traced native devices, C, and feedback; recover
traced native C within explicit print/arithmetic allowances. Supports remain
conservative boxes, not qualified spatial locations or a timing error bound.
"""
from datetime import datetime,timezone
from decimal import Decimal
import os
from pathlib import Path
import signal
import subprocess
import time
from check_magic_full_C_trace_v3 import reconstruct,compare,native,matrix,devices
from check_compact_clock_tree import verify
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    control=base/'magic_full_C_trace_controls_003/assessment.json'
    assert verify(control)['full_geometry_trace_accounting_controls_passed']
    default=base/'magic_full_C_trace_default_controls_002/assessment.json'
    assert verify(default)['installed_and_isolated_C_devices_feedback_equal']
    build=base/'magic_full_C_trace_build_002/assessment.json'
    assert verify(build)['full_geometry_trace_build_completed']
    isolated=ROOT/'build/timing400/magic_full_C_trace_623_002/bin/magic'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds=ROOT/f'openlane/{top}/runs/c1fine_range_001/final/gds/{top}.gds'
    assert sha(gds)=='0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    private=ROOT/'build/timing450/pdk/sky130A';rc=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    owner_path=base/'candidate_layout_checks_001/owner.json'
    import json
    deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out=base/'DCO_full_C_trace_controls_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('check_magic_full_C_trace_v3.py'),
        Path(__file__).with_name('check_magic_cap_clip_windows.py'),Path(__file__).with_name('check_isolated_magic_stock_v3.py'),
        control,default,build,MAGIC,isolated,gds,rc,tech,owner_path]
    pins={str(p):sha(p) for p in paths};results=[]
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    for corner,style in [('min','ngspice(lrlc)'),('nom','ngspice()'),('max','ngspice(hrhc)')]:
        records={}
        for label,binary,enabled in [('installed',MAGIC,False),('isolated',isolated,False),('trace',isolated,True)]:
            target=out/f'{corner}_{label}';target.mkdir();task=target/'extract.tcl'
            task.write_text(f'''crashbackups disable
locking disable
drc off
if {{[catch {{
gds read {gds}
load {top}
select top cell
flatten TRACE_DCO
load TRACE_DCO
cellname delete {top}
cellname rename TRACE_DCO {top}
select top cell
puts "OPENPLL_INTERNAL_SCALE_UM [cif scale out]"
extract style {style}
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract do adjust
extract do unique
extract warn all
extract all
feedback save {target}/feedback.txt
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist off
ext2spice -f ngspice -o {target}/control.spice {top}.ext
puts "DCO_FULL_C_TRACE_COMPLETE"
}} error]}} {{puts stderr $error;exit 1}}
exit 0
''');pins[str(task)]=sha(task)
            env=dict(os.environ,PDK_ROOT=str(private.parent));env.pop('OPENPLL_CAP_CLIP_INTERNAL',None);env.pop('OPENPLL_CAP_TRACE_SUPPORT',None)
            if enabled:env['OPENPLL_CAP_TRACE_SUPPORT']='1'
            with (target/'extract.log').open('x') as log,(target/'trace.log').open('x') as trace:
                child=subprocess.Popen([str(binary),'-dnull','-noconsole','-rcfile',str(rc),str(task)],cwd=target,
                    stdout=log,stderr=trace,env=env,start_new_session=True)
                save(out/'status.json',dict(state='native_DCO_CAD_running',corner=corner,tool=label,native_pid=child.pid,
                    native_analog_jobs_added=0,release_qualified=False))
                try:code=child.wait(timeout=min(900,max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                    save(out/'status.json',dict(state='timeout_inconclusive',corner=corner,tool=label,release_qualified=False));return
            assert code==0 and 'DCO_FULL_C_TRACE_COMPLETE' in (target/'extract.log').read_text(),(corner,label,code)
            records[label]=(matrix(target/'control.spice'),devices(target/(top+'.ext')),(target/'feedback.txt').read_text())
            if enabled:
                expected,rounding,nodes=native(target/(top+'.ext'))
                actual,absolute,events,counts,mapping=reconstruct((target/'trace.log').read_text())
                differences,worst=compare(expected,actual,rounding,absolute,len(events))
                eligible=[r for r in events if not r['zero_energy_self_branch']]
                removed=max(eligible,key=lambda r:abs(Decimal(r['delta_ff'])))
                damaged=dict(actual);k=tuple(removed['nodes']);damaged[k]-=Decimal(removed['delta_ff'])
                faults,_=compare(expected,damaged,rounding,absolute,len(events));assert faults
                save(target/'node_ids.json',mapping);save(target/'matrix_differences.json',differences)
                # Native trace retains every raw support; compact summary avoids a second giant JSON event copy.
                results.append(dict(corner=corner,native_devices=sum(records[label][1].values()),native_nonzero_C_pairs=len(records[label][0]),trace_events=len(events),events_by_reason=counts,
                    native_matrix_reconstructed=not differences,matrix_difference_pairs=len(differences),
                    maximum_difference_ff=worst,unlocated_output_clamp_events=sum(r['support'] is None for r in events),
                    signed_negative_events=sum(Decimal(r['delta_ff'])<0 for r in events),
                    missing_actual_contribution_negative_control_rejected=True))
                del events,eligible,actual,expected,absolute
        same=records['installed']==records['isolated']==records['trace'];assert same,corner
        results[-1]['installed_default_and_trace_C_devices_feedback_identical']=same
        save(out/'comparison.json',results)
    for p,d in pins.items():assert sha(p)==d,p
    passed=all(r['native_matrix_reconstructed'] for r in results)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        full_DCO_trace_accounting_passed=passed,native_CAD_runs=9,RC_corners=['min','nom','max'],
        installed_default_and_trace_C_devices_feedback_identical=True,results=results,
        support_boxes_independently_physically_verified=False,spatial_RC_and_transient_error_qualified=False,
        parent_fill_loading_and_supply_R_included=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='DCO_trace_controls_terminal',accounting_passed=passed,release_qualified=False))
    print('DCO full-C trace accounting:',passed,'; installed/default/trace native outputs identical at three RC corners. Spatial/timing qualification remains open.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        out=ROOT/'build/timing400/release_001/DCO_full_C_trace_controls_001'
        if out.exists():
            save(out/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),release_qualified=False))
            save(out/'status.json',dict(state='control_failed',error=repr(error),release_qualified=False))
        raise
