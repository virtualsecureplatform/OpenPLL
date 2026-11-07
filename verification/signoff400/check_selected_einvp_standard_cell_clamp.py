"""Test an existing e-inverter cell as a conditional high keeper; no layout ECO."""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from run_selected_einvp_window_replay_v2 import run as simulate
from assess_selected_einvp_window_replay import read
from check_selected_einvp_disabled_clamps import extents


def add_cells(text,cells):
    marker='.ends selected_einvp_cut\n'
    if text.count(marker)!=1:raise ValueError('unique cut end required')
    calls={}
    for line in text.splitlines():
        f=line.split()
        if f and f[0].startswith('Xflat'):
            if len(f)!=6:raise ValueError('literal four-terminal MOS required')
            calls[f[0]]=f
    added=[];newnodes=[];lines=[]
    for i,cell in enumerate(cells):
        local=cell['local_to_native_nodes']
        if any(len(v)!=1 for v in local.values()):raise ValueError('unique cell nodes required')
        local={k:v[0]for k,v in local.items()}
        replacements={local['Z']:local['Z'],local['A']:local['VGND'],local['TE']:local['a_27_47#'],local['VPWR']:local['VPWR'],local['VGND']:local['VGND']}
        for label,suffix in [('a_27_47#','enb'),('a_204_47#','n'),('a_276_297#','p')]:
            name='__openpll_keeper_%d_%s'%(i,suffix)
            if name in text:raise ValueError('new node collision')
            replacements[local[label]]=name;newnodes.append(name)
        names=cell['flat_MOS_instances']
        if len(names)!=6 or len(set(names))!=6:raise ValueError('six original cell devices required')
        for j,name in enumerate(names):
            f=calls[name];terminals=[replacements[n]for n in f[1:5]];instance='Xkeeper_%d_%d'%(i,j)
            lines.append(instance+' '+' '.join(terminals)+' '+f[5]+'\n');added.append(dict(instance=instance,terminals=terminals,leaf=f[5]))
    return text.replace(marker,''.join(lines)+marker),added,newnodes


def run(prepared,inspection,binary,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{21});output.mkdir(parents=True)
    pp=prepared/'assessment.json';p,physical=[json.loads(x.read_text())for x in [pp,inspection]]
    for a in [p,physical]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    cuts=[Path(x)for x in p['input_sha256']if x.endswith('/assessment.json')]
    if len(cuts)!=1:raise ValueError('unique original cut required')
    cut=json.loads(cuts[0].read_text());verify(cut['input_sha256']);verify(cut['artifacts'])
    if cut['input_sha256'].get(str(inspection))!=sha(inspection):raise ValueError('same physical cell inspection required')
    original=cuts[0].parent/'cut.spice';text=original.read_text();modified,added,newnodes=add_cells(text,physical['cells'])
    folder=output/'prepared';folder.mkdir();newcut=folder/'cut.spice';newcut.write_text(modified)
    files=[pp,inspection,cuts[0],original,binary,Path(__file__).resolve()]
    files += [Path(__file__).with_name(n)for n in ['common_v3.py','resources.py','run_selected_einvp_window_replay_v2.py','assess_selected_einvp_window_replay.py','check_selected_einvp_disabled_clamps.py']]
    pins={str(f):sha(f)for f in files};artifacts={str(newcut):sha(newcut),str(prepared/'boundaries.spice'):sha(prepared/'boundaries.spice')}
    for label in ['base','refined']:
        deck=folder/(label+'.spice');lines=(prepared/(label+'.spice')).read_text().replace(str(original),str(newcut)).replace(str(prepared/(label+'.csv')),str(folder/(label+'.csv'))).splitlines(True)
        lines=[line.rstrip('\n')+' '+' '.join('V(Xcut:%s)'%n for n in newnodes)+'\n'if line.startswith('.PRINT ')else line for line in lines]
        deck.write_text(''.join(lines));artifacts[str(deck)]=sha(deck)
    receipt=folder/'assessment.json'
    save(receipt,dict(input_sha256=pins,artifacts=artifacts,proposal='two_additional_sky130_fd_sc_hd__einvp_1',keeper_input='VGND',keeper_TE='original_internal_enable_complement',keeper_Z='original_Z',added_MOS=added,new_internal_nodes=newnodes,original_MOS_and_RC_unchanged=True,new_cell_extracted_parasitics_included=False,enabled_operation_qualified=False,layout_changed=False,release_ready=False))
    protocol=output/'protocol.json';save(protocol,dict(input_sha256=pins,prepared=str(receipt),prepared_sha256=sha(receipt),maximum_steps_ps=[.5,.25],comparison_window_ns=[202.5,210],release_ready=False))
    save(output/'status.json',dict(state='conditional_standard_cell_keeper_running',release_ready=False));simulate(folder,binary,output/'runs')
    rpath=output/'runs/assessment.json';r=json.loads(rpath.read_text());summaries={}
    if r['both_predeclared_runs_completed']:
        originals=[]
        for line in text.splitlines():
            f=line.split()
            if f and f[0].startswith('Xflat'):originals.append(dict(instance=f[0],terminals=f[1:5],leaf=f[5]))
        rc,reference=read(prepared/'recorded.csv')
        for label in ['base','refined']:
            cc,rows=read(folder/(label+'.csv'));summaries[label]=extents(cc,rows,rc,reference,originals+added)
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(x):sha(x)for x in [receipt,protocol,rpath]},both_runs_completed=r['both_predeclared_runs_completed'],device_terminal_ranges_V=summaries,added_MOS_count=len(added),new_internal_nodes=newnodes,conditional_disabled_window_only=True,new_cell_extracted_parasitics_included=False,enabled_operation_qualified=False,startup_qualified=False,frequency_or_input_loading_qualified=False,layout_changed=False,model_validity_ranges_qualified=False,electrical_rules_qualified=False,reliability_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='conditional_standard_cell_keeper_assessed',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prepared','inspection','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.prepared.resolve(),a.inspection.resolve(),a.binary.resolve(),a.output.resolve())
