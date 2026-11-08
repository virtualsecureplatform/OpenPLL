"""Independent coarse23 static DCO point; no extrapolated calibration or release qualification."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import json
from pathlib import Path
import tempfile
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from assess_keeper_physical_tuning import expected
from assess_selected_detector_phase_probe_v2 import read_selected
from assess_selected_isolated_control import frequency
from retain_completed_native_trace import retain


from run_keeper_static_terminated_DCO import environment


def run():
    b=ROOT/'build/signoff400'
    output=b/'selected_keeper_static_coarse23_DCO_1541'
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{17})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    conditional=b/'selected_keeper_receiver_native_1419'
    role_source=b/'selected_keeper_prescribed_boundary_roles_1522'
    physical=b/'selected_keeper_corrected_BSIM_physical_1296'
    reference=b/'selected_keeper_corrected_BSIM_fine149_1295'
    coarse,fine,load=23,149,32
    try:
        receipts=[p/'assessment.json' for p in (conditional,role_source,physical,reference)]
        records=[json.loads(p.read_text()) for p in receipts]
        for r in records:
            verify(r['input_sha256']);verify(r['artifacts'])
        if not records[2]['all_macro_and_DCO_tuning_bits_match']:
            raise ValueError('verified reference physical controls required')
        bindings=json.loads((conditional/'bindings.json').read_text())
        roles=json.loads((role_source/'boundaries.json').read_text())
        observations=json.loads((physical/'plan.json').read_text())['observations']
        mapping,reset,receiver=environment(bindings,roles,observations,coarse,fine)
        model=conditional/'model.spice'
        roots=[s.split() for s in model.read_text().splitlines() if s.startswith('.subckt ') and not s.split()[1].startswith('__openpll_')]
        if len(roots)!=1 or set(roots[0][2:])!=set(mapping) or len(roots[0][2:])!=len(mapping):
            raise ValueError('complete ordered root interface required')
        root=roots[0]
        observed_nodes=['PLLOUT','RECEIVER','VDD','RESET_DRIVER']
        leaves={}
        for name,r in observations.items():
            if r['endpoint']!='DCO':continue
            safe=bindings['all_physical_nodes'].get(r['physical_node'])
            if safe is None:raise ValueError('native DCO endpoint absent')
            node=mapping.get(safe,'XDUT:'+safe)
            leaves[name]=dict(**r,static_node=node)
            if node!='0' and node not in observed_nodes:observed_nodes.append(node)
        if len(leaves)!=302:raise ValueError('all 302 native DCO control leaves required')
        binary=ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce'
        backend=sha(binary)
        if backend!='84ba37cb0e3c405e084b1e210a35f0f492f03b7c94d2c1f9ef284b56121db12a':
            raise ValueError('checked corrected backend required')
        local=Path(tempfile.mkdtemp(prefix='openpll-static-DCO-'))
        raw,log,memory=[local/n for n in ('transient.raw','native.log','memory.log')]
        deck=output/'transient.spice'
        library='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
        deck.write_text('\n'.join(['* Static-code native DCO; approximate passive receiver termination and grounded capacitive exterior',
            f'.lib "{library}" tt',f'.include "{model}"','VDD VDD 0 1.8',
            'VRESET RESET_DRIVER 0 PWL(0 0 5n 0 5.1n 1.8 60n 1.8)',
            'XDUT '+' '.join(mapping[p] for p in root[2:])+' '+root[1],f'C_RECEIVER RECEIVER 0 {load}f',
            '.options parser model_binning=true','.options device temp=27','.options nonlin reltol=1e-5 abstol=1e-9',
            '.tran 10p 60n 0 10p','.print tran format=raw precision=17 file='+str(raw)+' '+' '.join('V('+n+')' for n in observed_nodes),'.end'])+'\n')
        files=[*receipts,conditional/'bindings.json',role_source/'boundaries.json',physical/'plan.json',model,binary,deck,Path(__file__).resolve(),
               *[Path(__file__).with_name(n) for n in ('assess_keeper_physical_tuning.py','assess_selected_detector_phase_probe_v2.py',
                  'assess_selected_isolated_control.py','retain_completed_native_trace.py','compiled_charge_v2.py','run_keeper_static_terminated_DCO.py')]]
        pins={str(p):sha(p) for p in files}
        save(output/'inputs.json',dict(input_sha256=pins,coarse=coarse,fine=fine,receiver_load_fF=load,
             CPU=17,memory_GiB=8,native_cap_s=86400,maximum_native_cases=1,automatic_identical_retry=False,
             simulation_ns=60,window_ns=[20,60],max_step_ps=10,
             programming_macro_inputs_ideal_static_truth_table=True,capacitive_exterior_grounded=True,
             receiver_output_prescribed=False,PLLOUT_prescribed=False,voltage_histories_used=False,
             receiver_node=receiver,reset_node=reset,leaf_observations=leaves,
             native_outputs_local=str(local),approximation_not_qualified=True,release_ready=False))
        save(output/'status.json',dict(state='waiting_for_static_DCO_resources',release_ready=False))
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+86400):
            save(output/'status.json',dict(state='static_terminated_DCO_native_running',release_ready=False))
            start=time.monotonic()
            execute(['/usr/bin/time','-v','-o',memory,binary,'-a','-linsolv','umfpack_reuse',deck],log,time.clock_gettime(time.CLOCK_BOOTTIME)+86400,8)
            elapsed=time.monotonic()-start
        retention=[retain(p,output/p.name,native_completed=True) for p in (raw,log,memory)]
        save(output/'retention.json',dict(files=retention))
        roles_to_read={n:n for n in observed_nodes}
        samples=read_selected(output/'transient.raw',roles_to_read,60e-9)
        columns={n:i+1 for i,n in enumerate(observed_nodes)}
        window=[r for r in samples if r[0]>=20e-9]
        checks=[]
        for name,r in leaves.items():
            values=[0.] if r['static_node']=='0' else [v[columns[r['static_node']]] for v in window]
            bit=expected(r['bus'],r['bit'],coarse,fine)
            passed=min(values)>=1.44 if bit else max(values)<=.36
            checks.append(dict(name=name,expected_logic=bit,minimum_V=min(values),maximum_V=max(values),passed=passed))
        save(output/'leaf_checks.json',checks)
        measured=None;reason=None
        try:measured=frequency(samples,20,60)
        except ValueError as error:reason=str(error)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in
             [output/'transient.raw',output/'native.log',output/'memory.log',output/'leaf_checks.json',output/'retention.json']},
             normal_native_completion=True,all_saved_values_finite=True,native_elapsed_s=elapsed,
             native_DCO_leaf_endpoints_checked=302,all_native_DCO_leaves_match=all(r['passed'] for r in checks),
             frequency_diagnostic=measured,frequency_unavailable_reason=reason,
             full_reference_frequency_MHz=records[3]['frequency_diagnostic']['frequency_mhz'],
             frequency_difference_ppm=(measured['frequency_mhz']/records[3]['frequency_diagnostic']['frequency_mhz']-1)*1e6 if measured else None,
             receiver_output_prescribed=False,voltage_histories_used=False,capacitive_exterior_grounded=True,
             receiver_load_approximation_qualified=False,startup_window_qualified=False,
             wire_R_included=False,independent_model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='static_terminated_DCO_capture_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':run()
