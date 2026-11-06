"""Diagnose a reduced DCO initialized from an actual pre-reset native state.

Keep circuit cards and quiet boundaries from the history control. Import every
private voltage, shift its prescribed histories, and use actual verified UIC
semantics. This is not a qualified nonlinear state restart or boundary model.
"""
import argparse,bisect,json,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from check_selected_boundary_waveforms import bind
from selected_native_clock_shapes import load
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def shifted(rows,start):
    if not rows or rows[0][0]!=0 or not 0<start<rows[-1][0]:raise ValueError('source must enclose checkpoint')
    k=bisect.bisect_left([t for t,v in rows],start)
    if rows[k][0]==start:value=rows[k][1]
    else:
        a,v=rows[k-1];b,w=rows[k];value=v+(w-v)*(start-a)/(b-a)
    return [(0,value)]+[(t-start,v)for t,v in rows if t>start]


def run(baseline,plan,state_receipt,uic_probe,output):
    os.sched_setaffinity(0,{28});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_saved_state_DCO_diagnostic',release_ready=False))
    try:
        bm=json.loads((baseline/'manifest.json').read_text());verify(bm['input_sha256'])
        p=json.loads(plan.read_text());verify(p['input_sha256'])
        if bm['controls']['coarse']!=20 or bm['controls']['fine']!=111 or bm['operating_point']['corner']!='tt':raise ValueError('original TT coarse20/fine111 history control required')
        sr=json.loads(state_receipt.read_text());verify(sr['input_sha256']);verify(sr['artifacts'])
        probe=json.loads(uic_probe.read_text());verify(probe['input_sha256']);verify(probe['artifacts'])
        if not probe['actual_native_UIC_voltage_initialization_verified']:raise ValueError('actual native UIC control required')
        state=state_receipt.parent/'saved_voltage_state.json'
        if sr['artifacts'].get(str(state))!=sha(state):raise ValueError('saved voltage vector not pinned')
        data=json.loads(state.read_text());start=data['time_s'];end=260e-9-start
        if not 175e-9<=start<=175.011e-9:raise ValueError('actual pre-reset native checkpoint required')
        source_manifests=[Path(x)for x in sr['input_sha256']if x.endswith('/manifest.json')]
        if len(source_manifests)!=1:raise ValueError('unique original native state source required')
        original=json.loads(source_manifests[0].read_text())
        models={x:h for x,h in bm['input_sha256'].items()if x.endswith('/model.spice')}
        if len(models)!=1 or any(original['input_sha256'].get(x)!=h for x,h in models.items()):raise ValueError('checkpoint native model differs')
        bound=bind(p['private_unknown_nodes'],data['variable_names'])
        if not bound['all_bound']:raise ValueError('every private circuit voltage must be initialized from native')
        actual_binary=[Path(x)for x in bm['input_sha256']if x.endswith('/Xyce')]
        if len(actual_binary)!=1 or probe['input_sha256'].get(str(actual_binary[0]))!=sha(actual_binary[0]):raise ValueError('UIC probe executable differs')
        binary=actual_binary[0];devices=output/'devices.spice';devices.write_bytes((baseline/'devices.spice').read_bytes())
        ic=output/'initial_conditions.spice'
        with ic.open('x')as stream:
            for node in p['private_unknown_nodes']:
                stream.write(f'.IC V({node})={data["values"][bound["bindings"][node]["index"]]:.17g}\n')
        inputs=[baseline/'manifest.json',baseline/'devices.spice',baseline/'sources.spice',baseline/'control.spice',plan,state_receipt,state,uic_probe,binary,devices,ic,Path(__file__).resolve()]
        inputs += [Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','compiled_charge_v2.py','check_selected_boundary_waveforms.py','selected_native_clock_shapes.py','assess_selected_detector_prefix.py','assess_selected_isolated_control.py')]
        waves=output/'shifted_sources';waves.mkdir();count=0;lines=[]
        for line in (baseline/'sources.spice').read_text().splitlines():
            match=re.fullmatch(r'(V\S+ \S+ 0 )PWL FILE "([^"]+)"',line)
            if match:
                original_path=Path(match[2]);dest=waves/f'input_{count}.pwl';rows=shifted(load(original_path),start)
                with dest.open('x')as stream:
                    for t,v in rows:stream.write(f'{t:.17g} {v:.17g}\n')
                if load(dest)!=rows:raise ValueError('shifted waveform serialization differs')
                inputs += [original_path,dest];line=match[1]+f'PWL FILE "{dest}"';count+=1
            lines.append(line)
        if count!=303:raise ValueError('all 303 prescribed histories must be shifted')
        sources=output/'sources.spice';sources.write_text('\n'.join(lines)+'\n');inputs.append(sources)
        deck=output/'control.spice';text=(baseline/'control.spice').read_text()
        for name in ('devices.spice','sources.spice','control.raw'):text=text.replace(str(baseline/name),str(output/name))
        original_tran='.tran 10p 260n {schedule(0,1n,100n,10p,112n,1n,175n,10p)}'
        if text.splitlines().count(original_tran)!=1:raise ValueError('expected baseline native protocol required')
        text=text.replace(original_tran,f'.tran 10p {end:.17g} 0 10p UIC')
        text=text.replace(f'.include "{sources}"',f'.include "{sources}"\n.include "{ic}"')
        deck.write_text(text);inputs.append(deck)
        pins={str(x):sha(x)for x in inputs};verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,CPU=28,MPI_ranks=1,memory_GiB=8,native_cap_s=10800,
             controls=bm['controls'],operating_point=bm['operating_point'],observed_roles=bm['observed_roles'],
             native_checkpoint_time_s=start,simulation_end_s=end,original_full_reference_end_s=260e-9,
             initialized_private_nodes=len(p['private_unknown_nodes']),all_private_voltages_bound=True,
             nonlinear_restart_and_boundary_charge_state_qualified=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
        save(output/'status.json',dict(state='saved_state_DCO_native_running',release_ready=False))
        with lease(1,8,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,8)
        verify(pins);raw=output/'control.raw';rows,info=read_prefix(raw,bm['observed_roles'])
        if info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-end)>1e-18:raise ValueError('complete shifted native waveform required')
        measured=frequency(rows,(200e-9-start)*1e9,end*1e9)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(raw):sha(raw)},frequency=measured,waveform=info,
            measured_original_time_ns=[200,260],nonlinear_restart_qualified=False,DCO_response_equivalence_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='saved_state_DCO_diagnostic_complete',release_ready=False));print(json.dumps(measured))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','plan','state-receipt','uic-probe','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve()for n in ('baseline','plan','state-receipt','uic-probe','output')))
