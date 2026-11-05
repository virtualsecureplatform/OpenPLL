"""Probe changed native source geometry only under original ideal D/S/B aliases."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import shlex
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def model_closure(first,deadline):
    pending,seen=[first],set()
    while pending:
        path=pending.pop().resolve()
        if path in seen:
            continue
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
            raise TimeoutError('model closure deadline')
        if not path.is_file():
            raise ValueError('missing model dependency: '+str(path))
        seen.add(path)
        for line in path.read_text().splitlines():
            text=line.strip()
            if not text or text.startswith('*'):
                continue
            tokens=shlex.split(text)
            if tokens[0].lower() not in ('.include','.inc','.lib') or (tokens[0].lower()=='.lib' and len(tokens)==2):
                continue
            pending.append(path.parent/tokens[1])
    return sorted(seen)


def table(path,columns,rows):
    text=path.read_text()
    if 'End of Xyce(TM) Simulation' not in text:
        raise ValueError('complete native probe table required')
    data=[list(map(float,line.split())) for line in text.splitlines()
          if line.split() and line.split()[0].isdigit()]
    if len(data)!=rows or any(len(row)!=columns+2 or not all(map(math.isfinite,row)) for row in data):
        raise ValueError('native probe table shape or finiteness differs')
    return data


def inside(config):
    cfg=json.loads(config.read_text())
    out=Path(cfg['output'])
    deadline=cfg['deadline_uptime']
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    binary=Path('/opt/xyce/bin/Xyce')
    model=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice')
    files=[binary,*model_closure(model,deadline)]
    pins={str(p):sha(p) for p in files}
    pairs=cfg['pairs']
    def point(case):
        corner,temperature=case
        root=out/f'{corner}_{temperature}'
        root.mkdir()
        names=[]
        # Model 0/1, alias/split sensitivity control, original/retained parameters.
        for m in range(2):
            for split in (0,1):
                for version in (0,1):
                    names.append((m,split,version,f'm{m}s{split}v{version}'))
        result={}
        for analysis in ('dc','ac'):
            deck=root/(analysis+'.cir')
            lines=[f'* Exact native two-device original-node alias probe: {corner} {temperature}',
                   f'.lib "{model}" {corner}',f'.options device temp={temperature} gmin=1e-18',
                   '.options nonlin reltol=1e-10 abstol=1e-20']
            if analysis=='dc':
                lines.append('Vdrive ctrl 0 0')
            quantities=['V(ctrl)'] if analysis=='dc' else []
            for m,split,version,name in names:
                original,retained=pairs[m]
                rail=0 if m==0 else 1.8
                source=rail+(0.2 if m==0 else -0.2)*split
                body=f'b{name}' if split else f's{name}'
                if analysis=='dc':
                    lines.append(f'VG{name} g{name} ctrl 0')
                    lines.append(f'VS{name} s{name} 0 {source:.17g}')
                    quantities.extend([f'I(VG{name})',f'I(VS{name})'])
                else:
                    gate=1.8 if m==0 else 0
                    lines.append(f'VG{name} g{name} 0 DC {gate} AC {1-split}')
                    lines.append(f'VS{name} s{name} 0 DC {source:.17g} AC {split}')
                    quantities.extend([f'IR(VG{name})',f'II(VG{name})',f'IR(VS{name})',f'II(VS{name})'])
                if split:
                    lines.append(f'VB{name} {body} 0 {rail}')
                card=original if version==0 else retained
                model_index=next(i for i,t in enumerate(card) if t.startswith('sky130_fd_pr__'))
                lines.append(' '.join([f'X{name}',f's{name}',f'g{name}',f's{name}',body,*card[model_index:]]))
            lines.append('.dc Vdrive 0 1.8 0.1' if analysis=='dc' else '.ac lin 2 1e6 4e8')
            lines.extend([f'.print {analysis} precision=16 '+' '.join(quantities),'.end'])
            deck.write_text('\n'.join(lines)+'\n')
            execute([binary,'-linsolv','KLU','-o',deck,deck],root/(analysis+'.log'),deadline,4)
            tables=[Path(str(deck)+suffix) for suffix in ('.prn','.FD.prn') if Path(str(deck)+suffix).exists()]
            if len(tables)!=1:
                raise ValueError('unique native probe data table required')
            result[analysis]=table(tables[0],len(quantities)-(analysis=='dc'),19 if analysis=='dc' else 2)
        worst=0.0
        checks=0
        sensitivities=[]
        for analysis,rows in result.items():
            width=2 if analysis=='dc' else 4
            for row in rows:
                for m in range(2):
                    pre_index=2+(m*4)*width
                    post_index=pre_index+width
                    for electrode in range(width):
                        a,b=row[pre_index+electrode],row[post_index+electrode]
                        error=abs(a-b)/max(abs(a),abs(b),1e-18)
                        worst=max(worst,error)
                        checks+=1
                        if abs(a-b)>1e-24+1e-12*max(abs(a),abs(b),1e-18):
                            raise ValueError(f'original ideal alias model response differs: {case} {analysis} {m} {error}')
                    if analysis=='ac':
                        a=2+(m*4+2)*width
                        b=a+width
                        difference=math.hypot(row[a+2]-row[b+2],row[a+3]-row[b+3])
                        if difference<=1e-9:
                            raise ValueError('split-node sensitivity control did not detect changed junction geometry')
                        sensitivities.append(difference)
        save(root/'result.json',dict(corner=corner,temperature_c=temperature,
             original_ideal_alias_response_controls_pass=True,scalar_response_comparisons=checks,
             maximum_scaled_response_delta=worst,split_node_control_current_deltas_a=sensitivities,
             physical_spatial_junction_allocation_qualified=False,release_qualified=False))
        return json.loads((root/'result.json').read_text())
    cases=[(c,t) for c in ('tt','ff','ss','sf','fs') for t in (-40,27,125)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(point,cases))
    if any(sha(Path(p))!=h for p,h in pins.items()):
        raise ValueError('native model/binary changed during alias probe')
    save(out/'native_assessment.json',dict(input_sha256=pins,results=results,
         original_ideal_DSB_alias_controls_pass=True,PVT_cases=len(cases),
         maximum_scaled_response_delta=max(r['maximum_scaled_response_delta'] for r in results),
         DC_gate_sweep_v=[0,1.8,0.1],AC_frequencies_hz=[1e6,4e8],
         comparator_absolute_current_floor_a=1e-24,comparator_scaled_limit=1e-12,
         comparator_reference_current_floor_a=1e-18,
         original_equation_residual_qualification=False,
         physical_spatial_junction_allocation_qualified=False,runtime_model_eligible=False,
         physical_RC_qualified=False,release_qualified=False))


def run(delta,fallback,output):
    delta,fallback,out=(p.resolve() for p in (delta,fallback,output))
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipts=[p/'assessment.json' for p in (delta,fallback)]
    difference,geometry=[json.loads(p.read_text()) for p in receipts]
    if not geometry['all_changed_native_parameter_devices_traced_to_whole_node_fallback']:
        raise ValueError('complete source fallback audit required')
    if geometry['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):
        raise ValueError('fallback/parameter delta lineage differs')
    cache=delta/'native_device_cards.jsonl'
    ids=[r['instance'] for r in json.loads((fallback/'whole_node_fallback_cases.json').read_text())]
    pairs={}
    with cache.open() as stream:
        for line in stream:
            name,a,b=json.loads(line)
            if name in ids:
                if len(a)<6 or a[1]!=a[3] or a[1]!=a[4]:
                    raise ValueError('original native device D/S/B must share the same conductor')
                pairs[name]=[a,b]
    if set(pairs)!=set(ids) or len(ids)!=2:
        raise ValueError('exact two changed native devices required')
    ordered=sorted(pairs.values(),key=lambda p:0 if '__nfet_' in p[0][5] else 1)
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    paths=[*receipts,cache,image,Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths}
    if pins[str(cache)]!=difference['artifacts'][str(cache)]:
        raise ValueError('paired native device cards changed')
    cfg=out/'config.json'
    save(cfg,dict(output=str(out),pairs=ordered,deadline_uptime=deadline))
    try:
        with lease(4,16,deadline):
            python='/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3'
            execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,python,
                     Path(__file__).resolve(),'--inside',cfg],out/'controller.log',deadline,16)
            if any(sha(Path(p))!=h for p,h in pins.items()):
                raise ValueError('alias probe input changed')
            native=out/'native_assessment.json'
            save(out/'assessment.json',dict(input_sha256=pins,
                 artifacts={str(p):sha(p) for p in [native,cfg,*out.glob('*/*.cir'),
                    *out.glob('*/*.log'),*out.glob('*/*.prn'),*out.glob('*/result.json')]},
                 **{k:v for k,v in json.loads(native.read_text()).items() if k!='input_sha256'}))
            print(json.dumps(dict(original_ideal_alias_controls_pass=True,PVT_cases=15)))
    except BaseException as error:
        save(out/'failure.json',dict(reason=repr(error),physical_RC_qualified=False,release_qualified=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inside',type=Path)
    parser.add_argument('--delta',type=Path)
    parser.add_argument('--fallback',type=Path)
    parser.add_argument('--output',type=Path)
    a=parser.parse_args()
    if a.inside:
        inside(a.inside)
    else:
        run(a.delta,a.fallback,a.output)
