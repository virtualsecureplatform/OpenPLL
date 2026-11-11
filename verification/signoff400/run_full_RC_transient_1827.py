"""One full distributed RC startup transient, admitted by completed DC review."""
import json, os, time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from contact_corrected_transient_deck import transient_deck
from read_selected_standard import read_selected_standard


def run():
    base = ROOT / 'build/signoff400'
    review = base / 'selected_completed_RC_review_1826/assessment.json'
    rr = json.loads(review.read_text()); verify(rr['input_sha256'])
    if not rr['full_physical_RC_export_verified'] or not rr['completed_full_RC_reset_DC_verified']:
        raise ValueError('completed full physical export and reset DC required')
    source = base / 'selected_seeded_full_RC_DC_1825'
    receipt = source / 'assessment.json'
    record = json.loads(receipt.read_text())
    verify(record['input_sha256']); verify(record['artifacts'])
    process = json.loads((source / 'native.process.json').read_text())
    if identity(process['pid']) == process['birth'] or not record['normal_native_exit']:
        raise ValueError('completed DC worker required')
    binary = ROOT / 'build/tools/xyce_metis_ordering_1790/Xyce'
    if record['input_sha256'][str(binary)] != sha(binary):
        raise ValueError('same admitted backend required')
    out = base / 'selected_full_RC_transient_1827'; out.mkdir(exist_ok=False)
    capture = out / 'transient.prn'; deck = out / 'transient.spice'
    original = (source / 'smoke.spice').read_text()
    text, _ = transient_deck(original, capture, 112, 20, 10)
    roots = [line.split() for line in original.splitlines() if line.startswith('XDUT ')]
    if len(roots) != 1: raise ValueError('one full macro required')
    ports = roots[0][1:-1]
    if len(ports) != 65 or len(set(ports)) != 65: raise ValueError('all formal ports required')
    old = '.print tran format=std precision=17 file=' + str(capture) + ' V(*)'
    if text.splitlines().count(old) != 1: raise ValueError('unique print required')
    text = text.replace(old, '.print tran format=std precision=17 file=' + str(capture) + ' ' + ' '.join('v('+p+')' for p in ports))
    deck.write_text(text)
    folder = Path(__file__).resolve().parent
    dependencies = [review, receipt, deck, Path(__file__).resolve(), folder/'contact_corrected_transient_deck.py', folder/'run_keeper_native_BSIM_coarse_band.py', folder/'run_keeper_flat_native_independent.py', folder/'reset_contract_v4.py', folder/'read_selected_standard.py', folder/'compiled_charge_v2.py']
    pins = {**record['input_sha256'], **{str(p):sha(p) for p in dependencies}}
    verify(pins)
    os.sched_setaffinity(0, {20})
    os.environ.update(OMP_NUM_THREADS='1', OMP_THREAD_LIMIT='1', OPENBLAS_NUM_THREADS='1')
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 86400
    save(out/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid()), deadline_uptime=deadline))
    save(out/'inputs.json', dict(input_sha256=pins, native_cap_s=86400, memory_GiB=64, CPU=20,
         max_native_cases=1, automatic_identical_retry=False, formal_ports=ports,
         reset_release_ns=80, end_ns=340, max_step_ps=10, coarse=20, fine=112,
         distributed_wire_R_included=True, all_internal_voltages_requested=False,
         transient_correlation_qualified=False, release_ready=False))
    try:
        save(out/'status.json', dict(state='waiting_for_global_CPU_RAM_budget', release_ready=False))
        start=time.monotonic()
        with lease(1,64,deadline):
            save(out/'status.json', dict(state='full_RC_startup_transient_running', release_ready=False))
            execute([binary,'-a','-linsolv','umfpack_reuse',deck], out/'native.log', deadline,64)
        verify(pins)
        rows=read_selected_standard(capture,{p:p for p in ports},340e-9)
        save(out/'assessment.json',dict(input_sha256=pins,
             artifacts={str(p):sha(p) for p in [deck,capture,out/'native.log']},
             normal_native_completion=True, all_65_formal_ports_finite=True,
             samples=len(rows), elapsed_s=time.monotonic()-start,
             distributed_wire_R_included=True, transient_correlation_qualified=False,
             model_qualified=False, release_ready=False))
        save(out/'status.json',dict(state='full_RC_startup_transient_complete',release_ready=False))
    except BaseException as error:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__ == '__main__': run()
