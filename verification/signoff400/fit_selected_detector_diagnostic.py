"""Fit selected-layout TT detector observations and replay independent holdouts.

The fitted scope is the sampled rising-edge neighborhood under conditional
exterior voltages. Holdout agreement cannot qualify unmeasured phases, corners,
receiver timing, exterior switching, or the model's uncertainty envelope.
"""
import argparse,csv,json,math,subprocess
from pathlib import Path
from common_v3 import save,sha,verify
from assess_selected_detector_phase_probe_v2 import transitions
from characterize_selected_detector_response import pair_phases
from fit_prototype_detector_model import render


def observe(path):
    a=json.loads(path.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    paths=[Path(p) for p in a['artifacts'] if p.endswith('/signals.csv')]
    if len(paths)!=1:raise ValueError('one verified selected waveform required')
    with paths[0].open() as f:
        reader=csv.reader(f);names=next(reader);rows=[[float(v) for v in row] for row in reader]
    if not rows or rows[0][0]!=0 or any(len(row)!=len(names) or not all(math.isfinite(v) for v in row) for row in rows) or any(b[0]<a[0] for a,b in zip(rows,rows[1:])):raise ValueError('finite nondecreasing waveform required')
    required=['reference_pin','feedback_pin','detector_up','detector_dn']
    if not set(required)<=set(names):raise ValueError('physical detector input and output observations required')
    edges={r:transitions(rows,names.index(r)) for r in required};end=rows[-1][0]*1e9;cycles=[]
    for ref,fb in pair_phases(edges['reference_pin']['rising_ns'],edges['feedback_pin']['rising_ns']):
        start=min(ref,fb)
        if start+20>end:continue
        active=[r for r in ['up','dn'] if any(start<=t<start+20 for t in edges['detector_'+r]['rising_ns'])]
        if len(active)!=1:raise ValueError('resolved unique detector decision required')
        cycles.append(dict(phase_ps=(fb-ref)*1000,decision=active[0]))
    if not cycles:raise ValueError('complete first-event observation required')
    latencies={r:{edge:[] for edge in ['rise','fall']} for r in ['UP','DN']}
    for role in latencies:
        for edge,direction in [('rise','rising_ns'),('fall','falling_ns')]:
            refs=edges['reference_pin'][direction]
            for t in edges['detector_'+role.lower()][direction]:
                prior=[v for v in refs if 0<t-v<20]
                if len(prior)!=1:raise ValueError('unique causal reference edge required')
                latencies[role][edge].append(t-prior[0])
    models={p:d for p,d in a['input_sha256'].items() if p.endswith('/model.spice')}
    if not models:
        manifests=[Path(p) for p in a['input_sha256'] if p.endswith('/manifest.json')]
        for manifest in manifests:
            models.update({p:d for p,d in json.loads(manifest.read_text())['input_sha256'].items() if p.endswith('/model.spice')})
    if len(models)!=1:raise ValueError('unique selected native model identity required')
    verify(models)
    return dict(assessment=str(path),waveform=str(paths[0]),native_model_sha256=models,edges=edges,cycles=cycles,latencies=latencies,
                measured_end_ns=end,normal_full_window_completed=a.get('normal_full_window_completed',True))


def same_model(observations):
    identities=[o['native_model_sha256'] for o in observations]
    if not identities or any(v!=identities[0] for v in identities):raise ValueError('fitting and holdouts must use the same physical native model')
    return identities[0]


def fit(observations):
    cycles=[c for o in observations for c in o['cycles']]
    dn=[c['phase_ps'] for c in cycles if c['decision']=='dn'];up=[c['phase_ps'] for c in cycles if c['decision']=='up']
    if not dn or not up or not max(dn)<min(up)<0:raise ValueError('ordered negative-phase opposite-decision bracket required')
    bracket=[max(dn),min(up)];latencies={}
    for role in ['UP','DN']:
        latencies[role]={}
        for edge in ['rise','fall']:
            values=[v for o in observations for v in o['latencies'][role][edge]]
            if not values:raise ValueError('both polarities require rise and fall timing')
            latencies[role][edge]=dict(observed_interval=[min(values),max(values)],nominal=(min(values)+max(values))/2)
    return dict(lookback_ps=-(sum(bracket)/2),observed_transition_bracket_ps=bracket,native_clock_latency_ns=latencies)


def replay(observation,parameters,model,folder):
    folder.mkdir();events=[]
    for role,signal in [('reference_pin','refclk'),('feedback_pin','feedback')]:
        for direction,value in [('rising_ns',1),('falling_ns',0)]:
            events.extend((round(t*1000),signal,value) for t in observation['edges'][role][direction])
    lines=['`timescale 1ns/1ps','module bench; reg refclk=0,feedback=0,reset_n=0; wire [1:0] bbpd;',
           'Prototype400DetectorModel dut(refclk,feedback,reset_n,bbpd);','initial begin #1;reset_n=1;end','initial begin']
    previous=0
    for t,signal,value in sorted(events):
        lines.append(f'#{(t-previous)/1000:.3f}; {signal}={value};');previous=t
    lines.extend(['end',f'initial begin #{observation["measured_end_ns"]:.9f}; $display("REPLAY_END");$finish;end'])
    for role,index in [('dn',0),('up',1)]:
        for edge,trigger in [('rise','posedge'),('fall','negedge')]:lines.append(f'always @({trigger} bbpd[{index}]) $display("EDGE {role} {edge} %.9f",$realtime);')
    lines.append('endmodule');bench=folder/'bench.v';bench.write_text('\n'.join(lines)+'\n');binary=folder/'bench.vvp'
    with (folder/'compile.log').open('x') as log:subprocess.run(['/usr/bin/iverilog','-g2012','-s','bench','-o',str(binary),str(model),str(bench)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    result=subprocess.run(['/usr/bin/vvp',str(binary)],capture_output=True,text=True,check=True,timeout=60)
    (folder/'run.log').write_text(result.stdout)
    if 'REPLAY_END' not in result.stdout:raise ValueError('incomplete fitted detector replay')
    emitted={(r,e):[] for r in ['up','dn'] for e in ['rise','fall']}
    for line in result.stdout.splitlines():
        f=line.split()
        if f and f[0]=='EDGE' and float(f[3])>5:emitted[f[1],f[2]].append(float(f[3]))
    records=[]
    for role in ['up','dn']:
        for edge,direction in [('rise','rising_ns'),('fall','falling_ns')]:
            actual=observation['edges']['detector_'+role][direction];predicted=emitted[role,edge]
            bounds=parameters['native_clock_latency_ns'][role.upper()][edge]['observed_interval'];limit=(bounds[1]-bounds[0])/2+.00101
            errors=[abs(a-b)*1000 for a,b in zip(actual,predicted)]
            records.append(dict(role=role,edge=edge,native_count=len(actual),model_count=len(predicted),
                counts_match=len(actual)==len(predicted),edge_errors_ps=errors,
                within_observed_fit_band_and_1ps_quantization=len(actual)==len(predicted) and all(e<=limit*1000 for e in errors)))
    threshold=-parameters['lookback_ps'];signs=[dict(**c,predicted='dn' if c['phase_ps']<threshold else 'up') for c in observation['cycles']]
    return dict(assessment=observation['assessment'],normal_full_window_completed=observation['normal_full_window_completed'],
                cycles=signs,all_sampled_signs_match=all(c['decision']==c['predicted'] for c in signs),edge_checks=records,
                all_event_counts_match=all(r['counts_match'] for r in records),
                all_edges_within_observed_fit_band=all(r['within_observed_fit_band_and_1ps_quantization'] for r in records))


def run(fitting,holdouts,output):
    if set(fitting)&set(holdouts) or len(set(fitting))!=len(fitting) or len(set(holdouts))!=len(holdouts) or not fitting or not holdouts:raise ValueError('distinct nonempty fitting and holdout sets required')
    for binary in ['/usr/bin/iverilog','/usr/bin/vvp']:
        if not Path(binary).is_file():raise EnvironmentError('run inside the pinned release container; missing '+binary)
    observed=[observe(p) for p in fitting];independent=[observe(p) for p in holdouts]
    model_identity=same_model(observed+independent);parameters=fit(observed)
    output.mkdir(parents=True);model=output/'detector.v';model.write_text(render(parameters));save(output/'parameters.json',parameters)
    records=[]
    for label,values in [('fit',observed),('holdout',independent)]:
        for i,o in enumerate(values):records.append(dict(scope=label,**replay(o,parameters,model,output/f'{label}_{i}')))
    paths=[*fitting,*holdouts,Path(__file__).resolve(),Path(__file__).with_name('fit_prototype_detector_model.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py'),Path(__file__).with_name('characterize_selected_detector_response.py'),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]
    pins={str(p):sha(p) for p in paths};verify(pins)
    artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,status='conditional_selected_detector_fit',
        corner='tt',supply_v=1.8,temperature_c=27,native_model_sha256=model_identity,records=records,fit_assessments=len(fitting),holdout_assessments=len(holdouts),
        all_sampled_signs_match=all(r['all_sampled_signs_match'] for r in records),
        all_event_counts_match=all(r['all_event_counts_match'] for r in records),
        all_edges_within_observed_fit_band=all(r['all_edges_within_observed_fit_band'] for r in records),
        scope='sampled rising-edge neighborhood; conditional exterior voltage and loading only',
        full_phase_coverage_qualified=False,receiver_path_latency_included=False,all_process_corners_covered=False,
        independent_qualification_holdouts_complete=False,exterior_switching_qualified=False,numerical_convergence_qualified=False,
        diagnostic=True,synthetic=True,native_interface_qualified=False,validated_for_prototype=False,release_ready=False))
    print(json.dumps(dict(lookback_ps=parameters['lookback_ps'],fit_cases=len(fitting),holdout_cases=len(holdouts),
        all_sampled_signs_match=all(r['all_sampled_signs_match'] for r in records),all_event_counts_match=all(r['all_event_counts_match'] for r in records),all_edges_within_fit_band=all(r['all_edges_within_observed_fit_band'] for r in records))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fit',action='append',type=Path,required=True);p.add_argument('--holdout',action='append',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run([p.resolve() for p in a.fit],[p.resolve() for p in a.holdout],a.output.resolve())
