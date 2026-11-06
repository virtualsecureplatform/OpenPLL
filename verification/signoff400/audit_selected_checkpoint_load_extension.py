"""Audit a larger physical clock-load partition against its checkpoint baseline."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources

def device_parts(text):
    definitions=[];cards={};depth=0;last=None
    for line in text.splitlines():
        f=line.split()
        if not f or f[0].startswith('*'):continue
        kind=f[0].lower()
        if kind=='.subckt':depth+=1
        if depth or kind.startswith('.'):
            definitions.append(line.strip());last=None
        elif kind=='+':
            if last is None:definitions.append(line.strip())
            else:cards[last]+='\n'+line.strip()
        else:
            if f[0]in cards:raise ValueError('duplicate top-level physical device')
            cards[f[0]]=line.strip();last=f[0]
        if kind=='.ends':depth-=1
        if depth<0:raise ValueError('unbalanced subcircuits')
    if depth:raise ValueError('unbalanced subcircuits')
    return definitions,cards

def extension(before,after):
    da,a=device_parts(before);db,b=device_parts(after)
    if da!=db:raise ValueError('device definitions or model directives differ')
    if any(b.get(n)!=card for n,card in a.items()):raise ValueError('original physical card removed or changed')
    added=b.keys()-a.keys()
    if not added:raise ValueError('strict larger physical circuit required')
    return dict(added_cards=len(added),added_nonlinear_cards=sum(n[0].upper()not in ('R','C')for n in added),added_passive_cards=sum(n[0].upper()in ('R','C')for n in added))

def ic(path):
    result={}
    for line in path.read_text().splitlines():
        m=re.fullmatch(r'\.IC V\(([^)]+)\)=(\S+)',line)
        if not m or m[1]in result:raise ValueError('unique private voltage initializations required')
        result[m[1]]=m[2]
    return result

def run(baseline,candidate,output):
    if output.exists():raise FileExistsError(output)
    manifests=[json.loads((p/'manifest.json').read_text())for p in(baseline,candidate)]
    for m in manifests:verify(m['input_sha256'])
    a,b=manifests
    for key in ('controls','operating_point','observed_roles','native_checkpoint_time_s','simulation_end_s','DCOP_skipped','reset_additional_uniform_voltage_error_v'):
        if a[key]!=b[key]:raise ValueError('checkpoint condition differs: '+key)
    result=extension((baseline/'devices.spice').read_text(),(candidate/'devices.spice').read_text())
    x,y=[ic(p/'initial_conditions.spice')for p in(baseline,candidate)]
    if any(y.get(n)!=v for n,v in x.items()):raise ValueError('old private voltage changed or omitted')
    if len(x)!=a['initialized_private_nodes']or len(y)!=b['initialized_private_nodes']:raise ValueError('initialized node inventory differs')
    xsrc,ysrc=[sources(p/'sources.spice')for p in(baseline,candidate)]
    removed=xsrc.keys()-ysrc.keys();added=ysrc.keys()-xsrc.keys()
    if not removed<=y.keys()-x.keys():raise ValueError('removed prescribed node did not become a new private voltage')
    if set(ysrc)&x.keys():raise ValueError('old private node is now clamped')
    paths=[Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]
    for node in xsrc.keys()&ysrc.keys():
        left,right=xsrc[node][1],ysrc[node][1]
        pair=[re.fullmatch(r'PWL FILE "([^"]+)"',s)for s in(left,right)]
        if any(pair):
            if not all(pair):raise ValueError('common source type changed')
            p,q=[Path(m[1])for m in pair];paths.extend([p,q])
            if sha(p)!=sha(q):raise ValueError('shared programming/reset waveform changed')
        elif left!=right:raise ValueError('shared quiet or supply voltage changed')
    def deck(folder):
        text=(folder/'control.spice').read_text()
        for name in ('devices.spice','sources.spice','initial_conditions.spice','control.raw'):text=text.replace(str(folder/name),'<'+name+'>')
        return text
    if deck(baseline)!=deck(candidate):raise ValueError('solver or simulation protocol changed')
    paths.extend(p/n for p in(baseline,candidate)for n in('manifest.json','devices.spice','sources.spice','initial_conditions.spice','control.spice'))
    pins={str(p):sha(p)for p in paths};verify(pins)
    save(output,dict(input_sha256=pins,**result,original_cards_and_private_voltage_values_preserved=True,
        new_private_voltage_nodes=len(y.keys()-x.keys()),prescribed_nodes_now_private=len(removed),new_quiet_boundary_nodes=len(added),
        common_boundary_waveforms_and_quiet_voltages_identical=True,same_solver_and_checkpoint_protocol=True,
        scope='Physical partition extension only. New clock drivers and incident passives replace eight held exterior nodes with initialized private unknowns; new exterior quiet nodes remain prescribed. Frequency/phase sensitivity is pending.',
        partition_uncertainty_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('baseline','candidate','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in('baseline','candidate','output')))
