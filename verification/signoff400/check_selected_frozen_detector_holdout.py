"""Check new native observations against frozen detector parameters, without refit."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from fit_selected_detector_diagnostic import observe,replay


def run(fit,assessments,output):
    if output.exists():raise FileExistsError(output)
    frozen=json.loads((fit/'assessment.json').read_text())
    if frozen.get('corner')!='tt':raise ValueError('only selected TT diagnostic fit supported')
    verify(frozen['input_sha256']);verify(frozen['artifacts'])
    if not assessments or len(set(assessments))!=len(assessments):raise ValueError('distinct nonempty holdouts required')
    old={r['assessment'] for r in frozen['records']}
    if old & set(map(str,assessments)):raise ValueError('new independent observations required')
    parameters=json.loads((fit/'parameters.json').read_text());model=fit/'detector.v'
    pins={str(p):sha(p) for p in [fit/'assessment.json',fit/'parameters.json',model,*assessments,Path(__file__).resolve(),Path(__file__).with_name('fit_selected_detector_diagnostic.py'),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]}
    observations=[observe(path) for path in assessments]
    if any(o['native_model_sha256']!=frozen['native_model_sha256'] for o in observations):raise ValueError('same physical model required')
    for path in assessments:
        a=json.loads(path.read_text())
        manifests=[Path(p) for p in a['input_sha256'] if p.endswith('/manifest.json')]
        if len(manifests)!=1:raise ValueError('unique physical native manifest required')
        manifest=manifests[0];m=json.loads(manifest.read_text());verify(m['input_sha256'])
        decks=[Path(p) for p in m['input_sha256'] if p.endswith('/probe.spice')]
        if len(decks)!=1:raise ValueError('unique native detector deck required')
        lines=decks[0].read_text().splitlines()
        libs=[line for line in lines if line.startswith('.lib ')]
        if len(libs)!=1 or libs[0].split()[-1]!='tt' or '.options device temp=27' not in lines:
            raise ValueError('TT 27 C native observation required')
        pins[str(manifest)]=sha(manifest)
    output.mkdir(parents=True)
    records=[replay(o,parameters,model,output/f'holdout_{i}') for i,o in enumerate(observations)]
    verify(pins)
    artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,records=records,
        parameters_refitted=False,all_sampled_signs_match=all(r['all_sampled_signs_match'] for r in records),
        all_event_counts_match=all(r['all_event_counts_match'] for r in records),
        all_edges_within_observed_fit_band=all(r['all_edges_within_observed_fit_band'] for r in records),
        independent_qualification_holdouts_complete=False,full_phase_coverage_qualified=False,
        detector_fit_qualified=False,release_ready=False))
    print(json.dumps(records))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--fit',type=Path,required=True)
    parser.add_argument('--assessment',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.fit.resolve(),[p.resolve() for p in args.assessment],args.output.resolve())
