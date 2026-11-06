"""Challenge reuse of an actual fine111 checkpoint for a different fine code.

Physical programming inputs ramp while reset remains asserted. All private
voltages still come from fine111. No target-code state or qualified model is
invented; compare this experiment against an independent full-native target.
"""
import argparse,bisect,json,math,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from selected_native_clock_shapes import load
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency
from run_selected_dco_real_driver_control_v5 import programming_sources


def interpolate(rows,t):
    j=bisect.bisect_left([x for x,v in rows],t)
    if j<len(rows)and rows[j][0]==t:return rows[j][1]
    if not 0<j<len(rows):raise ValueError('waveform must enclose requested time')
    a,v=rows[j-1];b,w=rows[j];return v+(w-v)*(t-a)/(b-a)


def retarget(rows,initial,final):
    if initial not in(0.,1.8)or final not in(0.,1.8)or initial==final:raise ValueError('opposite supported programming levels required')
    if not rows or rows[0][0]!=0 or rows[-1][0]<=1.5e-9 or any(not math.isfinite(t)or not math.isfinite(v)for t,v in rows):raise ValueError('finite complete original programming history required')
    if any(a[0]>=b[0]for a,b in zip(rows,rows[1:]))or any(abs(v-initial)>.18 for t,v in rows):raise ValueError('settled original programming history required')
    return [(t,v)for t,v in rows if t<.5e-9]+[(.5e-9,interpolate(rows,.5e-9)),(1.5e-9,final),(rows[-1][0],final)]


