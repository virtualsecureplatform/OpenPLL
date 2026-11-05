"""Quantify native pre/post-R device parameter changes without accepting them."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
import json
from pathlib import Path
import re
import time
from common import save,sha
from prepare_spatial_devices import xcards
from resources import lease


def number(token):
    match=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([kKmMuUnNpPfF]?)',token)
    if not match:
        raise ValueError('unsupported native numeric parameter: '+token)
    scale={'':0,'k':3,'m':-3,'u':-6,'n':-9,'p':-12,'f':-15}[match[2].lower()]
    return D(match[1])*D(10)**scale


def run(extraction,output):
    extraction,out=extraction.resolve(),output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    domain=(extraction/'domain').resolve()
    proof=domain/'assessment.json'
    receipt=json.loads(proof.read_text())
    before,after=(domain/'trace'/n for n in ('pre_resistance.spice','retained_rc.spice'))
    helper=Path(__file__).with_name('prepare_spatial_devices.py')
    paths=[proof,before,after,helper,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(8,8,deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins=dict(zip(map(str,paths),pool.map(sha,paths)))
        for p in (before,after):
            if pins[str(p)]!=receipt['artifacts'][str(p)]:
                raise ValueError('native SPICE device source changed')
        with ThreadPoolExecutor(max_workers=2) as pool:
            pre,post=list(pool.map(xcards,(before,after)))
        if pre.keys()!=post.keys():
            raise ValueError('native device instance identities differ')
        counts,models=Counter(),Counter()
        sums={stage:{k:D(0) for k in ('ad','as','pd','ps')} for stage in ('pre_R','post_R')}
        changed=0
        ledger,cards=out/'parameter_differences.jsonl',out/'native_device_cards.jsonl'
        with ledger.open('w') as target,cards.open('w') as cache:
            for name in sorted(pre,key=lambda n:int(n[1:])):
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                    raise TimeoutError('native device parameter audit deadline')
                a,b=pre[name],post[name]
                ma=[i for i,t in enumerate(a) if t.startswith('sky130_fd_pr__')]
                mb=[i for i,t in enumerate(b) if t.startswith('sky130_fd_pr__')]
                if len(ma)!=1 or len(mb)!=1 or ma!=mb or a[ma[0]]!=b[mb[0]]:
                    raise ValueError('native model or port count changed')
                model=a[ma[0]]
                aa,bb=a[ma[0]+1:],b[mb[0]+1:]
                def params(tokens):
                    result={}
                    for token in tokens:
                        key,value=token.split('=',1)
                        if key in result:
                            raise ValueError('duplicate native device parameter')
                        result[key]=value
                    return result
                pa,pb=params(aa),params(bb)
                for stage,values in (('pre_R',pa),('post_R',pb)):
                    for key in sums[stage]:
                        sums[stage][key]+=number(values.get(key,'0'))
                difference={key:[pa.get(key),pb.get(key)] for key in sorted(pa.keys()|pb.keys())
                            if pa.get(key)!=pb.get(key)}
                cache.write(json.dumps([name,a,b])+'\n')
                if difference:
                    changed+=1
                    counts.update(difference.keys())
                    models[model]+=1
                    target.write(json.dumps(dict(instance=name,model=model,differences=difference))+'\n')
        if any(sha(Path(p))!=h for p,h in pins.items()):
            raise ValueError('native parameter delta source changed')
        total_delta={k:str(sums['post_R'][k]-sums['pre_R'][k]) for k in sums['pre_R']}
        save(out/'assessment.json',dict(input_sha256=pins,
             artifacts={str(p):sha(p) for p in (ledger,cards)},native_devices=len(pre),
             changed_parameter_devices=changed,changed_parameter_key_counts=dict(counts),
             changed_parameter_model_counts=dict(models),
             aggregate_junction_parameters={s:{k:str(v) for k,v in d.items()} for s,d in sums.items()},
             aggregate_post_minus_pre_junction_delta=total_delta,
             parameter_change_is_diagnostic_not_accepted=True,
             native_SPICE_device_parameter_and_terminal_join_verified=False,
             spatial_nonlinear_junction_assignment_qualified=False,runtime_model_eligible=False,
             physical_RC_qualified=False,release_qualified=False))
        print(json.dumps(dict(native_devices=len(pre),changed_parameter_devices=changed,
             changed_parameter_key_counts=dict(counts),aggregate_junction_delta=total_delta)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extraction',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    run(a.extraction,a.output)
