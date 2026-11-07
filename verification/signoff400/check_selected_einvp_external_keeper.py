"""Use only standard-cell boundary pins: an external inverter drives each keeper."""
import argparse,json,os
from fractions import Fraction
from pathlib import Path
from common_v3 import save,sha,verify
from check_selected_einvp_standard_cell_clamp import add_cells
from check_selected_einvp_disabled_clamps import extents
from run_selected_einvp_window_replay_v2 import run as simulate
from assess_selected_einvp_window_replay import read


def add_inverters(text,cells,group,definitions,calls):
    if len(group)!=4 or any(r['leaf_master']!='sky130_fd_sc_hs__inv_2'for r in group):raise ValueError('complete four-MOS HS inverter required')
    newnodes=[];added=[];newdefs={}
    for i,cell in enumerate(cells):
        local={k:v[0]for k,v in cell['local_to_native_nodes'].items()if len(v)==1}
        enb='__openpll_external_enb_%d'%i
        if enb in text:raise ValueError('external inverter node collision')
        newnodes.append(enb);ports=dict(A=local['TE'],Y=enb,VGND=local['VGND'],VNB=local['VNB'],VPWR=local['VPWR'],VPB=local['VPB'])
        for j,row in enumerate(group):
            name=row['instance'];leaf=calls[name][-1];block=definitions[leaf];f=block[1].split();family,pins,parameters=row['local_primitive_signature']
            actual={k:Fraction(v)for k,v in (x.split('=',1)for x in f[6:])};expected={k:Fraction(v)for k,v in parameters}
            if len(block)!=3 or f[:5]!=['Xdevice','p0','p1','p2','p3']or f[5]!=family or actual!=expected:raise ValueError('exact physical inverter geometry required')
            newdefs[leaf]=block;terminals=[ports[p]for p in pins];instance='Xexternal_inv_%d_%d'%(i,j)
            added.append(dict(instance=instance,terminals=terminals,leaf=leaf))
        lines=[]
        for line in text.splitlines(True):
            f=line.split()
            if f and f[0].startswith('Xkeeper_%d_'%i):
                f=[f[0]]+[enb if x==local['a_27_47#']else x for x in f[1:5]]+[f[5]];line=' '.join(f)+'\n'
            lines.append(line)
        text=''.join(lines)
    marker='.ends selected_einvp_cut\n'
    if text.count(marker)!=1:raise ValueError('unique cut end required')
    lines=''.join(r['instance']+' '+' '.join(r['terminals'])+' '+r['leaf']+'\n'for r in added)
    return ''.join(''.join(block)for block in newdefs.values())+text.replace(marker,lines+marker),added,newnodes


