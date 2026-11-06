"""Review proposed enable-ECO logic proofs; physical implementation stays unqualified."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from abstract_selected_handoff_comparisons import abstract
from prove_selected_clear_before_unmask_v3 import CORE_MONITOR,PARENT_CONTRACT
from review_selected_clear_seed_recovery import header


def run(candidate,seeds,logic,reset,recovery,algebra,negative,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{30});catalog=candidate/'sources.json';c=json.loads(catalog.read_text());verify(c['basis_input_sha256']);sources=sorted(candidate.glob('*.v'));pins={str(catalog):sha(catalog)}
    if len(sources)!=9:raise ValueError('complete candidate source set required')
    for p in sources:
        if c['source_sha256'].get(str(p.relative_to(ROOT)))!=sha(p):raise ValueError('candidate source changed')
        pins[str(p)]=sha(p)
    receipts=[seeds/'assessment.json',logic,reset,recovery,algebra,negative];values=[json.loads(p.read_text()) for p in receipts]
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for a in values:
            verify(a['input_sha256'])
            if 'artifacts' in a:verify(a['artifacts'])
        a,l,s,r,e,n=values
        for item in(a,l,s):
            if any(item['input_sha256'].get(str(p))!=sha(p) for p in sources):raise ValueError('logic/proofs must bind actual candidate sources')
        expected=['clear_witness',*(f'seed_bit_{i}' for i in range(2,10))]
        if [x['case'] for x in a['records']]!=expected or not all(x['unbounded_property_proven'] and not x['rejecting_counterexample'] and x['expected_result'] for x in a['records']):raise ValueError('clear witness and all eight seed proofs required')
        cases={(phase,mode) for phase in (1,9999,19999,20001,29999,39999) for mode in (0,1,2)}
        if len(l['records'])!=18 or {(x['phase_ps'],x['mode']) for x in l['records']}!=cases or not all(x['passed'] for x in l['records']) or not l['actual_two_stage_reference_capture_wiring_verified'] or not l['raw_withdrawal_logic_preserved'] or l['stable_tracking_observation_ns']!=200:raise ValueError('complete concrete candidate restart/pipeline regression required')
        if not s['selected_leaf_reset_coassertion_contract_supplied_by_candidate'] or [x['case'] for x in s['records']]!=['baseline','fast_reset_polarity_mutant'] or not all(x['expected_result'] for x in s['records']) or not s['records'][0]['unbounded_proven'] or not s['records'][1]['counterexample']:raise ValueError('candidate reset-contract proof and hardware mutation control required')
        if not n['first_capture_stage_tapped_by_startup_mutant_rejected'] or not n['failed_for_expected_pipeline_assertion']:raise ValueError('first-stage startup tap must be rejected')
        if not r['arbitrary_prior_filter_state_repaired_by_one_valid_clear_clock'] or r['environment_constraints']!=0 or not all(x['expected_result'] for x in r['records']):raise ValueError('arbitrary-state DLF clear theorem and controls required')
        for name in ('IntegerPLL_DLF.v','IntegerPLL_B2TH.v','IntegerPLL_DigitalCore.v'):
            if r['input_sha256'].get(str(ROOT/'rtl/selected400'/name))!=sha(candidate/name):raise ValueError('DLF theorem source/parameter context differs')
        if e['assertions']!=16 or not e['all_eight_seed_projections_checked'] or not e['original_comparison_reproduced_by_omitted_equality_witness']:raise ValueError('complete comparison witness identities required')
        records=[]
        for name in expected:
            folder=seeds/name;bit=None if name=='clear_witness' else int(name.rsplit('_',1)[1]);projection=0 if bit is None else bit-2;monitor=CORE_MONITOR
            if bit is None:monitor=monitor.replace('assert(f_last_clear_seed==DLF_Ext_Data);','')
            else:monitor=monitor.replace('assert(f_last_clock_clear);','').replace('assert(f_last_clear_seed==DLF_Ext_Data);',f'assert(f_last_clear_seed[{bit}]==DLF_Ext_Data[{bit}]);')
            replacements={}
            for filename,properties in (('IntegerPLL_DigitalCore.v',monitor),('IntegerPLL_ProgrammedCore.v',PARENT_CONTRACT)):
                path=folder/filename
                if path.read_text()!=(candidate/filename).read_text().replace('endmodule',properties+'\nendmodule'):raise ValueError('monitored candidate source differs')
                replacements[filename]=path
            prefix='read_verilog -formal -sv '+' '.join(str(replacements.get(p.name,p)) for p in sources)+'\nprep -top IntegerPLL_ProgrammedCore\nflatten\nselect -assert-count 1 w:core.CLKDIV_RETIMED\nselect -assert-count 1 w:core.DCO_CODE\ncutpoint w:core.CLKDIV_RETIMED w:core.DCO_CODE\n'
            tail=f'write_json {folder}/abstraction.json\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n'
            if (folder/'export.ys').read_text()!=prefix+tail:raise ValueError('candidate source export recipe differs')
            recipe=f'read_json {folder}/abstracted.json\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/abstract.map {folder}/abstract.aig\n'
            if (folder/'abstract_export.ys').read_text()!=recipe:raise ValueError('candidate abstraction export differs')
            original=json.loads((folder/'abstraction.json').read_text());modified,comparisons=abstract(original,projection)
            if json.loads((folder/'abstracted.json').read_text())!=modified or json.loads((folder/'comparisons.json').read_text())!=comparisons:raise ValueError('comparison abstraction replay differs')
            module=original['modules']['IntegerPLL_ProgrammedCore'];cuts=[cell['connections']['Y'] for cell in module['cells'].values() if cell['type']=='$anyseq'];required=[module['netnames'][n]['bits'] for n in ('core.CLKDIV_RETIMED','core.DCO_CODE')]
            if sorted(cuts)!=sorted(required):raise ValueError('only declared clock/code outputs may become unconstrained')
            occupied={b for table in ('ports','netnames') for net in module[table].values() for b in net['bits'] if isinstance(b,int)};occupied.update(b for cell in module['cells'].values() for values in cell['connections'].values() for b in values if isinstance(b,int))
            if any(any(w in occupied for w in range(q['extra_equality_output_bit']-1,q['extra_equality_output_bit']+2)) for q in comparisons):raise ValueError('fresh comparison wire identifiers required')
            for filename in ('model.aig','abstract.aig'):header(folder/filename)
            log=(folder/'proof.log').read_text()
            if f'read_aiger {folder}/abstract.aig;' not in log or 'Property proved' not in log or 'Property UNDECIDED' in log or 'was asserted in frame' in log:raise ValueError('completed actual candidate AIG proof required')
            records.append(dict(case=name,unbounded_proven=True,source_and_abstraction_replayed=True))
        if (candidate/'IntegerPLL_ProgrammedCore.v').read_text().count('.DLF_Ext_Data({fine_seed,2\'b00})')!=1:raise ValueError('constant low seed bits differ')
        for p in(receipts+[Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','abstract_selected_handoff_comparisons.py','prove_selected_clear_before_unmask_v3.py','review_selected_clear_seed_recovery.py'))]):pins[str(p)]=sha(p)
        verify(pins);save(output,dict(input_sha256=pins,records=records,candidate_two_stage_reference_capture_verified=True,concrete_tracking_and_restart_reachability=True,first_stage_tap_and_reset_polarity_mutants_rejected=True,sampled_handoff_reset_contract_proven=True,logical_clear_seed_recovery_before_unmask_proven=True,assumptions=['external reset initially low for two global samples','programming static between resets','valid discrete clocks'],scope='Layout-unbound asynchronous-enable RTL proposal; candidate-specific source/proof composition with unchanged DLF theorem. Selected-layout timing/model receipts are not transferred.',candidate_layout_bound=False,physical_reset_skew_qualified=False,physical_CDC_qualified=False,closed_loop_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','seeds','logic','reset','recovery','algebra','negative','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.seeds.resolve(),a.logic.resolve(),a.reset.resolve(),a.recovery.resolve(),a.algebra.resolve(),a.negative.resolve(),a.output.resolve())
