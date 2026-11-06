"""Recover only an observer directory-hash failure from completed native data."""
import argparse,csv,json,math,os
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v2 import aligned,metrics,window_frequency


def run(original,baseline,native,reference,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28})
    failure=json.loads((original/'status.json').read_text())
    if failure['state']!='stopped_without_qualification' or not failure.get('reason','').startswith('IsADirectoryError('):raise ValueError('specific observer directory-hash failure required')
    inputs=json.loads((original/'inputs.json').read_text());verify(inputs['input_sha256'])
    report_path=original/'full_reference_comparison/assessment.json';report=json.loads(report_path.read_text());verify(report['input_sha256'])
    if report.get('normal_full_window_completed') is not True:raise ValueError('normally completed original native comparison required')
    waves=[];pins={str(p):sha(p) for p in [original/'status.json',original/'inputs.json',report_path,reference,Path(__file__).resolve(),Path(__file__).with_name('compare_selected_dco_startup_aligned_v2.py'),Path(__file__).with_name('assess_selected_detector_prefix.py')]}
    for p in [baseline,native]:
        if json.loads((p/'status.json').read_text())['state']!='real_driver_DCO_diagnostic_complete':raise ValueError('normal native completion required')
        m=json.loads((p/'manifest.json').read_text());verify(m['input_sha256'])
        worker=json.loads((p/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('native worker still live')
        rows,info=read_prefix(p/'control.raw',m['observed_roles'])
        if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete finite native 60 ns observations required')
        waves.append(aligned(rows,1,2))
        for name in ['manifest.json','status.json','control.raw','assessment.json']:pins[str(p/name)]=sha(p/name)
    if report['input_sha256'].get(str(native/'control.raw'))!=sha(native/'control.raw') or report['input_sha256'].get(str(reference))!=sha(reference):raise ValueError('original comparison must bind these exact observations')
    with reference.open() as stream:
        reader=csv.reader(stream);names=next(reader);full=[[float(x) for x in row] for row in reader]
    if not full or abs(full[-1][0]-260e-9)>1e-18 or any(len(row)!=len(names) or not all(math.isfinite(x) for x in row) for row in full):raise ValueError('complete finite full reference required')
    full_edges,full_startup=aligned(full,names.index('v(pllout)'),names.index('v(xpll:__parent_r_node_617)'))
    full_comparison=metrics(waves[1][0],full_edges,min(40,waves[1][1]['end_age_ns'],full_startup['end_age_ns']))
    if full_comparison!=report['frequency_comparisons']:raise ValueError('saved full-reference comparison did not reproduce')
    comparisons={}
    for name,start,stop in [('common',10,40),('early',10,25),('late',25,40)]:
        a,b=[window_frequency(w[0],start,stop) for w in waves]
        comparisons[name]=dict(window_after_first_rise_ns=[start,stop],baseline=a,clock_expanded=b,difference_ppm=1e6*(b['frequency_mhz']/a['frequency_mhz']-1))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,baseline_comparisons=comparisons,full_reference_comparisons=full_comparison,
        original_comparison_recomputed_identically=True,native_restarted=False,observer_failure_recovered=True,
        full_boundary_forcing_covered=False,frequency_correlation_qualified=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(baseline=comparisons['common'],full_reference=full_comparison['common'])))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['original','baseline','native','reference','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['original','baseline','native','reference','output']))
