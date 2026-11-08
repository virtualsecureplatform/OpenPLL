"""Compare trace-off/on native circuits and reconstruct exported flat coupling."""
import argparse,json,math,os,re,time
from collections import defaultdict,Counter
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from audit_keeper_native_R_contraction import compare

from audit_magic_coupling_geometry_trace import reconstruct
from audit_magic_ground_lifecycle import audit as ground_audit
from audit_magic_overlap_support import reconstruct as overlap_audit
from audit_magic_fringe_support import reconstruct as fringe_audit
from audit_magic_ground_support import audit as ground_support_audit
from audit_magic_ground_overlap import audit as ground_overlap_audit
from audit_magic_ground_halo import audit as ground_halo_audit

def ledger(trace,ext):
    numeric=trace.with_name('numeric.jsonl')
    with trace.open()as source,numeric.open('w')as target:
        for line in source:
            if json.loads(line)['kind']not in ['ground_halo_begin','ground_halo_end','ground_halo_subtract','ground_overlap_subtraction','ground_support','overlap_support_begin','overlap_shield_leaf','overlap_support_end','fringe_rule_begin','fringe_rule_end','fringe_shield_leaf']:target.write(line)
    supports=[];overlap=overlap_audit(trace,supports.append)
    if not overlap['all_overlap_support_reconstructed']:raise ValueError('unsupported overlap geometry')
    save(trace.with_name('overlap_support.json'),dict(metrics=overlap,supports=supports))
    fringe_support=[];fringe=fringe_audit(trace,fringe_support.append)
    if not fringe['all_rectilinear_fringe_support_verified']:raise ValueError('unsupported fringe geometry')
    save(trace.with_name('fringe_support.json'),dict(metrics=fringe,supports=fringe_support))
    coupling=reconstruct(numeric,ext)
    ground=ground_audit(numeric,ext)
    if not coupling['all_exported_C_pairs_reconstructed_at_native_precision']:
        raise ValueError('coupling trace reconstruction mismatch')
    if not ground['exported_ground_records_match']:
        raise ValueError('ground trace reconstruction mismatch')
    return dict(coupling=coupling,ground=ground,overlap=overlap,fringe=fringe,ground_support=ground_support_audit(trace),ground_overlap=ground_overlap_audit(trace),ground_halo=ground_halo_audit(trace))

def run(engine,output):
    receipt=engine/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a.get('ground_halo_subtraction_instrumented'):raise ValueError('explicit halo ground instrumentation required')
    if not a.get('ground_overlap_subtraction_support_linked'):raise ValueError('explicit ground-overlap provenance required')
    if not a.get('ground_area_and_perimeter_support_instrumented'):raise ValueError('explicit ground-support instrumentation required')
    if a['capacitance_equations_modified'] or a['release_tool_replaced']:raise ValueError('isolated logging-only engine required')
    binary=Path(a['installed_executable']);output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));pins={str(p):sha(p)for p in [receipt,binary,TECH,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_native_R_contraction.py'),Path(__file__).with_name('audit_magic_coupling_geometry_trace.py'),Path(__file__).with_name('audit_magic_ground_lifecycle.py'),Path(__file__).with_name('audit_magic_overlap_support.py'),Path(__file__).with_name('audit_magic_fringe_support.py'),Path(__file__).with_name('magic_fringe_kernel.py'),Path(__file__).with_name('audit_magic_ground_support.py'),Path(__file__).with_name('audit_magic_ground_overlap.py'),Path(__file__).with_name('audit_magic_ground_halo.py')]};results=[];artifacts={}
    cases=[('shielded_overlap','m3',[0,0,4000,100]),('recursive_shielding','m4',[0,0,4000,100]),('fringe_shielding','m3',[0,120,4000,220]),('recursive_fringe','m4',[0,120,4000,220])]
    try:
        for name,layer,box in cases:
            folders=[];top='Trace_'+name
            for enabled in [False,True]:
                folder=output/(name+('_on'if enabled else'_off'));folder.mkdir();folders.append(folder);rc=folder/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n');script=folder/'probe.tcl';spice=folder/'view.spice';trace=folder/'coupling.jsonl'
                extra=('box values 3000 120 4000 220\n'if name=='recursive_fringe'else'box values 3000 0 4000 100\n')+'paint m3\nlabel T center m3\nport make 4\n'if name in ['recursive_shielding','recursive_fringe']else''
                shield_box='0 120 2000 220'if name in ['fringe_shielding','recursive_fringe']else'0 0 2000 100'
                script.write_text(f'''cd {{{folder}}}
if {{[catch {{
load {top}
box values 0 0 4000 100
paint m1
label A center m1
port make 1
box values {' '.join(map(str,box))}
paint {layer}
label B center {layer}
port make 2
box values {shield_box}
paint m2
label S center m2
port make 3
{extra}extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o {{{spice}}} {top}.ext
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
                pins.update({str(p):sha(p)for p in [rc,script]});verify(pins)
                os.environ.pop('OPENPLL_COUPLING_TRACE',None)
                if enabled:os.environ['OPENPLL_COUPLING_TRACE']=str(trace)
                save(output/'status.json',dict(state='native_trace_neutrality_control',case=name,trace_enabled=enabled,release_ready=False))
                with lease(1,8,deadline):execute([binary,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],folder/'native.log',deadline,8)
                artifacts.update({str(p):sha(p)for p in [spice,folder/(top+'.ext'),folder/'native.log']})
                if enabled:artifacts[str(trace)]=sha(trace)
                elif trace.exists():raise ValueError('trace-off process unexpectedly wrote a trace')
            off,on=folders;metrics=compare((off/'view.spice').read_text(),(on/'view.spice').read_text())
            if not metrics['exact_device_and_C_contraction_verified']:raise ValueError('logging changed the native circuit')
            details=ledger(on/'coupling.jsonl',on/(top+'.ext'));artifacts.update({str(p):sha(p)for p in [on/'numeric.jsonl',on/'overlap_support.json',on/'fringe_support.json']});results.append(dict(case=name,normal_native_completion=True,trace_off_on_exact_device_and_C_match=True,**details));save(output/'progress.json',results)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_eight_native_controls_complete=True,logging_preserves_tested_circuits=True,legacy_side_overlap_runtime_path_qualified=False,numeric_ground_lifecycle_verified=True,ground_halo_subtraction_provenance_verified=True,ground_overlap_subtraction_provenance_verified=True,ground_area_perimeter_support_verified=True,ground_shielding_geometry_qualified=False,ground_capacitance_geometry_traced=False,full_PLL_geometry_trace_qualified=False,pointwise_placement_qualified=False,release_ready=False));save(output/'status.json',dict(state='ground_support_native_controls_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['engine','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.engine.resolve(),a.output.resolve())
