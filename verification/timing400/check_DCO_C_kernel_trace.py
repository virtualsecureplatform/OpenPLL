#!/usr/bin/env python3
"""Compare opt-in C-only RC-substrate preparation with installed native RC context.

Reuse the six completed installed/traced R-enabled reference cases. Run three
fresh C-only extracts with the opt-in flag and private tracing; require exact
native C/device equality at min/nom/max and contribution accounting. Confirm no
full wire-R pass or .res.ext output occurs. Retain feedback differences because
R-pass diagnostics are deliberately omitted. No spatial/timing/model adoption.
"""
from datetime import datetime,timezone
from verify_magic_C_surface_alignment_v2 import verify_alignment
from verify_magic_C_kernel_trace_v2 import verify_kernels
from decimal import Decimal
import os
from pathlib import Path
import signal
import subprocess
import time
from check_magic_full_C_trace_v4 import compare,native,matrix,devices
from stream_magic_full_C_trace import reconstruct_stream
from check_compact_clock_tree import verify
from run_candidate_layout_checks_v2 import MAGIC
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    reader=base/'magic_full_C_trace_stream_reader_controls_001/assessment.json'
    assert verify(reader)['stream_reader_controls_passed']
    kernel_reader=base/'magic_C_kernel_deadline_reader_controls_001/assessment.json'
    kr=verify(kernel_reader)
    assert kr['all12_completed_native_cases_equal_to_original_kernel_reader'] and kr['expired_deadline_rejected']
    control=base/'magic_C_kernel_trace_controls_001/assessment.json'
    assert verify(control)['full_geometry_trace_accounting_controls_passed']
    default=base/'magic_RC_substrate_C_default_controls_001/assessment.json'
    assert verify(default)['installed_and_isolated_C_devices_feedback_equal']
    build=base/'magic_C_kernel_trace_build_002/assessment.json'
    assert verify(build)['full_geometry_trace_build_completed']
    isolated=ROOT/'build/timing400/magic_C_kernel_trace_623_002/bin/magic'
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds=ROOT/f'openlane/{top}/runs/c1fine_range_001/final/gds/{top}.gds'
    assert sha(gds)=='0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    private=ROOT/'build/timing450/pdk/sky130A';rc=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    owner_path=base/'distributed_RC_model_qualification_001/owner.json'
    import json
    deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out=base/'DCO_C_kernel_trace_controls_001';out.mkdir(exist_ok=False)
    paths=[Path(__file__).resolve(),Path(__file__).with_name('check_magic_full_C_trace_v4.py'),
        Path(__file__).with_name('check_magic_cap_clip_windows.py'),Path(__file__).with_name('check_isolated_magic_stock_v3.py'),
        Path(__file__).with_name('verify_magic_C_kernel_trace_v2.py'),kernel_reader,reader,control,default,build,MAGIC,isolated,gds,rc,tech,owner_path,Path(__file__).with_name('stream_magic_full_C_trace.py'),Path(__file__).with_name('verify_magic_C_surface_alignment_v2.py')]
    pins={str(p):sha(p) for p in paths};results=[]
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    for corner,style in [('nom','ngspice()'),('min','ngspice(lrlc)'),('max','ngspice(hrhc)')]:
        reference=base/('DCO_resistance_enabled_C_context_001' if corner=='nom' else 'DCO_resistance_enabled_C_context_002')
        expected_receipt=reference/'assessment.json';assert verify(expected_receipt)['full_DCO_trace_accounting_passed']
        pins[str(expected_receipt)]=sha(expected_receipt)
        ref=reference/f'{corner}_installed'
        records={'installed':(matrix(ref/'control.spice'),devices(ref/(top+'.ext')),(ref/'feedback.txt').read_text())}
        for label,binary,enabled in [('trace',isolated,True)]:
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
            if enabled:
                env['OPENPLL_CAP_RC_SUBSTRATE']='1'
                env['OPENPLL_CAP_TRACE_SUPPORT']='1'
                env['OPENPLL_CAP_TRACE_FILE']=str(target/'contributions.log')
                env['OPENPLL_CAP_SURFACE_FILE']=str(target/'surfaces.log')
                env['OPENPLL_CAP_KERNEL_FILE']=str(target/'kernels.log')
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
            assert 'for resistance extraction.' not in (target/'extract.log').read_text()
            assert not list(target.glob('*.res.ext'))
            records[label]=(matrix(target/'control.spice'),devices(target/(top+'.ext')),(target/'feedback.txt').read_text())
            if enabled:
                def kernel_progress(counts):
                    save(out/'status.json',dict(state='assessing_DCO_local_C_kernels',corner=corner,runner_pid=os.getpid(),counts=counts,release_qualified=False))
                kernel_progress({})
                kernel_result=verify_kernels(target/'contributions.log',target/'kernels.log',deadline=deadline,progress=kernel_progress)
                save(target/'kernel_accounting.json',kernel_result)
                save(out/'status.json',dict(state='assessing_DCO_C_surface_alignment_and_matrix',corner=corner,runner_pid=os.getpid(),release_qualified=False))
                surface_result=verify_alignment(target/'contributions.log',target/'surfaces.log')
                save(target/'surface_alignment.json',surface_result)
                expected,rounding,nodes=native(target/(top+'.ext'))
                actual,absolute,event_count,counts,mapping,stats=reconstruct_stream(target/'contributions.log')
                differences,worst=compare(expected,actual,rounding,absolute,event_count)
                assert not differences and surface_result['events']==event_count
                damaged=dict(actual);k=tuple(stats['largest_nonself_event_nodes']);damaged[k]-=Decimal(stats['largest_nonself_event_delta_ff'])
                faults,_=compare(expected,damaged,rounding,absolute,event_count);assert faults
                save(target/'node_ids.json',mapping);save(target/'matrix_differences.json',differences)
                # Native trace retains every raw support; compact summary avoids a second giant JSON event copy.
                results.append(dict(corner=corner,native_devices=sum(records[label][1].values()),native_nonzero_C_pairs=len(records[label][0]),trace_events=event_count,events_by_reason=counts,
                    kernel_accounting=kernel_result,native_matrix_reconstructed=not differences,matrix_difference_pairs=len(differences),
                    maximum_difference_ff=worst,unlocated_output_clamp_events=stats['unlocated_output_clamp_events'],
                    signed_negative_events=stats['signed_negative_events'],
                    missing_actual_contribution_negative_control_rejected=True))
                del actual,expected,absolute
        same=records['installed'][:2]==records['trace'][:2];assert same,corner
        results[-1]['installed_RC_context_and_C_only_context_exact_C_devices_identical']=same
        results[-1]['native_feedback_equal_without_running_R_pass']=records['installed'][2]==records['trace'][2]
        results[-1]['full_wire_R_extraction_skipped']=True
        save(out/'comparison.json',results)
    for p,d in pins.items():assert sha(p)==d,p
    passed=all(r['native_matrix_reconstructed'] for r in results)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        full_DCO_trace_accounting_passed=passed,complete_ordered_plane_material_metadata=True,
        local_charge_kernel_integrals_and_alignment_passed=all(r['kernel_accounting']['local_kernel_integrals_reconstructed'] and r['kernel_accounting']['complete_ordered_kernel_to_contribution_alignment'] for r in results),native_CAD_runs=3,RC_corners=['min','nom','max'],RC_substrate_context=True,full_wire_R_extraction_skipped=True,
        installed_RC_and_opt_in_C_only_exact_C_and_devices_identical=True,results=results,
        support_boxes_independently_physically_verified=False,spatial_RC_and_transient_error_qualified=False,
        parent_fill_loading_and_supply_R_included=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='DCO_trace_controls_terminal',accounting_passed=passed,release_qualified=False))
    print('DCO native RC-substrate C-only equivalence:',passed,'; installed RC and opt-in C-only C/devices identical at three RC corners; full R pass skipped. Spatial/timing qualification remains open.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        out=ROOT/'build/timing400/release_001/DCO_C_kernel_trace_controls_001'
        if out.exists():
            save(out/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),release_qualified=False))
            save(out/'status.json',dict(state='control_failed',error=repr(error),release_qualified=False))
        raise
