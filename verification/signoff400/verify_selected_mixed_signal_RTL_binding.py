"""Verify current mixed-signal digital sources against the selected route and rejection controls."""
import json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from selected_physical_rtl import source_pins


def run():
    output=ROOT/'build/signoff400/selected_mixed_signal_RTL_binding_1547'
    output.mkdir(exist_ok=False)
    os.sched_setaffinity(0,{30})
    route=ROOT/'build/signoff400/prototype_v3_selected_route_019/assessment.json'
    record=json.loads(route.read_text())
    sources={p:d for p,d in record['candidate_source_sha256'].items() if p.endswith('.v')}
    verify(sources)
    pins=source_pins()
    portable={p:d for p,d in pins.items() if p.endswith('.v')}
    original_names={Path(p).name:d for p,d in sources.items()}
    portable_names={Path(p).name:d for p,d in portable.items()}
    if len(sources)!=9 or len(portable)!=9 or original_names!=portable_names:
        raise ValueError('all nine selected route RTL files must match portable sources exactly')
    names=['test_selected_physical_rtl.py','test_selected_mixed_signal_build_cache.py',
           'selected_mixed_signal_build_cache.py','selected_mixed_signal_build_cache_v2.py',
           'run_selected_mixed_signal_v8.py','verify_selected_mixed_signal_RTL_binding.py']
    pins.update({str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in names})
    pins[str(route)]=sha(route)
    log=output/'tests.log'
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+300):
        with log.open('x') as stream:
            subprocess.run(['/usr/bin/python3','-m','unittest','test_selected_physical_rtl',
                            'test_selected_mixed_signal_build_cache'],
                           cwd=Path(__file__).parent,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=60)
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(log):sha(log)},
         portable_RTL_files=9,exact_selected_route_RTL_bytes_verified=True,
         source_geometry_tool_and_image_rejection_controls_passed=True,
         compilation_scope='Actual selected digital RTL; analog models are separate diagnostic inputs',
         new_functional_proof=False,analog_models_qualified=False,closed_loop_qualified=False,release_ready=False))


if __name__=='__main__':run()
