#!/usr/bin/env python3
"""Validate full-geometry contribution accounting before any spatial RC use.

Trace-enabled extraction must match native C/device output with tracing off.
Actual accumulator deltas must reconstruct the native positive matrix within
native print precision and a conservative arithmetic allowance. Bounding boxes
are recorded but independent physical support/transient bounds remain open.
"""
from verify_magic_C_surface_alignment_v2 import verify_alignment
from verify_magic_C_kernel_trace import verify_kernels
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal
import json
import os
import shutil
from pathlib import Path
import shlex
import signal
import subprocess
import time
from check_magic_cap_clip_windows import native,GROUND
from check_isolated_magic_stock_v3 import matrix,devices
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def reconstruct(log):
    mapping={};begins=0
    for line in log.splitlines():
        if line.startswith('OPENPLL_BEGIN '):
            f=shlex.split(line);assert f[-1]=='full_geometry';begins+=1
        if line.startswith('OPENPLL_ID '):
            f=shlex.split(line);assert len(f)==4 and f[1] not in mapping
            mapping[f[1]]=GROUND if f[3]=='1' else f[2]
    assert begins==1 and log.splitlines().count('OPENPLL_END')==1 and list(mapping.values()).count(GROUND)==1
    totals=defaultdict(Decimal);absolute=defaultdict(Decimal);counts=Counter();events=[]
    def add(a,b,value,reason,support):
        assert a in mapping and (b is None or b in mapping),(a,b)
        aa=mapping[a];bb=GROUND if b is None else mapping[b]
        assert value.is_finite() and value!=0
        k=tuple(sorted([aa,bb]));counts[reason]+=1
        events.append(dict(a_id=a,b_id=b,nodes=list(k),delta_ff=str(value),reason=reason,support=support,
            zero_energy_self_branch=aa==bb))
        if aa!=bb:totals[k]+=value;absolute[k]+=abs(value)
    for line in log.splitlines():
        if line.startswith('OPENPLL_G '):
            f=shlex.split(line);assert len(f) in [5,9]
            support=None
            if f[4]=='box':
                support=[list(map(int,f[5:9]))];assert len(f)==9
            else:assert f[4]=='unlocated' and f[3]=='output_zero_clamp'
            add(f[1],None,Decimal(f[2])*Decimal('.001'),f[3],support)
        elif line.startswith('OPENPLL_P '):
            f=shlex.split(line);assert len(f)==14 and f[5]=='boxes'
            support=[list(map(int,f[6:10])),list(map(int,f[10:14]))]
            add(f[1],f[2],Decimal(f[3])*Decimal('.001'),f[4],support)
    for row in events:
        if row['support']:
            for l,b,r,t in row['support']:assert l<=r and b<=t
    assert events and totals
    return dict(totals),dict(absolute),events,dict(counts),mapping


def compare(expected,actual,rounding,absolute,event_count):
    n=Decimal(8*event_count+8);eps=Decimal(2)**-52
    assert n*eps<Decimal('.01')
    gamma=n*eps/(1-n*eps)
    rows=[];worst=Decimal(0)
    for k in sorted(expected.keys()|actual.keys()):
        delta=actual.get(k,Decimal(0))-expected.get(k,Decimal(0));worst=max(worst,abs(delta))
        allowance=rounding.get(k,Decimal(0))+gamma*absolute.get(k,Decimal(0))+Decimal('1e-9')
        if abs(delta)>allowance:rows.append(dict(nodes=list(k),native_ff=str(expected.get(k,0)),trace_ff=str(actual.get(k,0)),
            delta_ff=str(delta),allowance_ff=str(allowance)))
    return rows,str(worst)


