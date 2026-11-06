"""Capture sender packets from existing full-corner runs; launch no simulations."""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity


def run(ff_pipeline, remaining_pipeline, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {30})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    folder = Path(__file__).resolve().parent
    capture = folder / 'capture_selected_full_native_snapshot.py'
    export = folder / 'capture_selected_clock_driver_waveforms.py'
    image = ROOT / 'build/apptainer/openpll-release-modern.sif'
    drivers = ROOT / 'build/signoff400/selected_interface_clock_reset_inventory_276.json'
    inventory = ROOT / 'build/signoff400/selected_detector_boundary_inventory_181.json'
    sources = [Path(__file__).resolve(), capture, export, image, drivers, inventory,
               folder / 'capture_selected_native_initial_snapshot.py',
               folder / 'run_selected_detector_phase_probe.py',
               folder / 'selected_spice_device_conditions.py',
               folder / 'selected_matching_corner_sender.py',
               ROOT / 'tools/xyce_waveform/extract_boundary_pwl.cpp']
    owners = {}
    for parent in [ff_pipeline, remaining_pipeline]:
        owner = parent / 'owner.json'; sources.append(owner)
        owners[str(parent)] = json.loads(owner.read_text())
    pins = {str(p):sha(p) for p in sources}
    records = []
    save(output / 'inputs.json', dict(input_sha256=pins, original_owners=owners,
        native_simulations_launched=0, automatic_identical_retry=False,
        sender_packets_do_not_qualify_conditional_detector=True, release_ready=False))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 12 * 86400
    try:
        cases = [('ff',ff_pipeline,ff_pipeline)] + [
            (corner,remaining_pipeline / corner,remaining_pipeline) for corner in ['ss','sf','fs']]
        for corner, case, parent in cases:
            assessment = case / 'waveform_assessment'
            while True:
                state_path = assessment / 'status.json'
                state = json.loads(state_path.read_text()).get('state') if state_path.exists() else None
                if state in ['calibration_waveform_assessed','calibration_waveform_and_supply_power_assessed']:
                    if not (assessment / 'provenance.json').exists():
                        raise ValueError('terminal assessment missing provenance')
                    break
                pstate = json.loads((parent / 'status.json').read_text()).get('state')
                owner = owners[str(parent)]
                if state == 'stopped_without_qualification' or pstate == 'stopped_without_qualification':
                    raise RuntimeError('original full-corner pipeline stopped: ' + corner)
                if identity(owner['pid']) != owner['birth']:
                    raise RuntimeError('original pipeline owner exited before corner assessment: ' + corner)
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                    raise TimeoutError('sender observation deadline; original jobs unchanged')
                save(output / 'status.json',dict(state='waiting_for_original_full_corner_assessment',corner=corner,release_ready=False))
                time.sleep(10)
            verify(pins)
            destination = output / corner; destination.mkdir()
            native = case / 'native'
            for stage, script, arguments in [
                ('snapshot', capture, ['--native',native,'--assessment',assessment,'--output',destination / 'snapshot']),
                ('waveforms', export, ['--drivers',drivers,'--inventory',inventory,'--native',native,
                    '--snapshot-receipt',destination / 'snapshot/assessment.json','--output',destination / 'waveforms'])]:
                save(output / 'status.json',dict(state='capturing_full_corner_sender_packet',corner=corner,stage=stage,release_ready=False))
                command = ['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'python3',script,*arguments]
                with (destination / (stage + '.log')).open('x') as log:
                    subprocess.run(list(map(str,command)),check=True,stdout=log,stderr=subprocess.STDOUT,timeout=2100)
                verify(pins)
            # Independently check same-source and requested-corner binding before publishing.
            from selected_matching_corner_sender import validate
            op, bindings = validate(native,destination / 'snapshot',destination / 'waveforms',corner)
            records.append(dict(corner=corner,source_native=str(native),operating_point=op,artifacts=bindings))
            save(output / 'completed_packets.json', records)
        verify(pins)
        save(output / 'assessment.json',dict(input_sha256=pins,packets=records,native_simulations_launched=0,
            conditional_detector_qualified=False,release_ready=False))
        save(output / 'status.json',dict(state='four_corner_sender_packets_captured',release_ready=False))
    except BaseException as error:
        save(output / 'status.json',dict(state='stopped_without_qualification',reason=repr(error),original_native_jobs_unchanged=True,release_ready=False))
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    for name in ['ff-pipeline','remaining-pipeline','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.ff_pipeline.resolve(),a.remaining_pipeline.resolve(),a.output.resolve())
