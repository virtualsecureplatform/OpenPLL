"""Measure one-code up/down response through the retained physical fine driver.

One TT checkpoint diagnostic; engineered 1 ns input ramps are not extracted RTL
decoder timing, and this experiment does not qualify the model family.
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


def pulse(rows):
    if not rows or rows[0][0]!=0 or rows[-1][0]<=61e-9 or any(not math.isfinite(x)or not math.isfinite(v)for x,v in rows):raise ValueError('complete finite baseline waveform required')
    if any(a[0]>=b[0]for a,b in zip(rows,rows[1:])):raise ValueError('strictly increasing baseline knots required')
    if any(not -.1<=v<=.18 for t,v in rows if t>=20e-9):raise ValueError('fine111 inactive programming input must be settled low')
    return [(t,v)for t,v in rows if t<30e-9]+[(30e-9,interpolate(rows,30e-9)),(31e-9,1.8),(60e-9,1.8),(61e-9,interpolate(rows,61e-9))]+[(t,v)for t,v in rows if t>61e-9]


def run(baseline,inventory,output,cpu):
    if cpu not in range(16,32):raise ValueError('spare physical core required')
    os.sched_setaffinity(0,{cpu});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'status.json',dict(state='preparing_checkpoint_code_step',release_ready=False))
    try:
        m=json.loads((baseline/'manifest.json').read_text());verify(m['input_sha256'])
        if json.loads((baseline/'status.json').read_text())['state']!='saved_state_DCO_diagnostic_complete':raise ValueError('normally completed saved-state baseline required')
        if m['controls']['coarse']!=20 or m['controls']['fine']!=111 or m['operating_point']!={'corner':'tt','supply_v':1.8,'temperature_c':27}:raise ValueError('measured TT coarse20/fine111 checkpoint required')
        if m['initialized_private_nodes']!=5980 or not m['all_private_voltages_bound']:raise ValueError('original initialized circuit partition required')
        inv=json.loads(inventory.read_text());verify(inv['input_sha256']);entries=inv['controls']
        before=programming_sources(entries,20,111);after=programming_sources(entries,20,112)
        changed=[node for node in before if before[node]!=after[node]]
        node=entries['DCO_THERM[111]']['driver_input_node'];driver_output=entries['DCO_THERM[111]']['driver_output_anchor']
        if changed!=[node]or (before[node],after[node])!=(0.,1.8):raise ValueError('exact one-code physical driver transition required')
        text=(baseline/'sources.spice').read_text();lines=text.splitlines();matches=[i for i,l in enumerate(lines)if len(l.split())>=2 and l.split()[1]==node]
        if len(matches)!=1:raise ValueError('one actual input voltage source required')
        i=matches[0];match=re.fullmatch(r'(V\S+ \S+ 0 )PWL FILE "([^"]+)"',lines[i])
        if not match:raise ValueError('actual saved programming history source required')
        original=Path(match[2]);rows=load(original);new=pulse(rows);wave=output/'fine111_up_down.pwl'
        wave.write_text(''.join(f'{t:.17g} {v:.17g}\n'for t,v in new))
        if load(wave)!=new:raise ValueError('pulse serialization changed values')
        lines[i]=match[1]+f'PWL FILE "{wave}"';sources=output/'sources.spice';sources.write_text('\n'.join(lines)+'\n')
        if sum(a!=b for a,b in zip(text.splitlines(),lines))!=1:raise ValueError('only one physical source may change')
        deck=output/'control.spice';deck_text=(baseline/'control.spice').read_text()
        for old,newpath in((baseline/'sources.spice',sources),(baseline/'control.raw',output/'control.raw')):
            if deck_text.count(str(old))!=1:raise ValueError('unique original source/raw protocol required')
            deck_text=deck_text.replace(str(old),str(newpath))
        print_lines=[line for line in deck_text.splitlines()if line.startswith('.print ')]
        if len(print_lines)!=1:raise ValueError('one native waveform print required')
        deck_text=deck_text.replace(print_lines[0],print_lines[0]+f' v({node}) v({driver_output})');deck.write_text(deck_text)
        pins=dict(m['input_sha256']);pins.update({str(p):sha(p)for p in(baseline/'manifest.json',baseline/'assessment.json',baseline/'status.json',inventory,original,wave,sources,deck,Path(__file__).resolve(),*(Path(__file__).with_name(n)for n in('common_v3.py','resources.py','compiled_charge_v2.py','selected_native_clock_shapes.py','assess_selected_detector_prefix.py','assess_selected_isolated_control.py','run_selected_dco_real_driver_control_v5.py')))})
        roles=dict(m['observed_roles'],programming_driver_input=node,programming_driver_output=driver_output)
        save(output/'manifest.json',dict(input_sha256=pins,CPU=cpu,memory_GiB=8,native_cap_s=10800,automatic_identical_retry=False,operating_point=m['operating_point'],observed_roles=roles,
            coarse=20,fine_sequence=[111,112,111],driver_input_ramps_ns=[[30,31],[60,61]],engineering_stimulus_not_extracted_decoder_timing=True,
            unchanged_physical_cards_and_initial_conditions=True,changed_source_count=1,whole_model_qualified=False,release_ready=False));verify(pins)
        binary=next(Path(p)for p in pins if p.endswith('/Xyce'));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
        save(output/'status.json',dict(state='checkpoint_code_step_native_running',release_ready=False))
        with lease(1,8,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,8)
        verify(pins);raw=output/'control.raw';data,info=read_prefix(raw,roles)
        if info['incomplete_final_sample_discarded']or abs(data[-1][0]-m['simulation_end_s'])>1e-18:raise ValueError('complete original restart horizon required')
        windows=[dict(window_ns=[start,stop],fine=fine,**frequency(data,start,stop))for start,stop,fine in((15,25,111),(40,55,112),(70,84,111))]
        index=list(roles).index('programming_driver_input')+1
        for start,stop,value in((20,29,0.),(32,59,1.8),(62,84,0.)):
            values=[r[index]for r in data if start<=r[0]*1e9<=stop]
            if not values or max(abs(v-value)for v in values)>.18:raise ValueError('observed physical programming input does not match requested pulse')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(raw):sha(raw)},windows=windows,waveform=info,
            physical_driver_input_plateaus_verified=True,nonlinear_code_step_model_qualified=False,full_circuit_dynamic_equivalence_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='checkpoint_code_step_diagnostic_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in('baseline','inventory','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cpu',type=int,default=19);a=p.parse_args();run(a.baseline.resolve(),a.inventory.resolve(),a.output.resolve(),a.cpu)
