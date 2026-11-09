"""One bounded full-layout R export diagnostic; coverage is audited separately."""
import json,os,time,re
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from extract_keeper_flat_geometry_C import FLAT

def verify(pins):
    for p,d in pins.items():
        if sha(p)!=d:raise ValueError('input/artifact changed: '+p)

def run():
    b=ROOT/'build';output=b/'signoff400/selected_keeper_contact_corrected_full_R_1599';output.mkdir(exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        engine=b/'tools/magic_port_location_candidate_1594';flat=b/'signoff400/selected_keeper_contact_corrected_C_1573'
        review=b/'signoff400/selected_magic_port_location_electrical_review_1598/assessment.json'
        receipts=[engine/'assessment.json',flat/'assessment.json',review]
        records=[json.loads(p.read_text()) for p in receipts]
        for r in records:verify(r.get('input_sha256',{}));verify(r.get('artifacts',{}))
        if not records[0].get('unset_port_location_initialized') or not records[2]['contact_electrical_equivalence_verified']:
            raise ValueError('same corrected candidate and completed contact controls required')
        if not all(r['contraction']['exact_device_and_C_contraction_verified'] for r in records[2]['resistance_results']):
            raise ValueError('both native fixture contractions required')
        binary=engine/'install/bin/magic';gds=flat/'flat.gds'
        rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        script=output/'extract.tcl'
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
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice {FLAT}.ext
extresist simplify off
extresist extout on
extresist silent off
extresist threshold 0
extresist all
ext2spice extresist on
ext2spice -o after.spice {FLAT}.ext
feedback save feedback.txt
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
        pins={str(p):sha(p) for p in [*receipts,binary,engine/'install/lib/magic/tcl/tclmagic.so',gds,TECH,rc,script,__file__]}
        save(output/'inputs.json',dict(input_sha256=pins,requested_scope='all native eligible networks; no include whitelist',threshold=0,resistor_simplification=False,memory_GiB=16,queue_cap_s=86400,native_cap_s=43200,maximum_native_cases=1,automatic_identical_retry=False,coverage_qualified=False,release_ready=False))
        os.environ.pop('OPENPLL_COUPLING_TRACE',None);os.sched_setaffinity(0,{29})
        save(output/'status.json',dict(state='waiting_for_resources',release_ready=False))
        with lease(1,16,time.clock_gettime(time.CLOCK_BOOTTIME)+86400):
            save(output/'status.json',dict(state='native_full_R_extraction_running',release_ready=False))
            execute([str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],output/'native.log',time.clock_gettime(time.CLOCK_BOOTTIME)+43200,16)
        verify(pins)
        paths=[output/n for n in ['before.spice','after.spice',FLAT+'.ext',FLAT+'.res.ext','native.log','feedback.txt']]
        if any(not p.exists() for p in paths):raise ValueError('complete native artifacts required')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in paths},native_process_completed=True,
             emitted_R_cards=sum(line.startswith('R') for line in (output/'after.spice').open()),
             exact_network_coverage_verified=False,primitive_C_contraction_verified=False,wire_R_geometry_qualified=False,native_simulation_allowed=False,release_ready=False))
        save(output/'status.json',dict(state='native_full_R_export_complete_audit_pending',release_ready=False))
    except Exception as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':run()
