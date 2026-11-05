"""Isolate the recorded synchronizer-clock substitution in two completed probes."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from assess_selected_detector_prefix import read_prefix
from assess_selected_detector_phase_probe_v4 import transitions
from resources import identity


def signature(value):
    match=re.fullmatch(r'PWL FILE "([^"]+)"',value)
    return ('PWL',sha(Path(match[1]))) if match else ('literal',value)


def canonical_deck(text):
    text,count=re.subn(r'(?m)^\.include "[^"\n]+/(devices|sources)\.spice"$',lambda m:'.include "<'+m[1]+'>"',text)
    if count!=2:raise ValueError('two native include cards required')
    text,count=re.subn(r'(?i)\bfile=\S+','file=<RAW>',text)
    if count!=1:raise ValueError('one RAW output required')
    return text


def run(base,target,output):
    if output.exists():raise FileExistsError(output)
    pins={str(Path(__file__).resolve()):sha(Path(__file__).resolve())};manifests=[];responses=[];waves=[]
    for case in [base,target]:
        if json.loads((case/'status.json').read_text())['state']!='nearzero_conditional_response_measured':raise ValueError('completed physical-driver case required')
        native=case/'native';worker=json.loads((native/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('original native worker still live')
        manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256']);manifests.append(m)
        response=case/'response.json';r=json.loads(response.read_text());verify(r['input_sha256']);responses.append(r)
        roles=m['observed_roles'];rows,info=read_prefix(native/'probe.raw',roles)
        if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-80e-9)>1e-18:raise ValueError('normal complete 80 ns waveform required')
        waves.append({role:transitions(rows,i) for i,role in enumerate(roles,1)})
        for p in [case/'status.json',manifest,response,native/'probe.raw',native/'devices.spice',native/'sources.spice',native/'exterior_initial_voltages.json',native/'probe.spice']:pins[str(p)]=sha(p)
    if manifests[0]['observed_roles']!=manifests[1]['observed_roles']:raise ValueError('identical physical observations required')
    for name in ['devices.spice','exterior_initial_voltages.json']:
        if sha(base/'native'/name)!=sha(target/'native'/name):raise ValueError('circuit or quiet exterior voltages changed')
    if canonical_deck((base/'native/probe.spice').read_text())!=canonical_deck((target/'native/probe.spice').read_text()):raise ValueError('solver or observation deck changed')
    a,b=[sources(case/'native/sources.spice') for case in [base,target]]
    if a.keys()!=b.keys():raise ValueError('boundary inventory changed')
    changed=[node for node in a if signature(a[node][1])!=signature(b[node][1])]
    if changed!=['__context_node_5343']:raise ValueError('only the physical synchronizer clock may change')
    checks=[]
    for role in waves[0]:
        for edge in ['rising_ns','falling_ns']:
            x,y=[w[role][edge] for w in waves];same=len(x)==len(y)
            checks.append(dict(role=role,edge=edge,base_count=len(x),recorded_clock_count=len(y),counts_match=same,
                maximum_edge_difference_ps=max([abs(a-b)*1000 for a,b in zip(x,y)],default=0) if same else None))
    records=[]
    if len(responses[0]['cycles'])!=len(responses[1]['cycles']):raise ValueError('paired complete reference windows required')
    for a,b in zip(responses[0]['cycles'],responses[1]['cycles']):
        records.append(dict(reference_rise_ns=b['reference_rise_ns'],base_decision=a['decision'],recorded_clock_decision=b['decision'],
            physical_input_phase_difference_ps=b['measured_feedback_minus_reference_ps']-a['measured_feedback_minus_reference_ps'],
            captures={role:dict(base=a['capture'][role],recorded_clock=b['capture'][role]) for role in ['up','dn']}))
    verify(pins)
    save(output,dict(input_sha256=pins,physical_circuit_identical=True,quiet_exterior_identical=True,
        solver_controls_identical=True,changed_voltage_input_nodes=changed,cycles=records,edge_comparisons=checks,
        all_sampled_decisions_match=all(r['base_decision']==r['recorded_clock_decision'] for r in records),
        detector_fit_qualified=False,receiver_path_timing_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['base','target','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,name).resolve() for name in ['base','target','output']))
