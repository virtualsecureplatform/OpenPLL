#!/usr/bin/env python3
"""Bind candidate006 physical failures; antenna zero cannot waive shorts."""
import json
from pathlib import Path
import re
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';layout=base/'parent_dco_antenna_layout_006'
    lvs=verify(base/'parent_dco_antenna_lvs_006/assessment.json')
    topology=verify(base/'parent_dco_antenna_port_topology_006/assessment.json')
    antenna=verify(base/'parent_dco_antenna_bound_geometry_006/assessment.json')
    terminal=json.loads((layout/'native_completion.json').read_text())
    assert terminal['exit_code']==0 if 'exit_code' in terminal else (layout/'assembly.spice').exists()
    report=(layout/'drc_errors.rpt').read_text();count=int(re.search(r'MAGIC_DRC_RECTANGLES=(\d+)',report)[1]);assert count==8
    assert 'Metal1 spacing' in report
    assert not lvs['assembled_lvs_passed'] and not lvs['final_unique_match']
    records=json.loads((base/'parent_dco_antenna_port_topology_006/records.json').read_text())
    shorts=sorted([r['logical_nets'] for r in records['shorts']]);expected=sorted([
        ['DCO_THERM[101]','DCO_THERM[53]','DCO_THERM[77]'],['DCO_THERM[11]','DCO_THERM[21]']])
    assert shorts==expected and topology['missing_probes']==0 and topology['split_logical_nets']==0
    assert antenna['violations']==0 and not antenna['antenna_qualified']
    files=[Path(__file__).resolve(),layout/'native_completion.json',layout/'drc_errors.rpt',
        base/'parent_dco_antenna_lvs_006/assessment.json',base/'parent_dco_antenna_lvs_006/compare.json',
        base/'parent_dco_antenna_port_topology_006/assessment.json',base/'parent_dco_antenna_port_topology_006/records.json',
        base/'parent_dco_antenna_bound_geometry_006/assessment.json',base/'parent_dco_antenna_stream_006/assessment.json']
    out=base/'parent_dco_antenna_physical_failure_006';out.mkdir(exist_ok=False)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},
        candidate='parent_dco_antenna_stream_006',full_magic_drc_rectangles=count,assembled_lvs_passed=False,
        independently_confirmed_signal_short_groups=shorts,rectangular_macro_port_probes=topology['rectangular_macro_port_probes'],
        independent_antenna_diagnostic_violations=0,antenna_zero_ineligible_due_to_physical_shorts=True,
        repair='Reroute original ten diode nets plus THERM21/53/101; temporary M1 access keepout at spacing cluster.',
        release_qualified=False,adopted=False,scope=__doc__))
    print('Candidate006 fails: eight M1 spacing markers and two confirmed signal short groups. Antenna zero is ineligible.')

if __name__=='__main__':main()
