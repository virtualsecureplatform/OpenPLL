"""Independently review complex responses by native table column names."""
import argparse,json,time
from pathlib import Path
from common import save,sha
from resources import lease
from probe_native_junction_alias_v2 import table


def run(out):
    out.mkdir(parents=True,exist_ok=False);reference=Path('build/signoff400/startup_timing_junction_body_network_cause_003').resolve();receipt=reference/'assessment.json';wave=reference/'ac.cir.FD.prn';a=json.loads(receipt.read_text());paths=[receipt,wave,Path(__file__).resolve(),Path(__file__).with_name('probe_native_junction_alias_v2.py')];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    with lease(1,1,deadline):
        pins={str(p):sha(p) for p in paths}
        if pins[str(wave)]!=a['artifacts'][str(wave)]:raise ValueError('causal probe output changed')
        header=wave.open().readline().upper().split()
        if len(header)!=len(set(header)):raise ValueError('unique named native columns')
        data=table(wave,64,2);observations=[];maximum={0:0,1:0};absolute={0:0,1:0}
        for row in data:
            for model in range(2):
                for body in (1,0):
                    for electrode in ('VG','VS'):
                        values=[]
                        for version in (0,1):
                            name=f'{electrode}M{model}B{body}S0V{version}';values.append(complex(row[header.index(f'IR({name})')],row[header.index(f'II({name})')]))
                        left,right=values;delta=abs(left-right);relative=delta/max(abs(left),abs(right),1e-18);maximum[body]=max(maximum[body],relative);absolute[body]=max(absolute[body],delta);observations.append(dict(frequency_hz=row[1],model_index=model,native_instance='X14' if model==0 else 'X52',body_model_selector=body,electrode=electrode,pre_R_phasor_a=[left.real,left.imag],post_R_phasor_a=[right.real,right.imag],absolute_phasor_difference_a=delta,scaled_phasor_difference=relative))
        target=out/'complex_responses.json';save(target,observations)
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('causal review input changed')
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target)},PVT=dict(corner='tt',temperature_c=27,supply_v=1.8),named_column_complex_response_comparisons=len(observations),native_body_network_maximum_complex_relative_difference=maximum[1],native_body_network_maximum_complex_absolute_difference_a=absolute[1],disabled_body_network_maximum_complex_relative_difference=maximum[0],disabled_body_network_maximum_complex_absolute_difference_a=absolute[0],printed_alias_response_difference_disappears_with_body_network_disabled=absolute[1]>0 and absolute[0]==0,physical_effect_vs_numerical_conditioning_separated=False,modified_models_adopted=False,original_parameter_discrepancies_waived=False,spatial_junction_allocation_qualified=False,release_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
