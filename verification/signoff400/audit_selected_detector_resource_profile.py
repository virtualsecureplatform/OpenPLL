"""Check a 12-to-4 GiB profile change preserves exported detector physics/stimuli."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources


def run(reference,target,output):
    if output.exists():raise FileExistsError(output)
    a,b=[json.loads((p/'manifest.json').read_text()) for p in [reference,target]]
    for m in [a,b]:verify(m['input_sha256'])
    if (a['memory_GiB'],b['memory_GiB'])!=(12,4):raise ValueError('explicit original and bounded resource profiles required')
    excluded={'input_sha256','memory_GiB','bounded_clock_source_receipt'}
    if {k:v for k,v in a.items() if k not in excluded}!={k:v for k,v in b.items() if k not in excluded}:raise ValueError('non-resource manifest semantics changed')
    files=[Path(__file__).resolve(),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]+[d/n for d in [reference,target] for n in ['manifest.json','devices.spice','sources.spice','probe.spice']]
    if (reference/'devices.spice').read_bytes()!=(target/'devices.spice').read_bytes():raise ValueError('physical primitive/passive cards changed')
    decks=[];stimuli=[]
    for d,m in zip([reference,target],[a,b]):
        text=(d/'probe.spice').read_text()
        if text.count(str(d))!=3:raise ValueError('expected only local device/source includes and output path')
        decks.append(text.replace(str(d),'<CASE>'));normalized={}
        for node,(name,value) in sources(d/'sources.spice').items():
            match=re.fullmatch(r'PWL FILE "([^\"]+)"',value)
            if match:
                p=Path(match[1]);p.relative_to(d)
                if m['input_sha256'].get(str(p))!=sha(p):raise ValueError('actual bounded waveform must be pinned')
                files.append(p);value=('PWL_SHA256',sha(p))
            normalized[node]=(name,value)
        stimuli.append(normalized)
    if decks[0]!=decks[1] or stimuli[0]!=stimuli[1]:raise ValueError('solver, observations, constant bias or waveform bytes changed')
    save(output,dict(input_sha256={str(f):sha(f) for f in files},all_primitive_and_passive_cards_identical=True,all_source_nodes_values_and_waveform_bytes_identical=True,all_solver_and_observation_settings_identical=True,only_resource_limit_changed=True,original_memory_gib=12,new_memory_gib=4,native_success_under_new_limit_unproven=True,release_ready=False));print('detector exported physics identical; only 12-to-4 GiB profile changed')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','target','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','target','output']))
