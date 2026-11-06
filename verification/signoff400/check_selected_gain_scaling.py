"""Replay selected DLF fixed-point scaling; no analog headroom qualification."""
import argparse,json,os,subprocess
from pathlib import Path
from common_v3 import ROOT,save,sha,verify

def run(output):
    os.sched_setaffinity(0,{30})
    output.mkdir(parents=True,exist_ok=False)
    sources=ROOT/'rtl/selected400/sources.json'
    declared=json.loads(sources.read_text())['files']
    verify({str(ROOT/p):d for p,d in declared.items()})
    core=ROOT/'rtl/selected400/IntegerPLL_ProgrammedCore.v'
    digital=ROOT/'rtl/selected400/IntegerPLL_DigitalCore.v'
    if '.DLF_FRAC_WIDTH(2),.DLF_PROP_RAIL_GUARD(1)' not in core.read_text():
        raise ValueError('selected fixed-point parameter override changed')
    if 'assign dco_code_raw = DLF_CODE[DLF_CODE_WIDTH-1:DLF_CODE_WIDTH-8];' not in digital.read_text():
        raise ValueError('selected DCO projection changed')
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    bench=Path(__file__).with_name('selected_gain_scaling_tb.v')
    rtl=[ROOT/'rtl/selected400'/n for n in ('IntegerPLL_DLF.v','IntegerPLL_B2TH.v')]
    pins={str(p):sha(p)for p in (sources,core,digital,image,bench,Path(__file__).resolve(),*rtl)}
    prefix=['apptainer','exec','--bind','/home:/home',str(image)]
    commands=[prefix+['/usr/bin/iverilog','-g2012','-s','selected_gain_scaling_tb','-o',str(output/'test.vvp'),str(bench),*map(str,rtl)],
              prefix+['/usr/bin/vvp',str(output/'test.vvp')]]
    logs=[]
    for command in commands:
        result=subprocess.run(command,check=True,capture_output=True,text=True,timeout=60)
        logs.append(result.stdout+result.stderr)
    if 'PASS selected gain scaling: 112 integral updates plus three proportional checks' not in logs[-1]:
        raise ValueError('complete gain regression missing')
    log=output/'replay.log';log.write_text(''.join(logs));verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(log):sha(log),str(output/'test.vvp'):sha(output/'test.vvp')},
        commands=commands,integral_update_checks=112,proportional_checks=3,
        accumulator_fractional_bits=2,DLF_to_fine_shift_bits=2,
        KI4_fine_code_increment_per_update=0.25,KP4_fine_code_offset=1,
        updates_per_positive_fine_code_KI4=4,
        scope='Selected DLF simulation and pinned selected-wrapper parameter/projection binding. Fractional increments quantize asymmetrically at integer boundaries. This is not a complete controller or analog-loop test.',
        FF_headroom_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
