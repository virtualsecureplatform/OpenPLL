"""Extract an independent flat-geometry capacitance reference from checked GDS."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from runtime_common import ROOT
MAGIC=ROOT/"build/tools/magic_contact_residue_candidate_1570/install/bin/magic"
TOP='IntegerPLL_400MHz_PrototypeTop'
FLAT='IntegerPLL_400MHz_KeeperFlatC'


def run(layout,output):
    engine=ROOT/"build/tools/magic_contact_residue_candidate_1570/assessment.json"
    controls=ROOT/"build/signoff400/selected_magic_contact_candidate_review_1572/assessment.json"
    er,cr=[json.loads(q.read_text()) for q in [engine,controls]]
    verify(er["artifacts"])
    if not er.get("contact_residue_candidate") or not cr.get("all_four_native_integral_audits_pass") or not cr.get("noncontact_SPICE_unchanged"):
        raise ValueError("corrected candidate and completed native integral controls required")
    os.environ.pop("OPENPLL_COUPLING_TRACE",None)
    receipt=layout/'assessment.json';proof=layout/'lvs_proof/assessment.json';r,p=[json.loads(x.read_text())for x in [receipt,proof]]
    for a in [r,p]:verify(a['input_sha256']);verify(a['artifacts'])
    if not all(r[k]for k in ['assembled_drc_pass','assembled_lvs_pass','all_three_macros_expanded'])or p['input_sha256'].get(str(receipt))!=sha(receipt):raise ValueError('same expanded checked parent required')
    gds=layout/'assembly.gds'
    if r['artifacts'].get(str(gds))!=sha(gds):raise ValueError('checked GDS differs')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=16,automatic_identical_retry=False))
    rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
    flat_gds=output/'flat.gds';model=output/'capacitance.spice';script=output/'extract.tcl'
    script.write_text(f'cd {{{output}}}\ngds read {{{gds}}}\nload {TOP} -dereference\nflatten {FLAT}\nload {FLAT}\ngds write {{{flat_gds}}}\nextract do local\nextract do capacitance\nextract do coupling\nextract no resistance\nextract all\next2spice lvs\next2spice hierarchy off\next2spice subcircuit top on\next2spice short resistor\next2spice cthresh -1e100\next2spice -o {{{model}}} {FLAT}.ext\nquit -noprompt\n')
    files=[engine,controls,receipt,proof,gds,rc,script,MAGIC,TECH,Path(__file__).resolve(),Path(__file__).with_name('replay_keeper_flat_signed_C.py')];pins={str(x):sha(x)for x in files};save(output/'inputs.json',dict(input_sha256=pins,scope='contact-residue corrected full geometry C extraction; no R extraction',contact_residue_candidate=True,diagnostic_trace_disabled=True,signed_export_threshold_fF='-1e100'))
    try:
        save(output/'status.json',dict(state='flat_geometry_C_waiting_for_resources',release_ready=False))
        with lease(1,16,deadline):
            save(output/'status.json',dict(state='flat_geometry_C_extraction_running',release_ready=False));execute([MAGIC,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],output/'native.log',deadline,16)
        verify(pins);artifacts=[model,flat_gds,output/(FLAT+'.ext'),output/'native.log']
        if any(not x.exists()or x.stat().st_size==0 for x in artifacts):raise ValueError('complete flat extraction artifacts missing')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(x):sha(x)for x in artifacts},flat_geometry_capacitance_extracted=True,contact_residue_candidate=True,diagnostic_trace_disabled=True,source_GDS_sha256=sha(gds),native_source_masks_verified=False,primitive_inventory_verified=False,coefficient_equivalence_qualified=False,passivity_qualified=False,native_simulation_allowed=False,release_ready=False));save(output/'status.json',dict(state='flat_geometry_C_extracted_independent_checks_pending',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--layout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.layout.resolve(),a.output.resolve())
