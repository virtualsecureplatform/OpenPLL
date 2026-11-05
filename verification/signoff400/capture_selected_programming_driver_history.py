"""Capture actual programming-driver input history without restarting native.

Use the existing generic bounded-index RAW extractor. Its historical schema
names these channels clock_drivers, but this adapter explicitly labels them
programming data and reset, never a detector clock-source packet.
"""
import argparse,json,os
from pathlib import Path
from common_v3 import save,sha,verify
from capture_selected_clock_driver_waveforms import run as capture


def run(drivers,plan,inventory,native,snapshot,adapter,output):
    if adapter.exists() or output.exists():raise FileExistsError('fresh capture inventory and output required')
    d,p=[json.loads(path.read_text()) for path in [drivers,plan]];verify(d['input_sha256']);verify(p['input_sha256'])
    if p['input_sha256'].get(str(drivers))!=sha(drivers):raise ValueError('same DCO programming driver inventory required')
    roles={port:dict(node=c['driver_input_node'],kind='programming_driver_input') for port,c in d['controls'].items()}
    if len(roles)!=302 or len({r['node'] for r in roles.values()})!=302:raise ValueError('302 independent physical programming inputs required')
    reset=p['prescribed_reset_driver_input']
    if not reset or reset in {r['node'] for r in roles.values()}:raise ValueError('independent physical DCO reset driver input required')
    roles['DCO_reset_driver_input']=dict(node=reset,kind='reset_driver_input')
    pins=dict(d['input_sha256']);pins.update({str(path):sha(path) for path in [drivers,plan,Path(__file__).resolve()]});verify(pins)
    save(adapter,dict(input_sha256=pins,clock_drivers=roles,signal_kind='DCO programming data and reset; schema adapter only',
        physical_control_input_history_requested=True,driver_output_voltages_prescribed=False,
        programming_history_qualified=False,release_ready=False))
    capture(adapter,inventory,native,snapshot,output)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['drivers','plan','inventory','native','snapshot','adapter','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{29});run(*(getattr(a,n).resolve() for n in ['drivers','plan','inventory','native','snapshot','adapter','output']))
