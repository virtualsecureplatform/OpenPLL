"""Compare diagnostic call tracing against the exact backend on a known RC ladder."""
import json,time,csv
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute

def run():
    base=ROOT/'build/tools/xyce_linear_trace_1786/Xyce'
    trace=ROOT/'build/tools/xyce_metis_ordering_1790/Xyce'
    receipt=trace.parent/'assessment.json';r=json.loads(receipt.read_text())
    verify(r['input_sha256']);verify(r['artifacts'])
    if not r['ordering_only'] or r['changed_archive_members']!=['N_LAS_TranSolverFactory.C.o'] or r['base_binary_sha256']!=sha(base):raise ValueError('exact trace-only build required')
    out=ROOT/'build/signoff400/selected_init_trace_control_1791';out.mkdir(exist_ok=False)
    pins={str(p):sha(p)for p in [base,trace,receipt,Path(__file__).resolve()]};results=[]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+120
    with lease(1,4,deadline):
        for label,binary in [('base',base),('trace',trace)]:
            folder=out/label;folder.mkdir();data=folder/'dc.csv';deck=folder/'control.spice'
            lines=['* Analytical 7000 ohm ladder and 7000 ohm load','Vdrive n0 0 1']
            for i in range(7000):lines.extend([f'R{i} n{i} n{i+1} 1',f'C{i} n{i+1} 0 1p',f'Cn{i} n{i+1} 0 -1f'])
            lines.extend(['Rload n7000 0 7000','.dc Vdrive 1 1 1',f'.print dc format=csv precision=17 file={data} v(n0) v(n3500) v(n7000)','.end'])
            deck.write_text('\n'.join(lines)+'\n');execute([binary,'-a','-linsolv','umfpack_reuse',deck],folder/'native.log',deadline,4)
            rows=list(csv.reader(data.read_text().splitlines()));values=[float(v)for v in rows[1]]
            if len(values)!=3 or any(abs(v-e)>1e-10 for v,e in zip(values,[1,.75,.5])):raise ValueError('analytical ladder voltages differ')
            results.append(values)
    log=(out/'trace/native.log').read_text();events=[s for s in log.splitlines()if s.startswith('OPENPLL_INIT_TRACE')]
    expected=[f'OPENPLL_INIT_TRACE {phase} {stage}'for stage in ['analysis_object','solver_system','devices','nonlinear']for phase in ['begin','end']]
    expected += [f'OPENPLL_INIT_TRACE {phase} {stage}'for stage in ['node_symbols','print_parameters','fourier','fft','measure_ops','measure_fft','measure_suffix','final_expressions','delete_functions','delete_params','delete_globals']for phase in ['begin','end']]
    expected += ['OPENPLL_INIT_TRACE begin analysis_run']
    analysis_events=[s for s in log.splitlines()if s.startswith('OPENPLL_ANALYSIS_TRACE')]
    ordered=[('begin','device_mask'),('end','device_mask'),('begin','analysis_object_run'),('begin','dc_init'),('end','dc_init'),('begin','dc_loop'),('begin','dc_take_step'),('end','dc_take_step'),('end','dc_loop'),('begin','dc_finish'),('end','dc_finish'),('end','analysis_object_run')]
    if analysis_events!=['OPENPLL_ANALYSIS_TRACE '+phase+' '+label for phase,label in ordered]:raise ValueError('analysis boundary events differ')
    step_events=[s for s in log.splitlines()if s.startswith('OPENPLL_STEP_TRACE')]
    stack=[];seen=set()
    for event in step_events:
        _,phase,label=event.split()
        if phase=='begin':stack.append(label);seen.add(label)
        elif not stack or stack.pop()!=label:raise ValueError('unbalanced step trace')
    if stack or seen!={'predictor','sources','nonlinear_solve','load_rhs','load_jacobian','linear_solve'}:raise ValueError('missing step boundaries')
    linear_events=[s for s in log.splitlines()if s.startswith('OPENPLL_LINEAR_TRACE')]
    stack=[];seen=set()
    for event in linear_events:
        _,phase,label=event.split()
        if phase=='begin':stack.append(label);seen.add(label)
        elif not stack or stack.pop()!=label:raise ValueError('unbalanced linear trace')
    if stack or seen!={'transform','root_matrix','gather_values','prepare_values','symbolic','numeric'}:raise ValueError('missing linear boundaries')
    if 'OPENPLL_ORDERING requested=METIS used=3' not in log:raise ValueError('actual METIS ordering required')
    if events!=expected or results[0]!=results[1]:raise ValueError('trace event order or native numerical outputs differ')
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in out.rglob('*')if p.is_file()},analytical_RC_ladder_pass=True,baseline_and_trace_outputs_identical=True,all_initialization_boundaries_observed=True,events=events,analysis_events=analysis_events,step_events=step_events,linear_events=linear_events,results=results,full_model_backend_qualified=False,release_ready=False))

if __name__=='__main__':run()
