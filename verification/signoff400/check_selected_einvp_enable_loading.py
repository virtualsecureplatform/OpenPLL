"""Compare original/keeper cells under a predeclared conditional TE pulse."""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from run_selected_einvp_window_replay_v2 import run as simulate
from assess_selected_einvp_window_replay import read,compare


def replace_enables(text,nodes):
    lines=[];sources={};replacing=False;found=set()
    for line in text.splitlines(True):
        f=line.split()
        if f and f[0].startswith('Vboundary'):
            replacing=False
            if len(f)!=4 or f[2]!='0' or f[3]!='PWL(':raise ValueError('expected retained PWL source header')
            sources[f[1]]=f[0]
            if f[1]in nodes:
                if f[1]in found:raise ValueError('unique TE source required')
                found.add(f[1]);replacing=True
                lines.append(f[0]+' '+f[1]+' 0 PWL(0 0 2n 0 2.1n 1.8 7n 1.8 7.1n 0 10n 0)\n');continue
        if not replacing:lines.append(line)
    if found!=set(nodes):raise ValueError('every TE waveform must be replaced')
    return ''.join(lines),sources


def integrate(columns,rows,voltage,current,start,end):
    vi=[c.lower()for c in columns].index(voltage.lower());ii=[c.lower()for c in columns].index(current.lower())
    energy=charge=absolute=0.;peak=0.
    for left,right in zip(rows,rows[1:]):
        lo=max(start,left[0]);hi=min(end,right[0])
        if hi<=lo:continue
        def at(t,index):return left[index]+(right[index]-left[index])*(t-left[0])/(right[0]-left[0])
        v0,v1=at(lo,vi),at(hi,vi);i0,i1=at(lo,ii),at(hi,ii);dt=hi-lo
        # Exact product integral for piecewise-linear V and I, into the cut.
        energy-=dt*(2*v0*i0+v0*i1+v1*i0+2*v1*i1)/6
        charge-=dt*(i0+i1)/2
        if i0*i1<0:absolute+=dt*(i0*i0+i1*i1)/(2*(abs(i0)+abs(i1)))
        else:absolute+=dt*(abs(i0)+abs(i1))/2
        peak=max(peak,abs(i0),abs(i1))
    return dict(energy_supplied_fJ=energy*1e15,net_charge_supplied_fC=charge*1e15,absolute_charge_fC=absolute*1e15,peak_absolute_current_A=peak)