def main():
    base=ROOT/'build/timing400/release_001';default_dir=base/'magic_full_C_trace_default_controls_003'
    reference=default_dir/'assessment.json';assert verify(reference)['installed_and_isolated_C_devices_feedback_equal']
    build=base/'magic_C_kernel_trace_build_002/assessment.json';assert verify(build)['full_geometry_trace_build_completed']
    binary=ROOT/'build/timing400/magic_C_kernel_trace_623_002/bin/magic'
    private=ROOT/'build/timing450/pdk/sky130A';rc=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    owner_path=base/'distributed_RC_model_qualification_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime'];assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    cases=[('floating_metal',base/'fill_capacitance_control_001/drawing_purpose/control.gds','FILL_CAP_CONTROL'),
        ('floating_poly',base/'lower_fill_capacitance_controls_001/poly_drawing/control.gds','LOWER_FILL_CONTROL'),
        ('HS_NAND',base/'capacitance_corner_controls_001/nand2_2.gds','CAP_CORNER_NAND'),
        ('HD_narrow_FF',base/'narrow_mos_corner_exports_001/control.gds','NARROW_MOS_CONTROL')]
    out=base/'magic_C_kernel_trace_controls_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).with_name('verify_magic_C_kernel_trace.py'),base/'magic_full_C_trace_controls_001/status.json',Path(__file__).resolve(),Path(__file__).with_name('check_magic_cap_clip_windows.py'),
        Path(__file__).with_name('check_isolated_magic_stock_v3.py'),reference,build,binary,rc,tech,owner_path,base/'magic_C_surface_trace_controls_001/failure.json',
        Path(__file__).with_name('verify_magic_C_surface_alignment.py'),Path(__file__).with_name('verify_magic_C_surface_alignment_v2.py'),
        *[gds for name,gds,top in cases]]
    pins={str(p):sha(p) for p in paths};results=[]
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    env=dict(os.environ,PDK_ROOT=str(private.parent),OPENPLL_CAP_TRACE_SUPPORT='1');env.pop('OPENPLL_CAP_CLIP_INTERNAL',None)
    for flag in ['OPENPLL_CAP_RC_SUBSTRATE','OPENPLL_R_RETAIN_MESH','OPENPLL_R_NODE_TRACE_FILE','OPENPLL_R_SEGMENT_TRACE_FILE','OPENPLL_R_BIND_TRACE_FILE','OPENPLL_SPICE_DEVICE_TRACE_FILE']:env.pop(flag,None)
    for corner,style in [('min','ngspice(lrlc)'),('nom','ngspice()'),('max','ngspice(hrhc)')]:
        for name,gds,top in cases:
            target=out/f'{corner}_{name}';task=target/'extract.tcl'
            reused = False
            if reused:
                old_case=base/'magic_C_surface_trace_controls_001/min_floating_metal'
                assert 'FULL_C_TRACE_CONTROL_COMPLETE' in (old_case/'extract.log').read_text()
                # Prior native exit/marker and C/device/feedback checks passed before the header assessor failed.
                code=0
                shutil.copytree(old_case,target)
                for saved in old_case.iterdir():
                    if saved.is_file():
                        pins[str(saved)]=sha(saved)
                        assert sha(target/saved.name)==sha(saved)
                pins[str(task)]=sha(task)
            else:
                target.mkdir()
                task.write_text(f'''crashbackups disable
    locking disable
    drc off
    if {{[catch {{
    gds read {gds}
    load {top}
    puts "OPENPLL_INTERNAL_SCALE_UM [cif scale out]"
    extract style {style}
    extract do capacitance
    extract do coupling
    extract no resistance
    extract all
    feedback save {target}/feedback.txt
    ext2spice lvs
    ext2spice cthresh 0
    ext2spice -f ngspice -o {target}/control.spice {top}.ext
    puts "FULL_C_TRACE_CONTROL_COMPLETE"
    }} error]}} {{puts stderr $error;exit 1}}
    exit 0
    ''');pins[str(task)]=sha(task)
                env['OPENPLL_CAP_TRACE_FILE']=str(target/'contributions.log')
                env['OPENPLL_CAP_SURFACE_FILE']=str(target/'surfaces.log')
                env['OPENPLL_CAP_KERNEL_FILE']=str(target/'kernels.log')
                with (target/'extract.log').open('x') as log, (target/'trace.log').open('x') as trace:
                    child=subprocess.Popen([str(binary),'-dnull','-noconsole','-rcfile',str(rc),str(task)],cwd=target,
                        stdout=log,stderr=trace,env=env,start_new_session=True)
                    save(out/'status.json',dict(state='native_full_C_trace_running',corner=corner,case=name,native_pid=child.pid,
                        native_analog_jobs_added=0,release_qualified=False))
                    try:code=child.wait(timeout=min(60,max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGTERM)
                        try:child.wait(timeout=10)
                        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                        save(out/'status.json',dict(state='timeout_inconclusive',release_qualified=False));return
            text=(target/'extract.log').read_text();assert code==0 and 'FULL_C_TRACE_CONTROL_COMPLETE' in text,(name,corner,code)
            old=default_dir/f'{corner}_{name}_isolated'
            same=matrix(old/'control.spice')==matrix(target/'control.spice') and devices(old/(top+'.ext'))==devices(target/(top+'.ext'))
            assert same and (old/'feedback.txt').read_text()==(target/'feedback.txt').read_text(),(name,corner)
            surface_result=verify_alignment(target/'contributions.log',target/'surfaces.log')
            kernel_result=verify_kernels(target/'contributions.log',target/'kernels.log')
            save(target/'kernel_accounting.json',kernel_result)
            save(target/'surface_alignment.json',surface_result)
            native_C,rounding,nodes=native(target/(top+'.ext'))
            recovered,absolute,events,counts,mapping=reconstruct((target/'contributions.log').read_text())
            differences,worst=compare(native_C,recovered,rounding,absolute,len(events))
            assert surface_result['events']==len(events)
            assert not differences
            eligible=[r for r in events if not r['zero_energy_self_branch']]
            removed=max(eligible,key=lambda r:abs(Decimal(r['delta_ff'])))
            damaged=dict(recovered);k=tuple(removed['nodes']);damaged[k]-=Decimal(removed['delta_ff'])
            faults,_=compare(native_C,damaged,rounding,absolute,len(events));assert faults
            save(target/'events.json',events);save(target/'node_ids.json',mapping);save(target/'matrix_differences.json',differences)
            results.append(dict(case=name,corner=corner,native_run_reused_after_assessor_failure=reused,trace_enabled_C_MOS_feedback_equal_to_default=same,
                kernel_accounting=kernel_result,trace_events=len(events),events_by_reason=counts,native_matrix_reconstructed=not differences,
                matrix_difference_pairs=len(differences),maximum_difference_ff=worst,
                unlocated_output_clamp_events=sum(r['support'] is None for r in events),
                signed_negative_events=sum(Decimal(r['delta_ff'])<0 for r in events),
                missing_actual_contribution_negative_control_rejected=True))
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'comparison.json',results)
    passed=all(r['native_matrix_reconstructed'] and r['trace_enabled_C_MOS_feedback_equal_to_default'] for r in results)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        native_CAD_runs=12,native_CAD_runs_added=12,completed_native_runs_reused=0,physical_controls=4,RC_corners=['min','nom','max'],
        full_geometry_trace_accounting_controls_passed=passed,
        complete_plane_material_metadata_for_all_C_contributions=True,
        local_kernel_integrals_and_event_alignment_controls_passed=all(r['kernel_accounting']['local_kernel_integrals_reconstructed'] and r['kernel_accounting']['complete_ordered_kernel_to_contribution_alignment'] for r in results),
        trace_enabled_C_MOS_feedback_unchanged=True,native_print_and_arithmetic_allowances_explicit=True,
        missing_actual_contribution_fault_rejected=True,signed_and_unlocated_clamp_fields_retained=True,
        support_boxes_independently_physically_verified=False,full_layout_trace_qualified=False,
        spatial_RC_and_transient_error_qualified=False,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='full_C_trace_controls_terminal',controls_passed=passed,release_qualified=False))
    print('Full-geometry trace controls:',passed,'on12 case/corner combinations; physical supports/full-layout/timing remain unqualified.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        failure=ROOT/'build/timing400/release_001/magic_C_kernel_trace_controls_001'
        if failure.exists():
            save(failure/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),release_qualified=False))
            save(failure/'status.json',dict(state='control_failed',error=repr(error),release_qualified=False))
        raise
