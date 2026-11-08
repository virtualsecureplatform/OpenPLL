"""Test explicit PLLOUT extresist after C-only extraction; no RC model qualification."""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import MAGIC,TECH
from extract_keeper_flat_geometry_C import FLAT

def run(flat,anchors,output):
    receipts=[p/'assessment.json' for p in [flat,anchors]];a,b=[json.loads(p.read_text()) for p in receipts]
    for r in [a,b]:verify(r['input_sha256']);verify(r['artifacts'])
    if not b['all_exceptions_have_structural_anchor']:raise ValueError('structural driver preflight required')
    ext=flat/(FLAT+'.ext');gds=flat/'flat.gds'
    if b['input_sha256'].get(str(ext))!=sha(ext):raise ValueError('same checked flat EXT required')
    if not any(line.startswith('node "PLLOUT" ') for line in ext.open()):raise ValueError('explicit native PLLOUT node required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n');script=output/'pilot.tcl';model=output/'pilot.spice'
    script.write_text(f'''cd {{{output}}}
if {{[catch {{
gds read {{{gds}}}
load {FLAT}
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract warn all
extresist simplify off
extresist extout on
extresist silent off
extresist include PLLOUT
extract all
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist on
ext2spice -o {{{model}}} {FLAT}.ext
feedback save {{{output/'feedback.txt'}}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
    folder=Path(__file__).resolve().parent;files=[*receipts,ext,gds,rc,script,MAGIC,TECH,Path(__file__).resolve(),*[folder/n for n in ['compiled_charge_v2.py','replay_keeper_flat_signed_C.py','extract_keeper_flat_geometry_C.py']]];pins={str(p):sha(p) for p in files}
    save(output/'inputs.json',dict(input_sha256=pins,only_requested_net='PLLOUT',initial_full_RC_mode=False,explicit_extresist_after_C_only=True,CPU=26,memory_GiB=16,native_cap_s=1200,maximum_native_cases=1,automatic_identical_retry=False,signed_C_export_threshold_fF='-1e100',resistor_simplification=False,release_ready=False))
    try:
        save(output/'status.json',dict(state='PLLOUT_native_resistance_pilot_running',release_ready=False))
        with lease(1,16,deadline):execute([MAGIC,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],output/'native.log',deadline,16)
        verify(pins);res=output/(FLAT+'.res.ext');generated=[model,res,output/(FLAT+'.ext'),output/'native.log',output/'feedback.txt']
        if any(not p.exists() for p in generated):raise ValueError('native extraction artifacts missing')
        log=(output/'native.log').read_text();summary={k:[int(n) for n in re.findall(pattern,log)] for k,pattern in [('total_nets',r'Total Nets:\s*(\d+)'),('extracted_nets',r'Nets extracted:\s*(\d+)'),('output_nets',r'Nets output:\s*(\d+)')]}
        count=sum(line.startswith('R') for line in model.open())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in generated},native_process_completed=True,initial_full_RC_mode=False,explicit_extresist_after_C_only=True,requested_net='PLLOUT',native_statistics=summary,emitted_R_card_count=count,exactly_one_requested_network_verified=False,primitive_and_C_contraction_verified=False,distributed_wire_R_qualified=False,native_simulation_allowed=False,release_ready=False));save(output/'status.json',dict(state='PLLOUT_resistance_pilot_complete_audit_pending',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','anchors','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','anchors','output']))
