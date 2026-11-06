"""Assess full-corner waveform identity and characterize its recorded supply power."""
import argparse,time
from pathlib import Path
from common_v3 import save,sha
from resources import lease
from follow_full_corner_calibration import run as waveform
from assess_native_supply_csv import run as power


def run(native,output):
    waveform(native,output)
    try:
        save(output/'status.json',dict(state='characterizing_recorded_supply_power',release_ready=False))
        with lease(1,1,time.clock_gettime(time.CLOCK_BOOTTIME)+300):power(native,output/'supply_power.json')
        paths=[Path(__file__).resolve(),Path(__file__).with_name('follow_full_corner_calibration.py'),Path(__file__).with_name('assess_native_supply_csv.py'),output/'provenance.json']
        save(output/'complete.json',dict(input_sha256={str(p):sha(p)for p in paths},artifacts={str(p):sha(p)for p in(output/'assessment.json',output/'supply_power.json')},
            full_native_static_preset_startup_supply_power_characterized=True,locked_loop_power_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='calibration_waveform_and_supply_power_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),native_jobs_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('native','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.native.resolve(),a.output.resolve())
