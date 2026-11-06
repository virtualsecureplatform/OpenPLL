"""Verify native NODESET state selection and release on a tiny latch/divider control."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from assess_selected_detector_prefix import read_prefix


def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';image=ROOT/'build/apptainer/openpll-release-modern.sif';files=[Path(__file__).resolve(),binary,image,Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('assess_selected_detector_prefix.py')];records=[];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+180
    with lease(1,2,deadline):
        for index,(a,b) in enumerate([(1.8,0),(0,1.8)]):
            case=output/str(index);case.mkdir();guess=case/'guesses.spice';guess.write_text(f'.NODESET V(__context_a)={a} V(__context_b)={b} V(__context_x)=1.8\n');raw=case/'control.raw';deck=case/'control.spice'
            deck.write_text(f'''NODESET solver control; not PLL qualification
VDD supply 0 1.8
.model N NMOS LEVEL=1 VTO=0.4 KP=200u
.model P PMOS LEVEL=1 VTO=-0.4 KP=100u
MPA __context_a __context_b supply supply P W=2u L=1u
MNA __context_a __context_b 0 0 N W=1u L=1u
MPB __context_b __context_a supply supply P W=2u L=1u
MNB __context_b __context_a 0 0 N W=1u L=1u
CA __context_a 0 1f
CB __context_b 0 1f
R1 supply __context_x 1k
R2 __context_x 0 1k
.include "{guess}"
.options nonlin reltol=1e-6 abstol=1e-10
.tran 1p 1p 0 1p
.print tran format=raw precision=17 file={raw} v(__context_a) v(__context_b) v(__context_x)
.end
''')
            execute([binary,'-a','-linsolv','umfpack_reuse',deck],case/'native.log',deadline,2)
            rows,info=read_prefix(raw,{'a':'__context_a','b':'__context_b','x':'__context_x'})
            if info['incomplete_final_sample_discarded'] or info['declared_samples']!=len(rows) or abs(rows[-1][0]-1e-12)>1e-22:raise ValueError('normally completed native waveform required')
            first=rows[0][1:];selected=abs(first[0]-a)<1e-5 and abs(first[1]-b)<1e-5;released=abs(first[2]-.9)<1e-8
            records.append(dict(starting_guesses_V=[a,b,1.8],initial_native_values_V=first,latch_state_selected=selected,divider_guess_released_to_unconstrained_solution=released))
            files += [guess,deck,raw,case/'native.log',case/'native.process.json']
    pins={str(p):sha(p) for p in files};verify(pins);passed=all(r['latch_state_selected'] and r['divider_guess_released_to_unconstrained_solution'] for r in records)
    save(output/'assessment.json',dict(input_sha256=pins,records=records,both_native_NODESET_controls_pass=passed,scope='small level1-MOS latch and linear divider; NODESET behavior only, not PLL or PDK model validation',physical_models_qualified=False,release_ready=False))
    if not passed:raise ValueError('native NODESET behavior does not match expected selection/release')
    print(json.dumps(records))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