def run(prepared,inspection,binary,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{21});output.mkdir(parents=True)
    pp=prepared/'assessment.json';p,physical=[json.loads(x.read_text())for x in [pp,inspection]]
    for a in [p,physical]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    cuts=[Path(x)for x in p['input_sha256']if x.endswith('/assessment.json')]
    if len(cuts)!=1:raise ValueError('unique original cut required')
    cut=json.loads(cuts[0].read_text());verify(cut['input_sha256']);verify(cut['artifacts'])
    if cut['input_sha256'].get(str(inspection))!=sha(inspection):raise ValueError('same physical inspection required')
    np=Path(next(x for x in physical['input_sha256']if x.endswith('/nodes.json')));metadata=json.loads(np.read_text());rows=metadata['physical_instances'];seed=next(r for r in rows if r['leaf_master']=='sky130_fd_sc_hs__inv_2');group=[r for r in rows if r['leaf_master']==seed['leaf_master']and r['physical_hierarchy_identity']==seed['physical_hierarchy_identity']]
    full=Path(next(x for x in physical['input_sha256']if x.endswith('/model.spice')));definitions={};calls={};current=None;required={r['instance']for r in group}
    for line in full.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt'and f[1].startswith('__openpll_literal_leaf_'):current=f[1];definitions[current]=[line];continue
        if current is not None:
            definitions[current].append(line)
            if f[0].lower()=='.ends':current=None
        if f[0]in required:calls[f[0]]=f
    original=cuts[0].parent/'cut.spice';text,keepers,keepernodes=add_cells(original.read_text(),physical['cells']);text,inverters,invnodes=add_inverters(text,physical['cells'],group,definitions,calls);newnodes=keepernodes+invnodes
    folder=output/'prepared';folder.mkdir();newcut=folder/'cut.spice';newcut.write_text(text)
    files=[pp,inspection,cuts[0],original,np,full,binary,Path(__file__).resolve()]
    files += [Path(__file__).with_name(n)for n in ['common_v3.py','resources.py','check_selected_einvp_standard_cell_clamp.py','check_selected_einvp_disabled_clamps.py','run_selected_einvp_window_replay_v2.py','assess_selected_einvp_window_replay.py']]
    pins={str(f):sha(f)for f in files};artifacts={str(newcut):sha(newcut),str(prepared/'boundaries.spice'):sha(prepared/'boundaries.spice')}
    for label in ['base','refined']:
        deck=folder/(label+'.spice');lines=(prepared/(label+'.spice')).read_text().replace(str(original),str(newcut)).replace(str(prepared/(label+'.csv')),str(folder/(label+'.csv'))).splitlines(True)
        deck.write_text(''.join(line.rstrip('\n')+' '+' '.join('V(Xcut:%s)'%n for n in newnodes)+'\n'if line.startswith('.PRINT ')else line for line in lines));artifacts[str(deck)]=sha(deck)
    receipt=folder/'assessment.json';save(receipt,dict(input_sha256=pins,artifacts=artifacts,keeper_master='sky130_fd_sc_hd__einvp_1',external_inverter_master='sky130_fd_sc_hs__inv_2',instances_per_master=2,internal_original_enable_complement_tapped=False,keeper_input='VGND',external_inverter_input='original_TE',keeper_TE='external_inverter_Y',keeper_Z='original_Z',added_MOS_count=len(keepers)+len(inverters),new_cell_extracted_parasitics_included=False,layout_changed=False,release_ready=False))
    protocol=output/'protocol.json';save(protocol,dict(input_sha256=pins,prepared=str(receipt),prepared_sha256=sha(receipt),maximum_steps_ps=[.5,.25],comparison_window_ns=[202.5,210],release_ready=False))
    save(output/'status.json',dict(state='conditional_external_keeper_running',release_ready=False));simulate(folder,binary,output/'runs')
    rp=output/'runs/assessment.json';r=json.loads(rp.read_text());summaries={}
    if r['both_predeclared_runs_completed']:
        instances=[]
        for line in text.splitlines():
            f=line.split()
            if f and f[0].startswith(('Xflat','Xkeeper_','Xexternal_inv_')):instances.append(dict(instance=f[0],terminals=f[1:5],leaf=f[5]))
        if len(instances)!=32:raise ValueError('32 MOS in external keeper proposal required')
        rc,reference=read(prepared/'recorded.csv')
        for label in ['base','refined']:
            cc,data=read(folder/(label+'.csv'));summaries[label]=extents(cc,data,rc,reference,instances)
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(f):sha(f)for f in [receipt,protocol,rp]},both_runs_completed=r['both_predeclared_runs_completed'],device_terminal_ranges_V=summaries,internal_original_enable_complement_tapped=False,added_standard_cells=dict(sky130_fd_sc_hd__einvp_1=2,sky130_fd_sc_hs__inv_2=2),new_cell_extracted_parasitics_included=False,conditional_disabled_window_only=True,enabled_operation_qualified=False,startup_qualified=False,frequency_or_input_loading_qualified=False,layout_changed=False,model_validity_ranges_qualified=False,electrical_rules_qualified=False,reliability_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='conditional_external_keeper_assessed',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prepared','inspection','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.prepared.resolve(),a.inspection.resolve(),a.binary.resolve(),a.output.resolve())