def run(baseline,inventory,output,cpu,fine):
    if cpu not in range(16,32):raise ValueError('spare physical core required')
    os.sched_setaffinity(0,{cpu});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'status.json',dict(state='preparing_checkpoint_retarget',release_ready=False))
    try:
        m=json.loads((baseline/'manifest.json').read_text());verify(m['input_sha256'])
        if json.loads((baseline/'status.json').read_text())['state']!='saved_state_DCO_diagnostic_complete':raise ValueError('normally completed saved-state baseline required')
        if m['controls']['coarse']!=20 or m['controls']['fine']!=111 or m['operating_point']!={'corner':'tt','supply_v':1.8,'temperature_c':27}:raise ValueError('measured TT coarse20/fine111 checkpoint required')
        if m['initialized_private_nodes']!=5980 or not m['all_private_voltages_bound']:raise ValueError('original initialized circuit partition required')
        inv=json.loads(inventory.read_text());verify(inv['input_sha256']);entries=inv['controls']
        before=programming_sources(entries,20,111);after=programming_sources(entries,20,fine)
        changed=[node for node in before if before[node]!=after[node]]
        if fine==111 or len(changed)!=abs(fine-111):raise ValueError('nonzero thermometer code change required')
        original_roles=m['observed_roles'];data,_=read_prefix(baseline/'control.raw',original_roles)
        reset_index=list(original_roles).index('DCO_reset')+1
        if max(r[reset_index]for r in data if r[0]<=2e-9)>.18:raise ValueError('actual reset must remain asserted throughout the early programming ramp')
        text=(baseline/'sources.spice').read_text();lines=text.splitlines();waves=[];roles=dict(original_roles);modified=[]
        for bit in range(min(111,fine),max(111,fine)):
            entry=entries[f'DCO_THERM[{bit}]'];node=entry['driver_input_node'];driver_output=entry['driver_output_anchor']
            matches=[i for i,l in enumerate(lines)if len(l.split())>=2 and l.split()[1]==node]
            if len(matches)!=1:raise ValueError('one source per actual programming driver input required')
            i=matches[0];match=re.fullmatch(r'(V\S+ \S+ 0 )PWL FILE "([^"]+)"',lines[i])
            if not match:raise ValueError('actual saved programming history required')
            original=Path(match[2]);new=retarget(load(original),before[node],after[node]);wave=output/f'fine_{bit}.pwl'
            wave.write_text(''.join(f'{t:.17g} {v:.17g}\n'for t,v in new))
            if load(wave)!=new:raise ValueError('retargeted history serialization changed values')
            lines[i]=match[1]+f'PWL FILE "{wave}"';waves.extend((original,wave));modified.append(i)
            roles[f'programming_input_{bit}']=node;roles[f'programming_output_{bit}']=driver_output
        if len(set(modified))!=len(changed)or sum(a!=b for a,b in zip(text.splitlines(),lines))!=len(changed):raise ValueError('only declared changed physical programming inputs may differ')
        sources=output/'sources.spice';sources.write_text('\n'.join(lines)+'\n')
        deck=output/'control.spice';deck_text=(baseline/'control.spice').read_text()
        for old,newpath in((baseline/'sources.spice',sources),(baseline/'control.raw',output/'control.raw')):
            if deck_text.count(str(old))!=1:raise ValueError('unique original source/raw protocol required')
            deck_text=deck_text.replace(str(old),str(newpath))
        print_lines=[line for line in deck_text.splitlines()if line.startswith('.print ')]
        if len(print_lines)!=1:raise ValueError('one native waveform print required')
        deck_text=deck_text.replace(print_lines[0],print_lines[0]+''.join(f' v({n})'for key,n in roles.items()if key not in original_roles));deck.write_text(deck_text)
        pins=dict(m['input_sha256']);pins.update({str(p):sha(p)for p in(baseline/'manifest.json',baseline/'assessment.json',baseline/'status.json',baseline/'control.raw',inventory,*waves,sources,deck,Path(__file__).resolve(),*(Path(__file__).with_name(n)for n in('common_v3.py','resources.py','compiled_charge_v2.py','selected_native_clock_shapes.py','assess_selected_detector_prefix.py','assess_selected_isolated_control.py','run_selected_dco_real_driver_control_v5.py')))})
        save(output/'manifest.json',dict(input_sha256=pins,CPU=cpu,memory_GiB=8,native_cap_s=10800,automatic_identical_retry=False,operating_point=m['operating_point'],observed_roles=roles,
            coarse=20,checkpoint_fine=111,requested_fine=fine,simulation_end_s=m['simulation_end_s'],driver_input_ramp_ns=[.5,1.5],engineering_stimulus_not_extracted_decoder_timing=True,
            unchanged_physical_cards_and_initial_conditions=True,changed_source_count=len(changed),whole_model_qualified=False,release_ready=False));verify(pins)
        binary=next(Path(p)for p in pins if p.endswith('/Xyce'));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
        save(output/'status.json',dict(state='checkpoint_retarget_native_running',release_ready=False))
        with lease(1,8,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,8)
        verify(pins);raw=output/'control.raw';data,info=read_prefix(raw,roles)
        if info['incomplete_final_sample_discarded']or abs(data[-1][0]-m['simulation_end_s'])>1e-18:raise ValueError('complete original restart horizon required')
        windows=[dict(window_ns=[start,stop],fine=fine,**frequency(data,start,stop))for start,stop in((20,40),(40,60),(60,84))]
        for key in roles:
            if not key.startswith('programming_'):continue
            bit=int(key.rsplit('_',1)[1]);is_input=key.startswith('programming_input_');high=(bit<fine)==is_input
            index=list(roles).index(key)+1;values=[r[index]for r in data if 20e-9<=r[0]<=84e-9]
            if not values or (min(values)<1.62 if high else max(values)>.18):raise ValueError('observed physical programming driver failed to settle: '+key)
        if max(r[reset_index]for r in data if r[0]<=2e-9)>.18:raise ValueError('reset must remain asserted during actual programming ramp')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(raw):sha(raw)},windows=windows,waveform=info,
            physical_driver_input_plateaus_verified=True,cross_code_checkpoint_model_qualified=False,full_circuit_dynamic_equivalence_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='checkpoint_retarget_diagnostic_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('baseline','inventory','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cpu',type=int,default=18);p.add_argument('--fine',type=int,choices=range(8,248),required=True);a=p.parse_args();run(a.baseline.resolve(),a.inventory.resolve(),a.output.resolve(),a.cpu,a.fine)
