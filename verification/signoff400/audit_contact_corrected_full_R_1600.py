"""Completed-only full-R conservation audit; does not qualify skipped-net coverage."""
import json,os,time,sys,re
from runtime_common import ROOT,save,sha
from resources import identity,lease
from compiled_charge_v2 import execute
from compare_native_R_with_aliases import compare_with_aliases

BASE=ROOT/'build/signoff400'
SOURCE=BASE/'selected_keeper_contact_corrected_full_R_1599'
OUTPUT=BASE/'selected_keeper_contact_corrected_full_R_audit_1600'

def assess():
    receipt=SOURCE/'assessment.json';record=json.loads(receipt.read_text())
    if not record['native_process_completed']:raise ValueError('normal native completion required')
    flat=BASE/'selected_keeper_contact_corrected_C_1573';fr=flat/'assessment.json';f=json.loads(fr.read_text())
    for value in [record,f]:
        for p,d in value['artifacts'].items():
            if sha(p)!=d:raise ValueError('completed native artifact changed: '+p)
    first=compare_with_aliases((flat/'capacitance.spice').read_text(),(SOURCE/'before.spice').read_text())
    second=compare_with_aliases((SOURCE/'before.spice').read_text(),(SOURCE/'after.spice').read_text())
    log=(SOURCE/'native.log').read_text()
    counts={name:re.findall(pattern,log) for name,pattern in [('total_nets',r'Total Nets:\s*(\d+)'),('extracted_nets',r'Nets extracted:\s*(\d+)'),('output_nets',r'Nets output:\s*(\d+)')]}
    save(OUTPUT/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [receipt,fr,__file__,ROOT/'verification/signoff400/compare_native_R_with_aliases.py',ROOT/'verification/signoff400/audit_keeper_native_R_contraction.py']},
         corrected_C_baseline_comparison=first,ideal_R_contraction=second,native_summary=counts,
         baseline_C_equivalence_verified=first['exact_device_and_C_contraction_verified'],
         full_export_C_contraction_verified=second['exact_device_and_C_contraction_verified'],
         exact_requested_network_coverage_verified=False,wire_R_geometry_qualified=False,native_simulation_allowed=False,release_ready=False))

def run():
    OUTPUT.mkdir(exist_ok=False);save(OUTPUT/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    owner=json.loads((SOURCE/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((SOURCE/'status.json').read_text())['state']
            if state=='native_full_R_export_complete_audit_pending' and (SOURCE/'assessment.json').exists():break
            if state=='stopped_without_qualification':raise RuntimeError('full-R producer failed')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('full-R owner missing without completed receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('full-R observation deadline')
            save(OUTPUT/'status.json',dict(state='waiting_for_completed_full_R_export',release_ready=False));time.sleep(10)
        with lease(1,16,time.clock_gettime(time.CLOCK_BOOTTIME)+86400):
            save(OUTPUT/'status.json',dict(state='auditing_completed_native_exports',release_ready=False))
            execute(['/usr/bin/python3',__file__,'--assess'],OUTPUT/'audit.log',time.clock_gettime(time.CLOCK_BOOTTIME)+7200,16)
        save(OUTPUT/'status.json',dict(state='full_R_conservation_assessed_coverage_pending',release_ready=False))
    except Exception as error:
        save(OUTPUT/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    if sys.argv[1:]==['--assess']:assess()
    elif not sys.argv[1:]:run()
    else:raise ValueError('unsupported audit arguments')
