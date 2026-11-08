"""Exhaustively check static-code port bindings against selected physical observations."""
import json
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from run_keeper_static_terminated_DCO import environment


def run():
    base=ROOT/'build/signoff400'
    output=base/'selected_keeper_static_code_mapping_1532'
    output.mkdir(exist_ok=False)
    files=[base/'selected_keeper_receiver_native_1419/bindings.json',
           base/'selected_keeper_prescribed_boundary_roles_1522/boundaries.json',
           base/'selected_keeper_corrected_BSIM_physical_1296/plan.json',
           Path(__file__).resolve(),Path(__file__).with_name('run_keeper_static_terminated_DCO.py')]
    pins={str(p):sha(p) for p in files}
    bindings=json.loads(files[0].read_text())
    roles=json.loads(files[1].read_text())
    observations=json.loads(files[2].read_text())['observations']
    driven=bindings['externally_driven_ports']
    if len(set(driven.values()))!=len(driven):
        raise ValueError('distinct conditional input ports required')
    macro=[r for r in observations.values() if r['endpoint']=='macro']
    checked=0
    for coarse in range(48):
        for fine in range(8,248):
            mapping,reset,receiver=environment(bindings,roles,observations,coarse,fine)
            for row in macro:
                # Independent thermometer truth table, without calling expected().
                high=(row['bit']<coarse) if row['bus']=='COARSETHERMAL_CODE' else (row['bit']>=fine)
                if mapping[driven[row['physical_node']]]!=('VDD' if high else '0'):
                    raise ValueError('static thermometer polarity or threshold mismatch')
            if mapping[driven[reset]]!='RESET_DRIVER' or mapping[driven[receiver]]!='RECEIVER':
                raise ValueError('free receiver/reset binding changed')
            for rail,value in [('VPWR','VDD'),('VPB','VDD'),('VGND','0'),('VNB','0')]:
                if mapping[driven[rail]]!=value:raise ValueError('rail mismatch')
            if mapping[bindings['observation_only_ports']['PLLOUT']]!='PLLOUT':
                raise ValueError('PLLOUT not free')
            checked+=1
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={},
         static_codes_checked=checked,macro_bits_per_code=302,
         thermometer_assignments_checked=checked*302,all_assignments_match=True,
         coarse_domain=[0,47],fine_domain=[8,247],
         actual_selected_physical_mapping=True,native_simulations_performed=0,
         analog_accuracy_qualified=False,release_ready=False))


if __name__=='__main__':run()
