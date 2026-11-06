"""Run independent digital-layout checks for the unselected enable proposal."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute


def run(route, proof, output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{28,29,30,31})
    os.environ.update(OMP_NUM_THREADS='4',OMP_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        receipt = route/'assessment.json'
        rr, pr = [json.loads(p.read_text()) for p in (receipt,proof)]
        for a in (rr,pr):
            verify(a['input_sha256'])
            verify(a['artifacts'])
        if not (rr['digital_routing_completed'] and rr['nominal_rc_extracted']
                and pr['all_transition_and_output_functions_equivalent']
                and pr['corrupted_reset_function_rejected']):
            raise ValueError('routed/extracted candidate with actual equivalence proof required')
        if pr['input_sha256'].get(str(receipt)) != sha(receipt):
            raise ValueError('proof must bind exact candidate route')
        if (route/'signoff').exists() or (route/'layout_audit_runner').exists():
            raise FileExistsError('independent layout evidence already exists; no overwrite')
        checker = ROOT/'verification/prototype400/check_layout.py'
        paths = [receipt,proof,checker,Path(__file__).resolve(),
            ROOT/'build/apptainer/openpll-release-modern.sif',
            *(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','compiled_charge_v2.py'))]
        pins = {str(p):sha(p) for p in paths}
        save(output/'inputs.json',dict(input_sha256=pins,route=str(route),CPU=[28,29,30,31],
             memory_GiB=8,wall_limit_s=43200,candidate_selected=False))
        save(output/'status.json',dict(state='candidate_digital_layout_checks_running',release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        with lease(4,8,deadline):
            execute(['/usr/bin/python3',checker,'--route',route],output/'checks.log',deadline,8)
        completion = route/'layout_audit_runner/completion.json'
        c = json.loads(completion.read_text())
        verify(c['input_sha256'])
        result_path = route/'signoff/assessment.json'
        result = json.loads(result_path.read_text())
        verify(result['sha256'])
        if c['audit_sha256'] != sha(result_path):
            raise ValueError('layout completion must bind exact independent result')
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,
            artifacts={str(p):sha(p) for p in (completion,result_path,output/'checks.log')},
            digital_component_results={k:result[k] for k in ('power_pins_total','power_pins_connected',
                'antenna_net_violations','antenna_pin_violations','magic_drc_rectangles','lvs_unique_match',
                'diagnostic_physical_pass')},
            candidate_layout_selected=False,assembled_parent_checked=False,
            physical_timing_qualified=False,physical_CDC_qualified=False,
            density_EM_IR_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='candidate_digital_layout_checks_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('route','proof','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    run(a.route.resolve(),a.proof.resolve(),a.output.resolve())
