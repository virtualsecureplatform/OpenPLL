"""Extended native streaming control after a completed bounded waveform comparison."""
import argparse,json,os,re,sys,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute


def prerequisite(path, reference):
    value=json.loads(path.read_text())
    if type(value.get('within_diagnostic_voltage_tolerance')) is not bool or value.get('partial_observation') or value.get('end_s',0)<21e-9 or value.get('channels')!=31 or value.get('DC_comparison') is not False:
        raise ValueError('completed 21ns comparison required; voltage flags are diagnostics, not qualification')
    verify(value['input_sha256'])
    if value['input_sha256'].get(str(reference))!=sha(reference):
        raise ValueError('prerequisite must use the same native reference')
    return value


def run(bench,replay,binary,reference,output,stop_ns,prior):
    if not 21<stop_ns<=260:raise ValueError('extended endpoint must be within 21..260ns')
    previous=prerequisite(prior,reference)
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_streaming_control',release_ready=False))
    try:
        r=json.loads((replay/'assessment.json').read_text())
        a=json.loads((bench/'assessment.json').read_text())
        if not r.get('exact_saved_knots_replayed') and r.get('exact_replay_valid_through_s',0)<stop_ns*1e-9:raise ValueError('replay interval does not cover control')
        verify(r['artifacts']);verify(a['artifacts'])
        lines=(bench/'boundary_sources.spice').read_text().splitlines()
        mapping=[];drivers=[];replay_paths={}
        for key in r['artifacts']:
            name=Path(key).name
            if name in replay_paths:raise ValueError('ambiguous replay artifact filename')
            replay_paths[name]=Path(key)
        for i,line in enumerate(lines):
            m=re.fullmatch(r'Vboundary\d+ (\S+) 0 PWL FILE "([^"]+)"',line)
            if not m:raise ValueError('unexpected prescribed source')
            node=m[1];path=replay_paths.get(f'boundary_{i}.pwl')
            if path is None:raise ValueError('replay boundary file missing')
            if str(path) not in r['artifacts']:raise ValueError('unpinned replay boundary')
            mapping.append(f'{node} {path}\n')
            drivers.append(f'YDAC boundary{i} {node} 0 boundary_model\n')
        if len(mapping)!=r['boundary_files'] or len(mapping)!=a['required_boundary_files']:raise ValueError('boundary count mismatch')
        (output/'boundaries.txt').write_text(''.join(mapping))
        (output/'boundary_sources.spice').write_text(''.join(drivers))
        nodes=['PLLOUT','CLKDIV_RETIMED','CONFIG_READY','CONFIG_BUSY','FAILED','TRACKING']
        for name,width in [('COARSE_CODE',6),('DCO_CODE',8),('DLF_CODE',10)]:nodes.extend(f'{name}[{i}]' for i in range(width))
        nodes.append('__parent_R_node_617')
        (output/'outputs.txt').write_text('\n'.join(nodes)+'\n')
        deck=output/'control.spice'
        deck.write_text(f'''Selected recorded-boundary DAC streaming control; diagnostic
.lib "/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice" tt
.include "{bench}/devices.spice"
.include "{output}/boundary_sources.spice"
.model boundary_model DAC(tr=0 tf=0)
* ADC API readback is on an isolated ideal source, outside the private circuit.
Vapi api_monitor 0 0
YADC api_readback api_monitor 0 api_model R=1T WIDTH=1
.model api_model ADC(settlingtime=1p uppervoltagelimit=1 lowervoltagelimit=0)
Vpower VPWR 0 1.8
Vbody VPB 0 1.8
Vground VGND 0 0
Vnb VNB 0 0
.options parser model_binning=true
.options device temp=27
.options nonlin reltol=1e-5 abstol=1e-9
.options timeint reltol=1e-5 abstol=1e-9
.tran 1p {stop_ns}n 0 10p
.print tran v(PLLOUT)
.end
''')
        files=[deck,output/'boundaries.txt',output/'outputs.txt',output/'boundary_sources.spice',binary,reference,replay/'assessment.json',bench/'assessment.json',Path(__file__).resolve(),ROOT/'tools/xyce_streaming/boundary_replay_v2.cpp',prior]
        pins={str(p):sha(p) for p in files};pins.update(r['artifacts']);pins.update(a['artifacts']);pins.update(previous['input_sha256'])
        save(output/'manifest.json',dict(input_sha256=pins,CPU=24,memory_GiB=48,native_cap_s=43200,
            bootstrap_s=1e-12,isolated_ADC_readback=True,private_circuit_loading_preserved=True,
            diagnostic=True,physical_models_qualified=False,release_ready=False))
        os.sched_setaffinity(0,{24});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        with lease(1,48,deadline):
            save(output/'status.json',dict(state='native_streaming_control_running',release_ready=False))
            execute([binary,deck,output/'boundaries.txt',output/'outputs.txt',str(stop_ns),output/'signals.csv'],output/'native.log',deadline,48)
        verify(pins)
        if 'BOUNDARY_REPLAY_COMPLETE' not in (output/'native.log').read_text():raise ValueError('missing native completion marker')
        save(output/'status.json',dict(state='native_streaming_completed_comparison_pending',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['bench','replay','binary','reference','output']:p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--stop-ns',type=float,default=260)
    p.add_argument('--prerequisite',required=True,type=Path)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['bench','replay','binary','reference','output']),a.stop_ns,a.prerequisite.resolve())
