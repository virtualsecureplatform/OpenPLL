"""Compose selected discrete clear/seed recovery evidence without a timing waiver."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from selected_physical_rtl import source_pins
from abstract_selected_handoff_comparisons import abstract
from prove_selected_clear_before_unmask_v3 import CORE_MONITOR,PARENT_CONTRACT


def header(path):
    with path.open('rb') as stream:fields=stream.readline().decode().split()
    values=list(map(int,fields[1:]));values += [0]*(9-len(values))
    if fields[0]!='aig' or values[3]!=0 or values[5]!=1 or values[6]!=2:raise ValueError('one safety assertion and original two environment constraints required')


def run(seeds,witness,recovery,algebra,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{30});pins=source_pins();records=[]
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        receipts=[seeds/'assessment.json',witness,recovery,algebra];values=[json.loads(p.read_text()) for p in receipts]
        for a in values:
            verify(a['input_sha256'])
            if 'artifacts' in a:verify(a['artifacts'])
            for p,h in pins.items():
                if p.endswith('.v') and a['input_sha256'].get(p)!=h and a is not values[3]:raise ValueError('proof must bind identical selected RTL')
        a,w,r,e=values
        expected=[f'seed_bit_{i}' for i in range(2,10)]
        if [x['case'] for x in a['records']]!=expected or not all(x['unbounded_property_proven'] and not x['rejecting_counterexample'] and x['expected_result'] for x in a['records']):raise ValueError('all eight unbounded variable-seed proofs required')
        if not (w['sampled_clear_clock_precedes_each_unmask_unbounded_proven'] and w['baseline_AIG_independently_reproduced_identically'] and w['abstract_unmask_reachable']):raise ValueError('validated clear-clock witness and nonvacuity control required')
        if not (r['arbitrary_prior_filter_state_repaired_by_one_valid_clear_clock'] and r['output_override_independent_of_prior_state'] and r['environment_constraints']==0):raise ValueError('arbitrary-state DLF clear theorem required')
        if [x['case'] for x in r['records']]!=['baseline','clear_load_removed','output_mask_removed'] or not all(x['expected_result'] for x in r['records']):raise ValueError('both DLF hardware mutation controls required')
        if e['assertions']!=16 or not e['arbitrary_34bit_operands'] or not e['all_eight_seed_projections_checked'] or not e['original_comparison_reproduced_by_omitted_equality_witness']:raise ValueError('complete comparator witness identities required')
        for bit in range(2,10):
            folder=seeds/f'seed_bit_{bit}';monitor=CORE_MONITOR.replace('assert(f_last_clock_clear);','').replace('assert(f_last_clear_seed==DLF_Ext_Data);',f'assert(f_last_clear_seed[{bit}]==DLF_Ext_Data[{bit}]);')
            replacements={}
            for name,properties in (('IntegerPLL_DigitalCore.v',monitor),('IntegerPLL_ProgrammedCore.v',PARENT_CONTRACT)):
                path=folder/name;expected_source=(ROOT/'rtl/selected400'/name).read_text().replace('endmodule',properties+'\nendmodule')
                if path.read_text()!=expected_source:raise ValueError('monitored selected source differs')
                replacements[name]=path
            sources=sorted((ROOT/'rtl/selected400').glob('*.v'))
            prefix='read_verilog -formal -sv '+' '.join(str(replacements.get(p.name,p)) for p in sources)+'\nprep -top IntegerPLL_ProgrammedCore\nflatten\nselect -assert-count 1 w:core.CLKDIV_RETIMED\nselect -assert-count 1 w:core.DCO_CODE\ncutpoint w:core.CLKDIV_RETIMED w:core.DCO_CODE\n'
            tail=f'write_json {folder}/abstraction.json\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n'
            if (folder/'export.ys').read_text()!=prefix+tail:raise ValueError('original export recipe differs')
            recipe=f'read_json {folder}/abstracted.json\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/abstract.map {folder}/abstract.aig\n'
            if (folder/'abstract_export.ys').read_text()!=recipe:raise ValueError('abstract export recipe differs')
            original=json.loads((folder/'abstraction.json').read_text());modified,comparisons=abstract(original,bit-2)
            if json.loads((folder/'abstracted.json').read_text())!=modified or json.loads((folder/'comparisons.json').read_text())!=comparisons:raise ValueError('comparison abstraction differs from verified transformation')
            module=original['modules']['IntegerPLL_ProgrammedCore'];occupied={b for table in ('ports','netnames') for n in module[table].values() for b in n['bits'] if isinstance(b,int)}
            occupied.update(b for c in module['cells'].values() for v in c['connections'].values() for b in v if isinstance(b,int))
            for c in comparisons:
                if any(n in occupied for n in range(c['extra_equality_output_bit']-1,c['extra_equality_output_bit']+2)):raise ValueError('comparison witness must use fresh wire identifiers')
                if c['kept_bit_indices']!=[13,bit+18,*range(28,34)] or set(c['kept_bit_indices'])|set(c['omitted_bit_indices'])!=set(range(34)):raise ValueError('exact selected seed/run/coarse bit partition required')
            for name in ('model.aig','abstract.aig'):header(folder/name)
            log=(folder/'proof.log').read_text()
            if f'read_aiger {folder}/abstract.aig;' not in log or 'Property proved' not in log or 'Property UNDECIDED' in log or 'was asserted in frame' in log:raise ValueError('completed proof must read actual abstracted AIG')
            for name in ('IntegerPLL_DigitalCore.v','IntegerPLL_ProgrammedCore.v','abstraction.json','abstracted.json','comparisons.json','model.aig','abstract.aig','proof.log','export.ys','abstract_export.ys'):
                path=folder/name
                if a['artifacts'].get(str(path))!=sha(path):raise ValueError('complete proof artifact binding required')
            records.append(dict(seed_bit=bit-2,unbounded_proven=True,comparison_abstraction_replayed_identically=True,assertions=1,environment_constraints=2))
        # The two low DLF seed bits are explicit constants in the selected hookup.
        parent=(ROOT/'rtl/selected400/IntegerPLL_ProgrammedCore.v').read_text()
        if parent.count('.DLF_Ext_Data({fine_seed,2\'b00})')!=1:raise ValueError('selected seed projection differs')
        for p in(receipts+[Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','selected_physical_rtl.py','abstract_selected_handoff_comparisons.py','prove_selected_clear_before_unmask_v3.py'))]):pins[str(p)]=sha(p)
        verify(pins);detail=output/'seed_bits.json';save(detail,records)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},eight_variable_seed_bits_unbounded_proven=True,two_low_seed_bits_are_constant_zero=True,sampled_clear_clock_precedes_each_unmask_proven=True,current_seed_sampled_on_prior_clear_clock_proven=True,arbitrary_prior_DLF_state_repaired_by_clear=True,logical_clear_seed_recovery_before_unmask_proven=True,scope='Discrete selected RTL under initial external reset, static programming between resets and explicit sound datapath/command-comparison overapproximations. Proof composition requires the prior clear clock to be a valid physical clock.',physical_clear_arrival_qualified=False,metastability_resolution_qualified=False,reset_recovery_removal_qualified=False,all_crossings_reviewed=False,release_ready=False))
        save(output/'status.json',dict(state='discrete_clear_seed_recovery_reviewed',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('seeds','witness','recovery','algebra','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.seeds.resolve(),a.witness.resolve(),a.recovery.resolve(),a.algebra.resolve(),a.output.resolve())
