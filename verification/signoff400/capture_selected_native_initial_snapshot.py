"""Cache the complete finite initial native voltage vector for conditional cuts.

The entire source RAW is hashed once, with file identity checked across the
initial-vector read and full checksum. Later cuts bind to this small artifact.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from run_selected_detector_phase_probe import first_sample


def fingerprint(path):
    s=path.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def run(reference_probe,native,output):
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='capturing_full_initial_voltage_snapshot',release_ready=False))
    try:
        if json.loads((reference_probe/'status.json').read_text())['state']!='conditional_detector_probe_completed_assessment_pending':raise ValueError('normally completed reference probe required')
        rm=reference_probe/'manifest.json';ra=reference_probe/'assessment.json'
        m=json.loads(rm.read_text());a=json.loads(ra.read_text())
        if not a.get('native_exit_zero') or a['input_sha256']!=m['input_sha256']:raise ValueError('reference completion provenance mismatch')
        raw=native/'profile.raw';expected=m['input_sha256'].get(str(raw))
        if not expected:raise ValueError('verified source RAW identity missing')
        pins={str(p):sha(p) for p in [rm,ra,native/'manifest.json',Path(__file__).resolve(),Path(__file__).with_name('run_selected_detector_phase_probe.py')]}
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        with lease(1,2,deadline):
            before=fingerprint(raw);names,values=first_sample(raw);digest=sha(raw)
            if digest!=expected or fingerprint(raw)!=before:raise ValueError('source RAW changed during snapshot capture')
        verify(pins);pins[str(raw)]=digest
        snapshot=output/'initial_voltage_vector.json';save(snapshot,dict(variable_names=names,values=values,time_s=0))
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(snapshot):sha(snapshot)},
            vectors=len(names),all_initial_values_finite=True,source_file_fingerprint=before,
            snapshot_boundary_conditions_qualified=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='full_initial_voltage_snapshot_captured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference-probe','native','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{30});run(a.reference_probe.resolve(),a.native.resolve(),a.output.resolve())
