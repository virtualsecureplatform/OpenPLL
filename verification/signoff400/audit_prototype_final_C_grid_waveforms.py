"""Offline replay of native grid review, including measured input ramps and legacy metadata."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from characterize_prototype_final_cell_C_grid_v2 import review,fixtures


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    retained=[Path(p) for p in r['input_sha256'] if p.endswith('/observations.json')]
    if len(retained)!=1:raise ValueError('unique retained fixture bank required')
    verify({str(retained[0]):r['input_sha256'][str(retained[0])]})
    if not r['all_native_fixtures_passed'] or r['native_fixtures']!=729:raise ValueError('completed full combinational grid required')
    cases=fixtures(json.loads(retained[0].read_text()),r['corner'])
    wave=source/'batch.prn';observed=source/'observations.json';plan=source/'plan.json'
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+43200):
        replay,samples=review(wave,cases)
    original=json.loads(observed.read_text())
    if replay!=original or samples!=r['samples']:raise ValueError('independent waveform review differs from original observations')
    paths=[receipt,*retained,wave,observed,plan,Path(__file__).resolve(),Path(__file__).with_name('characterize_prototype_final_cell_C_grid_v2.py')]
    pins={str(p):sha(p) for p in paths};verify(pins)
    output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256=pins,corner=r['corner'],native_fixtures=len(replay),samples=samples,
        every_actual_input_ramp_verified_from_native_20_80_crossings=True,
        all_native_transition_counts_delays_slews_and_rails_replayed=True,
        all_original_observations_exactly_reproduced=True,
        original_plan_summary_metadata=json.loads(plan.read_text()).get('ramp_ps'),
        authoritative_full_ramp_ps_axis=sorted({f['full_ramp_ps'] for f in cases}),
        native_simulations_started=0,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
