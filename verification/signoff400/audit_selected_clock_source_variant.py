"""Prove a bounded-stimulus control kept devices, biases and solver settings.

The RAW precision change is observational. Exact intermediate clock curves
must match before simplification; only their bounded PWL variants drive the
new circuit. Response equivalence remains a separate native measurement.
"""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify


def normalize_deck(text):
    lines=[]
    for line in text.splitlines():
        if line.lower().startswith('.include '):
            name=Path(line.split('"')[1]).name
            if name not in ['devices.spice','sources.spice']:raise ValueError('unexpected include in control deck')
            line='.include "'+name+'"'
        if line.lower().startswith('.print '):
            line=line.replace(' precision=17','');line=re.sub(r'\bfile=\S+','file=<output>',line,flags=re.I)
        lines.append(line)
    return '\n'.join(lines)


def compare(reference,candidate):
    rp,cp=[p/'manifest.json' for p in [reference,candidate]];r,c=[json.loads(p.read_text()) for p in [rp,cp]]
    verify(r['input_sha256']);verify(c['input_sha256'])
    if r['phase_50_percent_crossing_offset_ns']!=c['phase_50_percent_crossing_offset_ns']:raise ValueError('phase commands differ')
    for key in ['observed_roles','omitted_primitive_loads','native_cap_s','memory_GiB','exterior_condition']:
        if r[key]!=c[key]:raise ValueError('control configuration differs: '+key)
    if sha(reference/'devices.spice')!=sha(candidate/'devices.spice'):raise ValueError('native device/passive cards changed')
    if sha(reference/'exterior_initial_voltages.json')!=sha(candidate/'exterior_initial_voltages.json'):raise ValueError('exterior initial voltages changed')
    for role in ['reference','feedback']:
        if sha(reference/(role+'_native.pwl'))!=sha(candidate/(role+'_native.pwl')):raise ValueError('exact pre-simplification clock curve changed')
    def source(p):return re.sub(r'PWL FILE "[^"]+"','PWL FILE "<clock>"',p.read_text())
    if source(reference/'sources.spice')!=source(candidate/'sources.spice'):raise ValueError('non-clock source or source node changed')
    if normalize_deck((reference/'probe.spice').read_text())!=normalize_deck((candidate/'probe.spice').read_text()):raise ValueError('native circuit controls or solver settings changed')
    bounded=candidate/'bounded_clock_sources/assessment.json';b=json.loads(bounded.read_text());verify(b['input_sha256']);verify(b['artifacts'])
    if any(v['uniform_voltage_bound_V']!=1e-6 or v['maximum_voltage_difference_V']>1e-6 for v in b['clock_sources'].values()):raise ValueError('bounded stimulus exceeds declared 1 uV control')
    return dict(reference=str(reference),candidate=str(candidate),devices_and_passive_cards_identical=True,
        exterior_initial_voltages_identical=True,exact_intermediate_clock_curves_identical=True,
        non_clock_sources_and_source_nodes_identical=True,solver_settings_and_observed_nodes_identical=True,
        RAW_precision_only_observation_change=True,clock_voltage_error_bound_V=1e-6,
        native_response_equivalence_proven=False,release_ready=False)


def run(references,candidates,output):
    if output.exists():raise FileExistsError(output)
    if len(references)!=len(candidates) or not references:raise ValueError('paired nonempty controls required')
    records=[compare(r,c) for r,c in zip(references,candidates)]
    pins={str(p/'manifest.json'):sha(p/'manifest.json') for p in [*references,*candidates]};pins[str(Path(__file__).resolve())]=sha(Path(__file__));verify(pins)
    save(output,dict(input_sha256=pins,records=records,all_control_identities_match=True,
        native_response_equivalence_proven=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(paired_controls=len(records),all_control_identities_match=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',action='append',type=Path,required=True);p.add_argument('--candidate',action='append',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run([p.resolve() for p in a.reference],[p.resolve() for p in a.candidate],a.output.resolve())
