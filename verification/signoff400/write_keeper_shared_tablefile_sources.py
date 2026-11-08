"""Keep literal table samples and request their common knot grid once."""
import argparse,json
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from write_keeper_tablefile_sources import write_sources as write_tables


def write_sources(array,columns,destination):
    auxiliary='openpll_replay_time_knots'
    if auxiliary in {r['conditional_formal_port'].lower() for r in columns['bindings'].values()}:raise ValueError('auxiliary knot node collides with physical port')
    stats=write_tables(array,columns,destination);text=destination.read_text()
    if text.count('TABLEFILE("')!=stats['driven_ports']:raise ValueError('complete literal source bank required')
    text=text.replace('TABLEFILE("','FASTTABLEFILE("')
    text+='* Independent zero-valued carrier requests the original common knot grid.\nVopenpllReplayKnots '+auxiliary+' 0 PWL(\n'
    text+=''.join('+ '+format(float(t),'.17g')+' 0\n' for t in array[:,0])
    text+='+ )\nRopenpllReplayKnots '+auxiliary+' 0 1\n'
    destination.write_text(text)
    stats.update(source_representation='FASTTABLEFILE with one shared PWL knot carrier',individual_table_breakpoints_disabled=True,shared_breakpoint_samples=len(array),all_original_time_knots_requested=True,auxiliary_knot_node=auxiliary)
    return stats


def run(waveforms,output):
    controls=ROOT/'build/signoff400/selected_xyce_shared_TABLEFILE_controls_1375/assessment.json';c=json.loads(controls.read_text());verify(c['input_sha256']);verify(c['artifacts'])
    if not c['all_twelve_native_controls_complete'] or not c['shared_knot_driver_used'] or not c['literal_source_samples_and_knot_breakpoints_verified']:raise ValueError('completed native shared-knot controls required')
    receipt=waveforms/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a['completed_boundary_waveforms_available'] or not a['all_saved_native_values_finite'] or not a['PLLOUT_is_observation_only']:raise ValueError('completed finite unforced reference required')
    columns_file=waveforms/'columns.json';array_file=waveforms/'boundary.npy';columns=json.loads(columns_file.read_text());array=np.load(array_file,mmap_mode='r')
    files=[controls,receipt,columns_file,array_file,Path(__file__).resolve(),Path(__file__).with_name('write_keeper_tablefile_sources.py')];pins={str(p):sha(p) for p in files};output.mkdir(parents=True,exist_ok=False);sources=output/'external_sources.spice'
    try:
        stats=write_sources(array,columns,sources);verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [sources,*sorted((output/'tables').glob('*.dat'))]},**stats,sampled_PWL_environment_only=True,native_replay_executed=False,model_qualified=False,release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='source_generation_failed',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['waveforms','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.waveforms.resolve(),a.output.resolve())
