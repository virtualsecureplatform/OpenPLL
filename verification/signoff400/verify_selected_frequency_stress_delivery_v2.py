"""Verify actual cached-RTL stress delivery without claiming closed-loop lock."""
import argparse
import csv
import json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify


def run(output):
    if output.exists():raise FileExistsError(output)
    base = ROOT/'build/signoff400'
    names = ['selected_stress_delivery_baseline_946','selected_stress_delivery_no_stress_947',
        'selected_stress_delivery_nominal_948','selected_stress_delivery_gain_949',
        'selected_stress_delivery_offset_950','selected_stress_delivery_both_951',
        'selected_stress_seed133_nominal_952','selected_stress_seed133_gain_953']
    folders = [base/n for n in names]
    identical = ('dco_table.txt','dco_frequency_model.json','controls.csv','edges.csv',
                 'segments.csv','reference_phase.json','run.log')
    for name in identical:
        if len({sha(folder/name) for folder in folders[:3]}) != 1:
            raise ValueError('unstressed/nominal cached traces differ: '+name)
    paths = [Path(__file__).resolve()]
    records = []
    tables = []
    for folder in folders:
        inputs = json.loads((folder/'inputs.json').read_text())
        assessment = json.loads((folder/'assessment.json').read_text())
        verify(inputs['input_sha256'])
        if assessment['release_ready'] is not False or assessment['state'] != 'needs_native_tuning_points':
            raise ValueError('expected unqualified delivery control stopping at missing native coverage')
        table = {}
        for line in (folder/'dco_table.txt').read_text().splitlines():
            c,f,v = map(int,line.split())
            if (c,f) in table:raise ValueError('duplicate model lookup key')
            table[c,f] = v
        tables.append(table)
        checked = 0
        previous = None
        half_periods = 0
        max_half_period_error_ps = 0.
        consumed = set()
        with (folder/'controls.csv').open() as stream:
            for row in csv.DictReader(stream):
                if row['event'] != 'EDGE':
                    previous = None
                    continue
                key = int(row['coarse']),int(row['fine'])
                if table.get(key) != int(row['frequency_millihz']):
                    raise ValueError('delivered VPI frequency differs from explicit stress table')
                current = (key,int(row['frequency_millihz']),int(row['time_ps']),int(row['level']))
                if previous is not None and previous[:2] == current[:2]:
                    error = abs((current[2]-previous[2])-5e14/current[1])
                    if current[3] == previous[3] or error > 1.01:raise ValueError('actual oscillator timing does not deliver stressed frequency at1ps quantization')
                    max_half_period_error_ps=max(max_half_period_error_ps,error);half_periods+=1
                previous=current
                checked += 1;consumed.add(key)
        if not checked or not half_periods:raise ValueError('actual oscillator edge and period delivery required')
        requests = assessment['measurement_requests']
        if not requests or any((r['coarse'],r['fine']) in table for r in requests):
            raise ValueError('missing-code requests must remain outside native interpolation domain')
        records.append(dict(case=str(folder),oscillator_edges_checked=checked,
            consumed_codes=[list(k) for k in sorted(consumed)],measurement_requests=requests,
            delivered_frequencies_match_derived_table=True,constant_code_half_periods_checked=half_periods,maximum_half_period_quantization_error_ps=max_half_period_error_ps))
        paths += [folder/n for n in ('inputs.json','assessment.json','dco_table.txt','controls.csv')]
    if any(set(t) != set(tables[0]) for t in tables):
        raise ValueError('frequency stress must not expand calibration lookup coverage')
    if tables[3] == tables[0] or tables[4] == tables[0] or tables[5] == tables[0]:
        raise ValueError('each nonnominal stress must actually change model frequencies')
    if tables[6][20,133] == tables[7][20,133] or any([20,133] not in r['consumed_codes'] for r in records[6:]):
        raise ValueError('gain stress must be exercised at a measured nonanchor code')
    pins = {str(p):sha(p) for p in paths};verify(pins)
    save(output,dict(input_sha256=pins,records=records,
        unstressed_and_nominal_seven_artifacts_byte_identical=True,
        every_observed_oscillator_edge_uses_explicit_table_frequency=True,
        actual_half_periods_match_stressed_frequency_within_1p01ps=True,
        gain_applied_at_nonanchor_code133=True,lookup_domain_expanded=False,
        missing_native_coverage_preserved=True,complete_closed_loop_cases=0,
        controller_robustness_qualified=False,uniform_model_uncertainty_qualified=False,release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args();run(a.output.resolve())
