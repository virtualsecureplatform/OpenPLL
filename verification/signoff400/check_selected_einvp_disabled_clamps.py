"""Compare two inactive-output clamp proposals in a retained-boundary replay only."""
import argparse,bisect,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from assess_selected_einvp_window_replay import read
from run_selected_einvp_window_replay_v2 import run as simulate


def add_clamps(text,cells,kind):
    if kind not in ['nfet_to_ground','pfet_to_supply']:raise ValueError('predeclared clamp kind required')
    marker='.ends selected_einvp_cut\n'
    if text.count(marker)!=1:raise ValueError('unique cut end required')
    cards=[];nodes=[]
    def node(cell,pin):
        values=cell['local_to_native_nodes'][pin]
        if len(values)!=1:raise ValueError('unique physical terminal required')
        return values[0]
    for i,cell in enumerate(cells):
        if kind=='nfet_to_ground':
            terminals=[node(cell,'Z'),node(cell,'a_27_47#'),node(cell,'VGND'),node(cell,'VNB')];leaf='__openpll_literal_leaf_5'
        else:
            terminals=[node(cell,'Z'),node(cell,'TE'),node(cell,'VPWR'),node(cell,'VPB')];leaf='__openpll_literal_leaf_2'
        if '.subckt '+leaf+' ' not in text:raise ValueError('existing literal geometry wrapper required')
        cards.append('Xdisabled_clamp%d '%i+' '.join(terminals)+' '+leaf+'\n')
        nodes.append(dict(instance='Xdisabled_clamp%d'%i,terminals=terminals,leaf=leaf,cell=cell['cell']))
    return text.replace(marker,''.join(cards)+marker),nodes


def extents(columns,rows,recorded_columns,recorded,instances):
    times=[r[0]for r in recorded];observed={c.lower():i for i,c in enumerate(columns)};ri={c:i for i,c in enumerate(recorded_columns)}
    results={};relations={'DS':(0,2),'GS':(1,2),'GD':(1,0),'GB':(1,3),'BS':(3,2),'BD':(3,0)}
    for row in rows:
        if row[0]<2.5e-9:continue
        j=max(0,min(len(times)-2,bisect.bisect_right(times,row[0])-1));left,right=recorded[j:j+2];fraction=(row[0]-left[0])/(right[0]-left[0])
        def voltage(n):
            if n=='0':return 0.
            key=('v(xcut:'+n+')').lower()
            if key in observed:return row[observed[key]]
            k=ri[n];return left[k]+fraction*(right[k]-left[k])
        for instance in instances:
            values=[voltage(n)for n in instance['terminals']];target=results.setdefault(instance['instance'],{})
            for name,(a,b)in relations.items():
                v=values[a]-values[b]
                if name not in target:target[name]=[v,v]
                else:target[name]=[min(target[name][0],v),max(target[name][1],v)]
    return results


def run(prepared,inspection,binary,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{21});output.mkdir(parents=True)
    pp=prepared/'assessment.json';p,physical=[json.loads(x.read_text())for x in [pp,inspection]]
    for a in [p,physical]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    cuts=[Path(x)for x in p['input_sha256']if x.endswith('/assessment.json')]
    if len(cuts)!=1:raise ValueError('unique original cut required')
    cut=json.loads(cuts[0].read_text());verify(cut['input_sha256']);verify(cut['artifacts'])
    if cut['input_sha256'].get(str(inspection))!=sha(inspection):raise ValueError('same physical cell inspection required')
    original=cuts[0].parent/'cut.spice';text=original.read_text();instances=[]
    for line in text.splitlines():
        f=line.split()
        if f and f[0].startswith('Xflat'):
            if len(f)!=6:raise ValueError('literal four-terminal MOS calls required')
            instances.append(dict(instance=f[0],terminals=f[1:5],leaf=f[5]))
    if len(instances)!=12:raise ValueError('original twelve-MOS cut required')
    files=[pp,inspection,cuts[0],original,binary,Path(__file__).resolve()]
    files += [Path(__file__).with_name(n)for n in ['common_v3.py','assess_selected_einvp_window_replay.py','run_selected_einvp_window_replay_v2.py','resources.py']]
    pins={str(f):sha(f)for f in files};plans=[]
    for kind in ['nfet_to_ground','pfet_to_supply']:
        folder=output/kind;folder.mkdir();newcut=folder/'cut.spice';modified,added=add_clamps(text,physical['cells'],kind);newcut.write_text(modified)
        artifacts={str(newcut):sha(newcut),str(prepared/'boundaries.spice'):sha(prepared/'boundaries.spice')}
        for label in ['base','refined']:
            deck=folder/(label+'.spice');deck.write_text((prepared/(label+'.spice')).read_text().replace(str(original),str(newcut)).replace(str(prepared/(label+'.csv')),str(folder/(label+'.csv'))));artifacts[str(deck)]=sha(deck)
        receipt=folder/'assessment.json';save(receipt,dict(input_sha256=pins,artifacts=artifacts,proposal=kind,original_MOS_geometry_and_RC_unchanged=True,added_MOS=added,recorded_boundaries_unchanged=True,physical_layout_changed=False,enabled_operation_checked=False,release_ready=False))
        plans.append(dict(kind=kind,prepared=str(folder),prepared_receipt_sha256=sha(receipt),runs=str(folder/'runs'),added_MOS=added))
    protocol=output/'protocol.json';save(protocol,dict(input_sha256=pins,plans=plans,maximum_steps_ps=[.5,.25],comparison_window_ns=[202.5,210],original_initial_voltages_retained=True,startup_and_enabled_operation_qualified=False,release_ready=False))
    results={};rc,reference=read(prepared/'recorded.csv')
    for plan in plans:
        verify(pins);folder=Path(plan['prepared'])
        if sha(folder/'assessment.json')!=plan['prepared_receipt_sha256']:raise ValueError('predeclared proposal changed')
        save(output/'status.json',dict(state='conditional_clamp_proposal_running',proposal=plan['kind'],release_ready=False))
        simulate(folder,binary,folder/'runs')
        assessed=json.loads((folder/'runs/assessment.json').read_text())
        if not assessed['both_predeclared_runs_completed']:results[plan['kind']]=dict(normal_completion=False);break
        summaries={}
        for label in ['base','refined']:
            cc,rows=read(folder/(label+'.csv'));summaries[label]=extents(cc,rows,rc,reference,instances+plan['added_MOS'])
        results[plan['kind']]=dict(normal_completion=True,device_terminal_ranges_V=summaries,added_MOS=plan['added_MOS'])
    artifacts={str(protocol):sha(protocol)}
    for plan in plans:
        f=Path(plan['runs'])/'assessment.json'
        if f.exists():artifacts[str(f)]=sha(f)
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,proposals=results,both_proposals_completed=len(results)==2 and all(r['normal_completion']for r in results.values()),comparison_window_ns=[202.5,210],conditional_disabled_window_only=True,original_initial_above_rail_state_retained=True,enabled_operation_qualified=False,startup_qualified=False,frequency_or_input_loading_qualified=False,layout_changed=False,model_validity_ranges_qualified=False,reliability_qualified=False,electrical_rules_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='conditional_clamp_proposals_assessed',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prepared','inspection','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.prepared.resolve(),a.inspection.resolve(),a.binary.resolve(),a.output.resolve())
