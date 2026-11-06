"""Explicit diagnostic frequency stress derived from observed TT discrepancies.

Measured knots stay unchanged. Applying local observations to a wider code
range is an engineering stress experiment, not a qualified uncertainty bound.
"""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
from common_v3 import save,sha,verify


def observations(gain_path,retarget_path):
    gain,retarget = [json.loads(p.read_text()) for p in (gain_path,retarget_path)]
    for receipt in (gain,retarget):
        verify(receipt['input_sha256'])
        if 'artifacts' in receipt:verify(receipt['artifacts'])
    if not gain['normal_native_completions'] or not retarget['normal_native_completions']:
        raise ValueError('normally completed discrepancy observations required')
    if (retarget['checkpoint_fine'],retarget['target_fine'],retarget['coarse']) != (111,133,20):
        raise ValueError('selected111-to133 state/history challenge required')
    manifests = [Path(p) for p in gain['input_sha256'] if p.endswith('/manifest.json')]
    if len(manifests) != 3:raise ValueError('exact pulse and two static reference manifests required')
    for path in manifests:
        m = json.loads(path.read_text());verify(m['input_sha256'])
        if m['operating_point'] != dict(corner='tt',temperature_c=27,supply_v=1.8):raise ValueError('observed TT operating point required')
    low = min(row['switched_over_static_increment'] for row in gain['windows'])
    offset = retarget['against_full_native']['common']['difference_ppm']
    if not math.isfinite(low) or low <= 0 or not math.isfinite(offset):
        raise ValueError('finite positive observed gain and finite offset required')
    lineage = retarget['native_model_lineage']
    if len(lineage) != 1:raise ValueError('one full physical model identity required')
    verify(lineage)
    pins = {str(p):sha(p) for p in (gain_path,retarget_path,Path(__file__).resolve())}
    pins.update(lineage)
    return low,offset,lineage,pins


def generate(gain_path,retarget_path,output):
    output.mkdir(parents=True,exist_ok=False)
    low,offset,lineage,pins = observations(gain_path,retarget_path)
    packets = []
    for name,use_gain,use_offset in (('nominal',False,False),('gain',True,False),
                                   ('offset',False,True),('gain_offset',True,True)):
        packet = output/(name+'.json')
        save(packet,dict(schema_version=1,kind='diagnostic_affine_frequency_stress',input_sha256=pins,
            gain_observation=str(gain_path),retarget_observation=str(retarget_path),
            physical_model_sha256=lineage,operating_point=dict(corner='tt',temperature_c=27,supply_v=1.8),
            coarse=20,anchor_fine=111,gain_choice='observed_low' if use_gain else 'nominal',
            offset_choice='observed_retarget' if use_offset else 'zero',
            gain_multiplier=low if use_gain else 1.,offset_ppm_at_anchor=offset if use_offset else 0.,
            measured_frequency_knots_modified=False,wide_code_applicability_qualified=False,
            extrema_joint_physical_realizability_claimed=False,uniform_uncertainty_bound_qualified=False,
            release_ready=False))
        packets.append(packet)
    save(output/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in packets},observed_low_gain_ratio=low,
        observed_retarget_difference_ppm=offset,finite_stress_scenarios=4,
        native_cases_launched=0,closed_loop_stress_executed=False,
        uniform_uncertainty_bound_qualified=False,release_ready=False))


def transform(dense,measured,packet):
    coarse,anchor = packet['coarse'],packet['anchor_fine']
    if set(c for c,f in dense) != {coarse} or (coarse,anchor) not in measured:
        raise ValueError('one matching coarse family and measured anchor required')
    factor = Fraction(str(packet['gain_multiplier']))
    ppm = Fraction(str(packet['offset_ppm_at_anchor']))
    if factor <= 0:raise ValueError('positive gain required')
    reference = measured[coarse,anchor]
    result = {key:round(reference+reference*ppm/1000000+factor*(value-reference))
              for key,value in dense.items()}
    if any(type(v) is not int or v <= 0 for v in result.values()):
        raise ValueError('positive integer millihertz stress frequencies required')
    return result


def apply(dense,measured,registry_path,packet_path):
    from selected_model_registry import validate
    packet = json.loads(packet_path.read_text())
    verify(packet['input_sha256'])
    low,offset,lineage,pins = observations(Path(packet['gain_observation']),Path(packet['retarget_observation']))
    if (packet.get('schema_version') != 1 or packet.get('kind') != 'diagnostic_affine_frequency_stress'
            or packet.get('uniform_uncertainty_bound_qualified') is not False
            or packet.get('release_ready') is not False
            or packet.get('wide_code_applicability_qualified') is not False):
        raise ValueError('explicitly unqualified diagnostic stress packet required')
    if packet['gain_choice'] not in ('nominal','observed_low') or packet['offset_choice'] not in ('zero','observed_retarget'):
        raise ValueError('supported predeclared observed stress choice required')
    if packet['gain_multiplier'] != (low if packet['gain_choice']=='observed_low' else 1.) or packet['offset_ppm_at_anchor'] != (offset if packet['offset_choice']=='observed_retarget' else 0.):
        raise ValueError('stress parameters differ from pinned observed choices')
    if packet['physical_model_sha256'] != lineage or packet['coarse'] != 20 or packet['anchor_fine'] != 111:
        raise ValueError('exact observed model and measured anchor required')
    if packet['operating_point'] != dict(corner='tt',temperature_c=27,supply_v=1.8):raise ValueError('TT observations cannot stress another process corner')
    registry = validate(json.loads(registry_path.read_text()))
    if registry['analog']['operating_point'] != packet['operating_point']:
        raise ValueError('stress operating point differs from native registry')
    if any(registry['analog']['input_sha256'].get(p)!=h for p,h in lineage.items()):
        raise ValueError('stress must bind the same full physical model')
    result = transform(dense,measured,packet)
    pins.update({str(p):sha(p) for p in (registry_path,packet_path)})
    pins.update(packet['input_sha256']);verify(pins)
    return result,dict(input_sha256=pins,packet=str(packet_path),gain_multiplier=packet['gain_multiplier'],
        offset_ppm_at_anchor=packet['offset_ppm_at_anchor'],coarse=20,anchor_fine=111,
        formula='f_stress(code)=f_measured(anchor)*(1+offset_ppm/1e6)+gain*(f_base(code)-f_measured(anchor))',
        lookup_domain_expanded=False,measured_knots_overwritten=False,
        wide_code_applicability_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('gain','retarget','output'):p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args();generate(a.gain.resolve(),a.retarget.resolve(),a.output.resolve())
