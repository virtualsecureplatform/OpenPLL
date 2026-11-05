#!/usr/bin/env python3
"""Record terminal antenna repair evidence and live qualification state."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'build/timing400/release_001'
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):
    text=json.dumps(value,indent=2)+'\n';tmp=p.with_suffix('.json.tmp');tmp.write_text(text);tmp.replace(p)


def main():
    evidence=['qualification_progress_030.json','parent_dco_antenna_physical_failure_006/assessment.json',
        'parent_dco_antenna_port_topology_004/assessment.json','parent_dco_antenna_port_topology_006/assessment.json',
        'parent_dco_antenna_targeted_007/superseded.json','parent_dco_antenna_targeted_008/assessment.json',
        'parent_dco_antenna_layout_audit_008/assessment.json','parent_dco_antenna_geometry_008/antenna/assessment.json',
        'parent_dco_antenna_localization_008/assessment.json','parent_dco_antenna_targeted_009/native_completion.json',
        'parent_dco_antenna_targeted_010/native_completion.json','parent_dco_antenna_targeted_011/assessment.json',
        'parent_dco_antenna_stream_011/assessment.json','parent_dco_antenna_layout_audit_011/assessment.json',
        'parent_dco_antenna_geometry_011/native_completion.json','parent_dco_antenna_geometry_011/topology/assessment.json',
        'parent_dco_antenna_geometry_011/antenna/assessment.json','parent_dco_antenna_single_net_repair_audit_011/assessment.json']
    paths=[BASE/n for n in evidence]+[Path(__file__).resolve(),ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    a=read(BASE/'parent_dco_antenna_layout_audit_011/assessment.json');assert a['assembled_magic_drc_passed'] and a['assembled_lvs_passed']
    g=read(BASE/'parent_dco_antenna_geometry_011/antenna/assessment.json');assert g['violations']==0 and len(g['formation_coverage'])==13
    layer=read(BASE/'parent_dco_antenna_single_net_repair_audit_011/assessment.json')
    analog=[]
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc/'comm').read_text().strip()!='Xyce':continue
            state=(proc/'stat').read_text().rsplit(')',1)[1].split()[0]
            if state=='Z':continue
            analog.append(dict(pid=int(proc.name),argv=[s.decode() for s in (proc/'cmdline').read_bytes().split(b'\0') if s]))
        except (FileNotFoundError,ProcessLookupError):continue
    assert len(analog)<=4
    now=datetime.now(timezone.utc).isoformat()
    candidate=dict(route=str((BASE/'parent_dco_antenna_targeted_011').relative_to(ROOT)),
        stream=str((BASE/'parent_dco_antenna_stream_011').relative_to(ROOT)),full_magic_drc_rectangles=0,assembled_lvs_passed=True,
        top_pins=55,parent_diodes=564,parent_well_taps=141,independent_antenna_violations=0,formation_stages_checked=13,
        independent_macro_port_probes=743,physical_shorts=0,missing_probes=0,split_logical_nets=0,
        filled=False,native_antenna_pending_for_final_filled_candidate=True,rc_qualified=False,release_qualified=False,adopted=False)
    fill=BASE/'parent_dco_antenna_fill_011'
    filling=dict(directory=str(fill.relative_to(ROOT)),owner=read(fill/'owner.json'),status_at_observation=read(fill/'status.json'))
    progress=dict(observed_utc=now,classification='progress_not_release',evidence_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        candidate006_failure=dict(full_magic_drc_rectangles=8,assembled_lvs_passed=False,signal_short_groups=[['DCO_THERM[77]','DCO_THERM[53]','DCO_THERM[101]'],['DCO_THERM[11]','DCO_THERM[21]']],antenna_zero_ineligible=True),
        route007_superseded_partial=True,route009_010_layer_access_preflight_nonpasses=True,
        intermediate008=dict(full_magic_drc_rectangles=0,assembled_lvs_passed=True,antenna_violations=1,antenna_net='DCO_THERM[53]',antenna_stage='m3'),
        latest_candidate=candidate,single_net_repair=dict(net='DCO_THERM[53]',m3_before_um=532.38,m3_after_um=384.54,
            m3_reduction_um=layer['m3_wire_length_reduction_um'],unchanged_background_routes=356,all_placements_and_bindings_preserved=True),
        fill_generation=filling,native_analog_jobs=sorted(analog,key=lambda r:r['pid']),native_analog_count=len(analog),
        original_deadlines_retained=True,native_analog_jobs_restarted=0,required_nominal_15pvt_scope_unchanged=True,
        calibration_and_dynamic_models_qualified=False,physical_whole_pll_passes=0,release_qualified=False,adopted=False,
        next_actions=['Merge freshly generated fill and replace insufficient stock M5 fill with the preserved denser pattern',
            'Check final filled GDS with full DRC/LVS, density, independent topology/forming antenna and native MOS-only antenna',
            'Regenerate matching fill-aware parasitics and repaired macro interface models',
            'Collect TT100 endpoints and assess both corrected160ns probes under existing absolute cutoffs',
            'Continue qualified nominal15PVT timing, calibration, interface and fullPLL gates'])
    snapshot=BASE/'qualification_progress_031.json';assert not snapshot.exists();write(snapshot,progress)
    overview=ROOT/'build/timing450/implementation_assessment.json';data=read(overview)
    data['latest_400mhz_qualification_progress']=str(snapshot.relative_to(ROOT))
    data['active_400mhz_parent_dco_antenna_route'].update(observed_utc=now,latest_candidate=candidate,
        last_full_drc_lvs_passing_candidate=str((BASE/'parent_dco_antenna_layout_audit_011/assessment.json').relative_to(ROOT)),
        physical_checks=dict(terminal_full_drc_lvs_pass=True,independent_antenna_violations=0,fill_generation=filling),release_qualified=False)
    data['active_400mhz_parent_antenna_review'].update(observed_utc=now,latest_candidate=candidate,
        latest_conservative_geometry=str((BASE/'parent_dco_antenna_geometry_011/antenna/assessment.json').relative_to(ROOT)),
        failed_candidate006_retained=str((BASE/'parent_dco_antenna_physical_failure_006/assessment.json').relative_to(ROOT)),
        antenna_qualified=False,release_qualified=False)
    for key in ['release_qualified','selected','timing_closure_complete']:data[key]=False
    write(overview,data)
    print('Recorded progress031: unfilled full DRC/LVS and thirteen antenna stages pass; final fill/native antenna and electrical gates remain open.')

if __name__=='__main__':main()
