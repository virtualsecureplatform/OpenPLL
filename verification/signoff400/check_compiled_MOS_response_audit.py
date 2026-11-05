"""Control an independent named-column compiled MOS response audit."""
import argparse,json,math,os,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute


def config(receipt):
    a=json.loads(receipt.read_text());c=a['case'];return dict(profile_start=c['profile_start'],profile_count=c['profile_count'],**{k:dict(reference=str(receipt.parent/k/'ngspice.dat'),native=str(receipt.parent/k/('xyce.cir.prn' if k=='dc' else 'xyce.cir.FD.prn'))) for k in ('dc','ac')})


def verify_metrics(actual,expected):
    for analysis in ('dc','ac'):
        for key in ('terminal_response_comparisons','diagnostic_numeric_screen_exceedances'):
            if actual[analysis][key]!=expected[analysis][key]:raise ValueError('independent response count/screen mismatch')
        for key in ('maximum_absolute_current_difference_A','maximum_scaled_current_difference'):
            if not math.isclose(actual[analysis][key],expected[analysis][key],rel_tol=3e-14,abs_tol=1e-25):raise ValueError('independent complex response magnitude mismatch')


def check(out,deadline):
    source=ROOT/'tools/sheet_charge/audit_MOS_responses.cpp';header=ROOT/'tools/charge_compiler/json.hpp';plan=ROOT/'build/signoff400/startup_timing_MOS_backend_profiles_001/comparison_plan.json';grid=json.loads(plan.read_text());expected=dict(DC_gate_sweep_v=[0,1.8,.3],drain_source_bias_magnitudes_v=[0,.9,1.8],reverse_body_bias_magnitudes_v=[0,.2],AC_gate_source_bias_magnitudes_v=[0,.9,1.8],AC_terminal_excitations=['gate','drain','bulk'],AC_frequencies_hz=[1e6,4e8])
    if any(grid[k]!=v for k,v in expected.items()):raise ValueError('compiled named-column grid binding changed')
    receipts=[ROOT/'build/signoff400/startup_timing_MOS_backend_batch_control_001/assessment.json'];short=sorted((ROOT/'build/signoff400/startup_timing_MOS_backend_grid_001').glob('*/assessment.json'))
    receipts.append(next(p for p in short if json.loads(p.read_text())['case']['profile_count']==12));pins={str(p):sha(p) for p in (source,header,plan,Path(__file__).resolve(),Path('/usr/bin/g++').resolve(),*receipts)};binary=out/'audit_MOS_responses';execute(['g++','-std=c++20','-O3','-fno-fast-math','-ffp-contract=off',source,'-o',binary],out/'build.log',deadline,4);results=[]
    for i,receipt in enumerate(receipts):
        cfg=config(receipt);a=json.loads(receipt.read_text())
        for spec in (cfg['dc'],cfg['ac']):
            for name in spec.values():
                pins[name]=sha(name)
                if pins[name]!=a['artifacts'][name]:raise ValueError('sealed native data changed')
        target=out/f'case_{i}.json';save(target,cfg);execute([binary,target],out/f'case_{i}.log',deadline,4);actual=json.loads((out/f'case_{i}.log').read_text());verify_metrics(actual,a['results']);results.append(dict(case=a['case'],results=actual));
    original=config(receipts[0]);native=Path(original['ac']['native']);lines=native.read_text().splitlines();mutations={}
    wrong=lines[:];tokens=wrong[0].split();tokens[2],tokens[4]=tokens[4],tokens[2];wrong[0]=' '.join(tokens);mutations['swapped_named_columns']=wrong
    wrong=lines[:];tokens=wrong[1].split();tokens[1]='nan';wrong[1]=' '.join(tokens);mutations['nonfinite_coordinate']=wrong
    wrong=lines[:];tokens=wrong[1].split();tokens[1]='2000000';wrong[1]=' '.join(tokens);mutations['wrong_frequency']=wrong
    wrong=lines[:];wrong[1]=' '.join(wrong[1].split()[:-1]);mutations['truncated_row']=wrong
    mutations['missing_terminal_marker']=[line for line in lines if 'End of Xyce(TM) Simulation' not in line]
    for label,content in mutations.items():
        data=out/(label+'.prn');data.write_text('\n'.join(content)+'\n');cfg=json.loads(json.dumps(original));cfg['ac']['native']=str(data);path=out/(label+'.json');save(path,cfg)
        try:execute([binary,path],out/(label+'.log'),deadline,4)
        except RuntimeError:pass
        else:raise ValueError('malformed native response accepted: '+label)
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('audit source changed')
    artifacts=[binary,*out.glob('case_*.json'),*out.glob('case_*.log')];save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},results=results,independent_compiled_named_response_controls_pass=True,full_and_short_profile_batches_checked=True,malformed_native_controls_rejected=sorted(mutations),diagnostic_screen_is_physical_acceptance_budget=False,full_450_batch_audit_complete=False,release_qualified=False));save(out/'status.json',dict(state='compiled_MOS_response_audit_controls_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_one_build_audit_CPU_slot',release_qualified=False))
    try:
        with lease(1,4,deadline):check(out,deadline)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