def run(original,keeper,inspection,binary,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{21});output.mkdir(parents=True)
    op=original/'assessment.json';kp=keeper/'prepared/assessment.json';ir=inspection
    o,k,physical=[json.loads(p.read_text())for p in [op,kp,ir]]
    for a in [o,k,physical]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    cuts=[Path(x)for x in o['input_sha256']if x.endswith('/assessment.json')]
    if len(cuts)!=1:raise ValueError('unique original cut required')
    cut=json.loads(cuts[0].read_text());verify(cut['input_sha256']);verify(cut['artifacts'])
    if cut['input_sha256'].get(str(ir))!=sha(ir) or k.get('internal_original_enable_complement_tapped')is not False:raise ValueError('matching inspected cells and external-pin-only keeper required')
    cells=physical['cells'];te={cell['local_to_native_nodes']['TE'][0]for cell in cells};boundaries=original/'boundaries.spice'
    text,sources=replace_enables(boundaries.read_text(),te);newboundary=output/'boundaries.spice';newboundary.write_text(text)
    roles={'supply':'VPWR'}
    for i,cell in enumerate(cells):
        for pin in ['A','TE']:roles['cell%d_%s'%(i,pin)]=cell['local_to_native_nodes'][pin][0]
    if not all(n in sources for n in roles.values()):raise ValueError('all current measurement sources required')
    files=[op,kp,ir,cuts[0],boundaries,binary,Path(__file__).resolve()]
    files += [Path(__file__).with_name(n)for n in ['common_v3.py','resources.py','run_selected_einvp_window_replay_v2.py','assess_selected_einvp_window_replay.py']]
    pins={str(p):sha(p)for p in files};plans=[]
    for name,source in [('original',original),('external_keeper',keeper/'prepared')]:
        folder=output/name;folder.mkdir();artifacts={str(newboundary):sha(newboundary)}
        model=cuts[0].parent/'cut.spice'if name=='original'else source/'cut.spice';artifacts[str(model)]=sha(model)
        for label in ['base','refined']:
            deck=folder/(label+'.spice');lines=(source/(label+'.spice')).read_text().replace(str(boundaries),str(newboundary)).replace(str(source/(label+'.csv')),str(folder/(label+'.csv'))).splitlines(True)
            vectors=' '.join('V(%s) I(%s)'%(node,sources[node])for node in dict.fromkeys(roles.values()))
            deck.write_text(''.join(line.rstrip('\n')+' '+vectors+'\n'if line.startswith('.PRINT ')else line for line in lines));artifacts[str(deck)]=sha(deck)
        receipt=folder/'assessment.json';save(receipt,dict(input_sha256=pins,artifacts=artifacts,variant=name,TE_pulse_ns=[2,2.1,7,7.1],recorded_A_and_other_boundaries_unchanged=True,outside_control_network_not_resimulated=True,layout_changed=False,release_ready=False));plans.append(dict(name=name,folder=str(folder),prepared_sha256=sha(receipt)))
    protocol=output/'protocol.json';save(protocol,dict(input_sha256=pins,plans=plans,enable_transition_duration_ns=.1,enabled_comparison_ns=[2.6,6.8],disabled_comparison_ns=[7.6,10],transition_windows_ns=[[1.8,2.4],[6.8,7.4]],current_measurement_roles=roles,release_ready=False))
    results={};artifacts={str(protocol):sha(protocol)};datasets={}
    windows={'enabled':(2.6e-9,6.8e-9),'disabled':(7.6e-9,10e-9),'assert_transition':(1.8e-9,2.4e-9),'withdraw_transition':(6.8e-9,7.4e-9)}
    for plan in plans:
        folder=Path(plan['folder']);verify(pins)
        if sha(folder/'assessment.json')!=plan['prepared_sha256']:raise ValueError('predeclared decks changed')
        save(output/'status.json',dict(state='conditional_enable_loading_running',variant=plan['name'],release_ready=False));simulate(folder,binary,folder/'runs')
        rp=folder/'runs/assessment.json';r=json.loads(rp.read_text());artifacts[str(rp)]=sha(rp)
        if not r['both_predeclared_runs_completed']:results[plan['name']]=dict(normal_completion=False);break
        summaries={}
        for label in ['base','refined']:
            path=folder/(label+'.csv');cc,rows=read(path);artifacts[str(path)]=sha(path);datasets[(plan['name'],label)]=(cc,rows)
            summaries[label]={window:{role:integrate(cc,rows,'V('+node+')','I('+sources[node]+')',lo,hi)for role,node in roles.items()}for window,(lo,hi)in windows.items()}
        results[plan['name']]=dict(normal_completion=True,current_and_energy=summaries)
    comparison={}
    if len(results)==2 and all(r['normal_completion']for r in results.values()):
        bc,base=datasets[('original','refined')];kc,new=datasets[('external_keeper','refined')]
        for cell in cells:
            key='V(Xcut:'+cell['output_node']+')';bi=[x.lower()for x in bc].index(key.lower());ki=[x.lower()for x in kc].index(key.lower())
            comparison[cell['output_node']]={}
            for window,(lo,hi)in windows.items():
                selected=[row for row in new if lo<=row[0]<=hi]
                comparison[cell['output_node']][window]=compare(base,selected,bi,ki,lo)
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,variants=results,output_comparisons=comparison,both_variants_completed=len(results)==2 and all(r['normal_completion']for r in results.values()),current_sign_convention='negative ideal-source branch current supplies charge/energy into cut',conditional_synthetic_enable_pulse_only=True,physical_control_network_and_added_parasitics_not_resimulated=True,original_initial_above_rail_state_not_qualified=True,enabled_logic_or_timing_qualified=False,PLL_frequency_shift_qualified=False,physical_design_candidate_selected=False,electrical_rules_qualified=False,reliability_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='conditional_enable_loading_assessed',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['original','keeper','inspection','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.original.resolve(),a.keeper.resolve(),a.inspection.resolve(),a.binary.resolve(),a.output.resolve())
