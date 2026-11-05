"""Compare completed DCO models in an identical observation window without rerunning native cases."""
import argparse
import csv
import json
from pathlib import Path
from common_v3 import save, sha, verify
from assess_prototype_native_waveform import read_points, assess


def sample(directory,start_ns,stop_ns):
    receipt=directory/'assessment.json';review=directory/'all_cycle_assessment/assessment.json'
    r,a=[json.loads(p.read_text()) for p in (receipt,review)]
    if not r['native_worker_completed'] or not a['all_captured_measurement_cycles_assessed']:
        raise ValueError('completed independently assessed native point required')
    verify(r['input_sha256']);verify(a['input_sha256']);verify(a['artifacts'])
    manifest=directory/'input_manifest.json';m=json.loads(manifest.read_text());command=m['command']
    def arg(n):return command[command.index(n)+1]
    identity=(arg('--corner'),float(arg('--temperature-c')),float(arg('--vdd')),
              int(arg('--coarse-codes')),int(arg('--codes')))
    if arg('--simulator')!='ngspice' or '--ngspice-klu' not in command:
        raise ValueError('same explicit KLU solver family required')
    if not 0<=start_ns<stop_ns<=float(arg('--sim-time-ns')):raise ValueError('comparison window not covered')
    table=directory/'native/dco_postlayout_results.csv';rows=list(csv.DictReader(table.open()))
    if len(rows)!=1 or rows[0]['status']!='pass' or rows[0]['timed_out']!='no':raise ValueError('one successful native point required')
    row=rows[0];wave=Path(row['waveform']);deck=Path(row['netlist']);log=Path(row['log'])
    for p in (wave,deck,log,table):
        if a['input_sha256'].get(str(p))!=sha(p):raise ValueError('native output not pinned by waveform assessment')
    if 'Using KLU as Direct Linear Solver' not in log.read_text():raise ValueError('native KLU banner required')
    metrics=assess(read_points(wave),start_ns*1e-9,stop_ns*1e-9,identity[2])
    physical={p:h for p,h in r['input_sha256'].items() if p.endswith('.gds')}
    if len(physical)!=1:raise ValueError('one directly pinned candidate GDS required')
    paths=[receipt,review,manifest,table,wave,deck,log]
    return identity,physical,metrics,{str(p):sha(p) for p in paths}


def run(baseline,driver,farthest,start_ns,stop_ns,output):
    records={};pins={};identities=[];layouts=[]
    for label,directory in (('cell_C_plus_SPEF',baseline),('full_C_driver',driver),('full_C_farthest',farthest)):
        identity,physical,metrics,paths=sample(directory,start_ns,stop_ns)
        identities.append(identity);layouts.append(physical);pins.update(paths);records[label]=metrics
    if any(i!=identities[0] for i in identities) or any(g!=layouts[0] for g in layouts):
        raise ValueError('comparison physical candidate and operating point must match')
    base=records['cell_C_plus_SPEF']['average_frequency_hz']
    frequency={k:v['average_frequency_hz'] for k,v in records.items()}
    spread=abs(frequency['full_C_driver']-frequency['full_C_farthest'])
    for n in ('assess_prototype_native_waveform.py',):
        p=Path(__file__).with_name(n);pins[str(p)]=sha(p)
    pins[str(Path(__file__).resolve())]=sha(Path(__file__).resolve());verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'comparison.json'
    save(detail,dict(operating_point=dict(zip(('corner','temperature_c','supply_v','coarse_code','fine_code'),identities[0])),
         candidate_gds_sha256=layouts[0],window_start_ns=start_ns,window_stop_ns=stop_ns,
         all_cycle_metrics=records,average_frequency_hz=frequency,
         frequency_shift_from_cell_C_plus_SPEF_ppm={k:(v/base-1)*1e6 for k,v in frequency.items()},
         attachment_variant_spread_hz=spread))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         identical_candidate_and_operating_point_verified=True,identical_measurement_window_verified=True,
         all_captured_complete_cycles_in_window_assessed=True,native_simulations_started=0,
         sampled_attachment_frequency_spread_hz=spread,
         distributed_C_placement_uncertainty_bounded=False,numerical_uncertainty_included=False,
         parent_loading_complete=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','driver','farthest','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--start-ns',type=float,default=10);p.add_argument('--stop-ns',type=float,default=40)
    a=p.parse_args();run(a.baseline.resolve(),a.driver.resolve(),a.farthest.resolve(),a.start_ns,a.stop_ns,a.output.resolve())
