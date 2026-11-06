"""Fit one explicitly bound corner's raw detector observations and holdouts.

Recorded upstream excitation remains TT; this diagnostic does not qualify
corner sender waveforms or a uniform detector uncertainty envelope.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from fit_selected_detector_diagnostic import observe,same_model,fit,replay
from fit_prototype_detector_model import render
from selected_spice_device_conditions import read
from audit_selected_dco_history_inputs import sources


def observe_corner(path,corner):
    case=path.parent.parent;manifest=case/'native/manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    expected=dict(corner=corner,temperature_c=27,supply_v=1.8)
    if m['operating_point']!=expected or m['initialization_corner']!=corner:raise ValueError('actual native model and initial-state corner must match requested fit')
    deck=case/'native/probe.spice';condition=read(deck)
    if condition!={'corner':corner,'temperature_c':27.}:raise ValueError('actual PDK selector differs from fit metadata')
    voltage=sources(case/'native/sources.spice')
    if any(float(voltage[n][1])!=v for n,v in(('VPWR',1.8),('VPB',1.8),('VGND',0.),('VNB',0.))):raise ValueError('nominal supply/body rails required')
    if m['upstream_waveform_operating_point']!={'corner':'tt','coarse':20,'fine':111,'temperature_c':27,'supply_v':1.8}or m['corner_sender_waveforms_correlated']is not False:raise ValueError('explicit recorded TT-excitation diagnostic scope required')
    a=json.loads(path.read_text())
    if a['native_duration_ns']!=80 or a['all_native_samples_finite']is not True or a['missing_physical_input_observations']:raise ValueError('complete physical raw detector observations required')
    if json.loads((case/'status.json').read_text())['state']!='corner_detector_response_measured':raise ValueError('normally completed original corner case required')
    o=observe(path);o['binding_paths']=[manifest,deck,case/'native/sources.spice',case/'status.json'];return o


def run(fitting,holdouts,corner,output):
    if output.exists():raise FileExistsError(output)
    if corner not in('ff','ss','sf','fs'):raise ValueError('declared non-TT process corner required')
    if not fitting or not holdouts or len(set(fitting+holdouts))!=len(fitting)+len(holdouts):raise ValueError('nonempty disjoint fitting and independent holdout sets required')
    observations=[observe_corner(p,corner)for p in fitting];independent=[observe_corner(p,corner)for p in holdouts];model_id=same_model(observations+independent);parameters=fit(observations)
    parameters.update(operating_point=dict(corner=corner,temperature_c=27,supply_v=1.8),upstream_waveform_operating_point=dict(corner='tt',coarse=20,fine=111,temperature_c=27,supply_v=1.8),corner_sender_waveforms_correlated=False)
    output.mkdir(parents=True);model=output/'detector.v';model.write_text(render(parameters));save(output/'parameters.json',parameters)
    records=[]
    for label,values in(('fit',observations),('holdout',independent)):
        for i,o in enumerate(values):records.append(dict(scope=label,**replay(o,parameters,model,output/f'{label}_{i}')))
    paths=[*fitting,*holdouts,Path(__file__).resolve(),*(Path(__file__).with_name(n)for n in('common_v3.py','fit_selected_detector_diagnostic.py','fit_prototype_detector_model.py','selected_spice_device_conditions.py','audit_selected_dco_history_inputs.py')),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]
    paths += [p for o in observations+independent for p in o['binding_paths']];pins={str(p):sha(p)for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in output.rglob('*')if p.is_file()},operating_point=parameters['operating_point'],native_model_sha256=model_id,
        fit_assessments=len(fitting),holdout_assessments=len(holdouts),records=records,
        all_sampled_signs_match=all(r['all_sampled_signs_match']for r in records),all_event_counts_match=all(r['all_event_counts_match']for r in records),all_edges_within_observed_fit_band=all(r['all_edges_within_observed_fit_band']for r in records),
        upstream_waveform_operating_point=parameters['upstream_waveform_operating_point'],corner_sender_waveforms_correlated=False,
        diagnostic=True,synthetic=True,native_interface_qualified=False,uniform_uncertainty_bound_qualified=False,full_phase_coverage_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fit',action='append',type=Path,required=True);p.add_argument('--holdout',action='append',type=Path,required=True);p.add_argument('--corner',choices=('ff','ss','sf','fs'),required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run([x.resolve()for x in a.fit],[x.resolve()for x in a.holdout],a.corner,a.output.resolve())
