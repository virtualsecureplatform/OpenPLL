"""Prepare a separate three-macro assembly frame for the enable proposal.

The actual digital GDS is covered by an independently checked obstruction LEF.
This does not promote the proposal or transfer old assembled-model evidence.
Run inside the release image.
"""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute

KPY = Path('/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3')


def run(route, proof, candidate, dco, layout_check, output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{28,29,30,31})
    os.environ.update(OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        folder = Path(__file__).resolve().parent
        abstract_tool = folder/'extend_prototype_macro_obstructions.py'
        frame_tool = folder/'build_prototype_candidate_parent_frame_v4.py'
        checked = json.loads(layout_check.read_text())
        verify(checked['input_sha256'])
        verify(checked['artifacts'])
        if checked['digital_component_results']['diagnostic_physical_pass'] is not True:
            raise ValueError('independent digital component physical checks must pass')
        if checked['input_sha256'].get(str(route/'assessment.json')) != sha(route/'assessment.json'):
            raise ValueError('physical checks must bind exact repaired candidate route')
        paths = [Path(__file__).resolve(),abstract_tool,frame_tool,KPY,layout_check,
            route/'assessment.json',proof/'assessment.json',candidate/'assessment.json',dco/'assessment.json',
            ROOT/'build/apptainer/openpll-release-modern.sif',
            *(folder/n for n in ('common_v3.py','resources.py','compiled_charge_v2.py'))]
        pins = {str(p):sha(p) for p in paths}
        save(output/'inputs.json',dict(input_sha256=pins,route=str(route),candidate=str(candidate),
            dco=str(dco),CPU=[28,29,30,31],whole_check_limit_s=1800,candidate_selected=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        save(output/'status.json',dict(state='covering_actual_digital_GDS_obstructions',release_ready=False))
        abstract = output/'obstructions'
        with lease(1,4,deadline):
            execute([KPY,abstract_tool,'--route',route,'--output',abstract],output/'obstructions.log',deadline,4)
        ar = json.loads((abstract/'assessment.json').read_text())
        verify(ar['input_sha256'])
        verify(ar['artifacts'])
        verify(pins)
        frame = output/'frame'
        save(output/'status.json',dict(state='building_separate_three_macro_frame',release_ready=False))
        # The frame worker takes its own four-core/eight-GiB lease.
        execute(['/usr/bin/python3',frame_tool,'--digital-route',route,'--digital-checks',proof,
            '--candidate',candidate,'--dco-candidate',dco,'--digital-abstract',abstract,'--output',frame],
            output/'frame.log',deadline,8)
        fr = json.loads((frame/'assessment.json').read_text())
        verify(fr['input_sha256'])
        verify(fr['artifacts'])
        if fr['assembly_frame_pass'] is not True:
            raise ValueError('exact three-macro frame audit required')
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,
            artifacts={str(p):sha(p) for p in (abstract/'assessment.json',frame/'assessment.json')},
            candidate_source_sha256=fr['candidate_source_sha256'],
            original_digital_geometry_and_pins_preserved=True,
            actual_routing_and_cut_GDS_obstruction_coverage_verified=True,
            assembly_frame_pass=True, parent_power_and_routing_completed=False,
            assembled_GDS_DRC_LVS_passed=False, candidate_selected=False,
            physical_timing_CDC_qualified=False,old_native_model_evidence_transferred=False,release_ready=False))
        save(output/'status.json',dict(state='separate_enable_candidate_frame_prepared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('route','proof','candidate','dco','layout-check','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    run(a.route.resolve(),a.proof.resolve(),a.candidate.resolve(),a.dco.resolve(),a.layout_check.resolve(),a.output.resolve())
