"""Queue one extended diagnostic after the short streaming comparison completes.

No automatic retry; completion never qualifies the analog model or release.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from run_selected_streaming_control_v2 import run
from compare_selected_streaming_v2 import follow


def queue(config_path,output):
    config=json.loads(config_path.read_text())
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    short=Path(config['short_comparison']);owner=json.loads((short/'owner.json').read_text())
    paths=[config_path,Path(__file__).resolve(),Path(__file__).with_name('run_selected_streaming_control_v2.py'),
           Path(__file__).with_name('compare_selected_streaming_v2.py'),Path(config['binary'])]
    pins={str(p):sha(p) for p in paths}
    save(output/'inputs.json',dict(input_sha256=pins,short_owner=owner,diagnostic=True,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7500
    try:
        while True:
            status=json.loads((short/'status.json').read_text())
            if status['state']=='streaming_comparison_complete':break
            if status['state']=='stopped_without_qualification':raise RuntimeError('short native streaming control or comparison failed')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('short comparison owner exited without completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('short comparison wait exhausted')
            save(output/'status.json',dict(state='waiting_for_21ns_comparison',release_ready=False));time.sleep(10)
        verify(pins)
        save(output/'status.json',dict(state='extended_streaming_diagnostic_running',release_ready=False))
        run(*(Path(config[name]) for name in ['bench','replay','binary','reference','native_output']),
            config['stop_ns'],short/'assessment.json')
        verify(pins)
        follow(Path(config['native_output']),Path(config['reference']),Path(config['assessment_output']),config['stop_ns']*1e-9)
        verify(pins)
        save(output/'status.json',dict(state='extended_streaming_diagnostic_assessed',physical_models_qualified=False,release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();queue(a.config.resolve(),a.output.resolve())
