"""Exercise the future sequential adapter inside the pinned native image."""
import argparse,json,time
from pathlib import Path
from common import save,sha
from compiled_charge import execute
from resources import lease
from test_compiled_propagation_assessor import equal


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400';controls=base/'compiled_sequential_assessor_controls_001';proof=controls/'assessment.json';a=json.loads(proof.read_text());source=root/'build/timing400/release_001/compact_sequential_15PVT_completion_001/tt_p27';plan=source/'plan.json';prior=source/'run_001/assessment.json';wave=source/'run_001/batch.prn'
    image=root/'build/apptainer/openpll-release-modern.sif';adapter=root/'verification/timing400/assess_compact_sequential_compiled.py';worker=root/'verification/timing400/run_sequential_PVT_case_compiled.py'
    paths=[proof,controls/'assess_sequential_waveform',plan,prior,wave,image,adapter,worker,Path(__file__).resolve()];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(1,4,deadline):
        pins={str(p):sha(p) for p in paths}
        if pins[str(controls/'assess_sequential_waveform')]!=a['artifacts'][str(controls/'assess_sequential_waveform')]:raise ValueError('compiled sequential control binary changed')
        native=out/'native';native.mkdir();(native/'batch.prn').symlink_to(wave)
        checker=out/'check_adapter.py';checker.write_text("""import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'verification/timing400'))
from assess_compact_sequential_compiled import assess
out=Path(sys.argv[1]);source=Path(sys.argv[2]);controls=Path(sys.argv[3])
plan=json.loads((source/'plan.json').read_text());prior=json.loads((source/'run_001/assessment.json').read_text())
assess(plan,dict(prior['input_sha256']),out/'native',time.clock_gettime(time.CLOCK_BOOTTIME)+1800,controls)
""")
        execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',checker,out,source,controls],out/'check_adapter.log',deadline,4)
        found=json.loads((native/'assessment.json').read_text());before=json.loads(prior.read_text())
        for key in ('fixtures','passing','records','pvt','all_native_waveform_events_terminal'):equal(before[key],found[key],key)
        if not found['compiled_streaming_sequential_assessor_used']:raise ValueError('compiled sequential adapter not exercised')
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('adapter source changed during control')
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(checker):sha(checker),str(native/'assessment.json'):sha(native/'assessment.json')},compiled_sequential_adapter_matches_retained_108_fixture_TT_records=True,adapter_exercised_inside_pinned_native_image=True,native_simulations_started=0,future_native_worker_execution_validated=False,setup_hold_recovery_removal_qualified=False,physical_timing_qualified=False,release_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
