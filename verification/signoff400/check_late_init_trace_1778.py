"""Compare diagnostic call tracing against the exact backend on a known RC ladder."""
import json,time,csv
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute

def run():
    base=ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce'
    trace=ROOT/'build/tools/xyce_late_init_trace_1777/Xyce'
    receipt=trace.parent/'assessment.json';r=json.loads(receipt.read_text())
    verify(r['input_sha256']);verify(r['artifacts'])
    if not r['trace_only'] or r['changed_archive_members']!=['N_CIR_Xyce.C.o'] or r['base_binary_sha256']!=sha(base):raise ValueError('exact trace-only build required')
    out=ROOT/'build/signoff400/selected_init_trace_control_1778';out.mkdir(exist_ok=False)
    pins={str(p):sha(p)for p in [base,trace,receipt,Path(__file__).resolve()]};results=[]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+120
    with lease(1,4,deadline):
        for label,binary in [('base',base),('trace',trace)]:
            folder=out/label;folder.mkdir();data=folder/'dc.csv';deck=folder/'control.spice'
            lines=['* Analytical 3000 ohm ladder and 3000 ohm load','Vdrive n0 0 1']
            for i in range(3000):lines.extend([f'R{i} n{i} n{i+1} 1',f'C{i} n{i+1} 0 1p',f'Cn{i} n{i+1} 0 -1f'])
            lines.extend(['Rload n3000 0 3000','.dc Vdrive 1 1 1',f'.print dc format=csv precision=17 file={data} v(n0) v(n1500) v(n3000)','.end'])
            deck.write_text('\n'.join(lines)+'\n');execute([binary,'-a','-linsolv','umfpack_reuse',deck],folder/'native.log',deadline,4)
            rows=list(csv.reader(data.read_text().splitlines()));values=[float(v)for v in rows[1]]
            if len(values)!=3 or any(abs(v-e)>1e-10 for v,e in zip(values,[1,.75,.5])):raise ValueError('analytical ladder voltages differ')
            results.append(values)
    log=(out/'trace/native.log').read_text();events=[s for s in log.splitlines()if s.startswith('OPENPLL_INIT_TRACE')]
    expected=[f'OPENPLL_INIT_TRACE {phase} {stage}'for stage in ['analysis_object','solver_system','devices','nonlinear']for phase in ['begin','end']]
    expected += [f'OPENPLL_INIT_TRACE {phase} {stage}'for stage in ['node_symbols','print_parameters','fourier','fft','measure_ops','measure_fft','measure_suffix','final_expressions','delete_functions','delete_params','delete_globals']for phase in ['begin','end']]
    expected += ['OPENPLL_INIT_TRACE begin analysis_run']
    if events!=expected or results[0]!=results[1]:raise ValueError('trace event order or native numerical outputs differ')
    verify(pins)
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in out.rglob('*')if p.is_file()},analytical_RC_ladder_pass=True,baseline_and_trace_outputs_identical=True,all_initialization_boundaries_observed=True,events=events,results=results,full_model_backend_qualified=False,release_ready=False))

if __name__=='__main__':run()
