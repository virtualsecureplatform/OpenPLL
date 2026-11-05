#!/usr/bin/env python3
"""Record checked parent geometry without closing electrical/timing gates."""
from datetime import datetime,timezone
import json
from common import ROOT,save,sha,verify
from status_store import update_root


def main():
    base=ROOT/'build/timing400/prototype_001';closure=base/'filled_closure_005'
    receipt=json.loads((closure/'assessment.json').read_text());verify(receipt['input_sha256'])
    assert receipt['filled_geometry_checks_pass']
    layout=json.loads((closure/'layout/assessment.json').read_text());verify(layout['input_sha256']);verify(layout['artifacts'])
    geometry=json.loads((closure/'geometry/assessment.json').read_text());verify(geometry['input_sha256']);verify(geometry['artifacts'])
    topology=json.loads((closure/'topology/assessment.json').read_text());verify(topology['input_sha256']);verify(topology['artifacts'])
    density=json.loads((closure/'density_audit/assessment.json').read_text());verify(density['input_sha256'])
    assert density['stock_density_checks_passed'] and topology['complete_port_connectivity_screen_passed']
    value=dict(observed_utc=datetime.now(timezone.utc).isoformat(),assessment=str(closure/'assessment.json'),
         assessment_sha256=sha(closure/'assessment.json'),gds=str((closure/'layout/assembly.gds').resolve()),
         gds_sha256=sha(closure/'layout/assembly.gds'),magic_drc_rectangles=0,lvs_unique_match=True,
         forming_antenna_violations=0,native_antenna_feedback=0,density_checks=density['constrained_density_checks'],density_failures=0,
         physical_port_probes=topology['rectangular_macro_port_probes'],missing_or_split_or_shorted_ports=0,
         geometry_checks_pass=True,power_integrity_qualified=False,physical_timing_qualified=False,
         physical_lock_qualified=False,prototype_handoff_qualified=False)
    update_root('filled_geometry',value)
    state=json.loads((base/'status.json').read_text());gates=state['gates']
    gates['physical_signoff']='GEOMETRY_PASS_OPEN_POWER_INTEGRITY_AND_ELECTRICAL_INTEGRATION'
    gates['dco_model']='OPEN_FILL_AWARE_DOMAIN_RECONCILIATION_AND_NUMERICAL_CONTROLS'
    update_root('gates',gates)
    index=ROOT/'build/timing450/implementation_assessment.json';data=json.loads(index.read_text())
    current=data.setdefault('post_campaign_active_checks',{}).setdefault('programmed_400mhz_prototype',{})
    current.update(final_parent_geometry=str((closure/'assessment.json').relative_to(ROOT)),
         final_parent_geometry_checks_pass=True,active_loading_status=str((base/'filled_loading_006/status.json').relative_to(ROOT)),
         active_domain_status=str((base/'filled_domain_004/status.json').relative_to(ROOT)),
         prototype_handoff_qualified=False,release_qualified=False)
    save(index,data)
    print(json.dumps(value))


if __name__=='__main__':main()
