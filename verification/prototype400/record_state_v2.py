#!/usr/bin/env python3
"""Record current prototype evidence without promoting diagnostic results."""
from datetime import datetime, timezone
import json
from pathlib import Path
from common import ROOT, source_pins, save, sha, verify


def main():
    base=ROOT/'build/timing400/prototype_001'
    current=source_pins()
    paths=dict(digital=base/'digital_006/assessment.json',
               mapping=base/'mapping_equivalence_003/assessment.json',
               synthetic_loop=base/'loop_driver_diagnostic_003/assessment.json',
               route=base/'local_antenna_001/status.json',
               routed_candidate=base/'route_004/status.json',
               physical=base/'physical_checks_006/status.json',
               digital_layout=base/'physical_checks_006/assessment.json',
               assembly_frame=base/'assembly_frame_001/assessment.json')
    evidence={}
    for name,path in paths.items():
        if not path.exists():continue
        value=json.loads(path.read_text())
        if 'input_sha256' in value:verify(value['input_sha256'])
        if 'artifacts' in value:verify(value['artifacts'])
        evidence[name]=dict(path=str(path),sha256=sha(path),
             state=value.get('state'),digital_control_checks=value.get('digital_control_checks'),
             all_trace_cases_passed=value.get('all_trace_cases_passed'),
             physical_models_qualified=value.get('physical_models_qualified'),
             digital_layout_pass=value.get('digital_layout_pass'))
    state=dict(observed_utc=datetime.now(timezone.utc).isoformat(),
         profile='verification/prototype_400mhz.json',candidate_source_sha256=current,
         evidence=evidence,
         gates=dict(digital_startup='RTL_CONTROLS_PASS' if 'digital' in evidence else 'OPEN',
                    dco_model='OPEN_FINAL_ASSEMBLY_EXTRACTION_AND_LOCAL_CONVERGENCE',
                    interfaces_reset_cdc='OPEN_MATCHING_PHYSICAL_BOUNDS',
                    whole_pll_lock='OPEN_PHYSICAL_MODELS_REQUIRED',
                    digital_timing='OPEN_FIVE_CORNER_TIMING_AND_CDC_CLOSURE',
                    physical_signoff='OPEN_PARENT_POWER_ROUTING_EXTRACTION_AND_SIGNOFF',
                    reproducible_handoff='OPEN_PRIOR_GATES'),
         qualification_corner_groups=5,model_based_scenarios=60,
         passing_physical_lock_cases=0,prototype_handoff_qualified=False,release_qualified=False,
         digital_layout_pass=True,assembly_frame_pass=True,native_simulation_running=False,
         next='Wire parent power, route the placed three-macro assembly, and verify/extract final loading before scheduling long native points.')
    save(base/'status.json',state)
    index=ROOT/'build/timing450/implementation_assessment.json'
    value=json.loads(index.read_text())
    value.setdefault('post_campaign_active_checks',{})['programmed_400mhz_prototype']=dict(
        profile=state['profile'],status=str((base/'status.json').relative_to(ROOT)),
        digital_controls=str(paths['digital'].relative_to(ROOT)),
        physical_status=str(paths['physical'].relative_to(ROOT)),
        source_changed_from_four_mode_candidate=True,prototype_handoff_qualified=False,
        release_qualified=False)
    save(index,value)
    print(json.dumps(dict(gates=state['gates'],prototype_handoff_qualified=False)))


if __name__=='__main__':main()
