"""Replay frozen corner parameters against independently bound native senders."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from fit_selected_detector_diagnostic import replay
from selected_detector_level_observations import observe
from selected_matching_corner_sender import validate
from selected_spice_device_conditions import read
from audit_selected_dco_history_inputs import sources


def fit_corner(frozen):
    corner=frozen.get('corner',frozen.get('operating_point',{}).get('corner'))
    if corner not in ('tt','ff','ss','sf','fs'):
        raise ValueError('explicit frozen fit corner required')
    if 'operating_point' in frozen and frozen['operating_point']!={'corner':corner,'temperature_c':27,'supply_v':1.8}:
        raise ValueError('nominal frozen fit operating point required')
    return corner


def bind_matched_native(manifest,corner,model_identity):
    m=json.loads(manifest.read_text());verify(m['input_sha256'])
    models={p:d for p,d in m['input_sha256'].items() if p.endswith('/model.spice')}
    if models!=model_identity:raise ValueError('same physical native model required')
    expected={'corner':corner,'temperature_c':27,'supply_v':1.8}
    if m.get('operating_point')!=expected or m.get('initialization_corner')!=corner:
        raise ValueError('fit, native device and initial-state corners must match')
    if m.get('corner_sender_waveforms_correlated') is not True:
        raise ValueError('matching full-native sender required')
    if m.get('physical_feedback_driver_retained') is not True or m.get('feedback_driver_Q_voltage_prescribed') is not False:
        raise ValueError('physical feedback driver must be retained without Q clamp')
    deck=manifest.parent/'probe.spice';rails=manifest.parent/'sources.spice'
    if read(deck)!={'corner':corner,'temperature_c':27.}:
        raise ValueError('actual native PDK corner differs from frozen fit')
    voltage=sources(rails)
    if any(float(voltage[n][1])!=v for n,v in (('VPWR',1.8),('VPB',1.8),('VGND',0.),('VNB',0.))):
        raise ValueError('nominal supply/body rails required')
    full=[Path(p) for p in m['input_sha256'] if p.endswith('/manifest.json')]
    if len(full)!=1:raise ValueError('unique full-native source manifest required')
    snapshot=Path(m['reference_initial_vector_snapshot'])
    waveforms=Path(m['native_clock_shape_source'])
    op,pins=validate(full[0].parent,snapshot,waveforms,corner)
    if op!=m.get('upstream_waveform_operating_point'):
        raise ValueError('sender operating point differs from captured source')
    for p in [manifest,deck,rails,full[0]]:pins[str(p)]=sha(p)
    if any(m['input_sha256'].get(p)!=d for p,d in pins.items() if p!=str(manifest)):
        raise ValueError('native manifest must bind all matching-source receipts')
    return op,pins


def run(fit,assessments,output):
    if output.exists():raise FileExistsError(output)
    frozen=json.loads((fit/'assessment.json').read_text())
    corner=fit_corner(frozen)
    verify(frozen['input_sha256']);verify(frozen['artifacts'])
    if not assessments or len(set(assessments))!=len(assessments):raise ValueError('distinct nonempty holdouts required')
    old={r['assessment'] for r in frozen['records']}
    if old & set(map(str,assessments)):raise ValueError('new independent observations required')
    parameters=json.loads((fit/'parameters.json').read_text());model=fit/'detector.v'
    pins={str(p):sha(p) for p in [fit/'assessment.json',fit/'parameters.json',model,*assessments,Path(__file__).resolve(),Path(__file__).with_name('fit_selected_detector_diagnostic.py'),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]}
    observations=[observe(path,parameters['lookback_ps']) for path in assessments]
    helper=Path(__file__).with_name('selected_detector_level_observations.py');pins[str(helper)]=sha(helper)
    for path in assessments:
        a=json.loads(path.read_text())
        manifests=[Path(p) for p in a['input_sha256'] if p.endswith('/manifest.json')]
        if len(manifests)!=1:raise ValueError('unique physical native manifest required')
        if a.get('native_duration_ns')!=80 or a.get('all_native_samples_finite') is not True or a.get('missing_physical_input_observations'):
            raise ValueError('complete 80 ns finite physical observations required')
        case=manifests[0].parent.parent
        status=case/'status.json'
        if json.loads(status.read_text()).get('state')!='corner_detector_response_measured':
            raise ValueError('normally completed matched-sender case required')
        op,binding=bind_matched_native(manifests[0],corner,frozen['native_model_sha256'])
        pins.update(binding);pins[str(status)]=sha(status)
    for name in ['common_v3.py','selected_matching_corner_sender.py','selected_spice_device_conditions.py',
                 'audit_selected_dco_history_inputs.py','capture_selected_native_initial_snapshot.py']:
        helper=Path(__file__).with_name(name);pins[str(helper)]=sha(helper)
    output.mkdir(parents=True)
    records=[]
    for i,o in enumerate(observations):
        record=replay(dict(o,cycles=[]),parameters,model,output/f'holdout_{i}')
        record.update(cycles=o['cycles'],all_sampled_signs_match=all(c['decision']==c['predicted'] for c in o['cycles']),
                      pre_reference_detector_edges=o['pre_reference_detector_edges'],initial_feedback_high=o['initial_feedback_high'])
        records.append(record)
    verify(pins)
    artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,records=records,
        corner=corner,parameters_refitted=False,corner_sender_waveforms_correlated=True,
        correlation_scope="identical full-native sender and initialization per observation; conditional exterior/reset remain unqualified",
        native_interface_qualified=False,uniform_uncertainty_bound_qualified=False,all_sampled_signs_match=all(r['all_sampled_signs_match'] for r in records),
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
