"""Check the layout-unbound candidate's sampled handoff reset contract.

Feedback-clock output is unconstrained to admit arbitrary stalls. Physical
reset skew and recovery/removal remain outside this discrete proof.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from selected_physical_rtl import source_pins
from prove_selected_handoff_reset_contract_v2 import PROPERTIES
from prove_handoff_v2 import YOSYS


def run(candidate,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    catalog=candidate/'sources.json';a=json.loads(catalog.read_text());verify(a['basis_input_sha256']);sources=sorted(candidate.glob('*.v'));pins=source_pins()
    if len(sources)!=9:raise ValueError('complete candidate source set required')
    for p in sources:
        if a['source_sha256'].get(str(p.relative_to(ROOT)))!=sha(p):raise ValueError('candidate source identity differs')
        pins[str(p)]=sha(p)
    for p in(catalog,image,Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','compiled_charge_v2.py','selected_physical_rtl.py','prove_selected_handoff_reset_contract_v2.py','prove_handoff_v2.py'))):pins[str(p)]=sha(p)
    prefix=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image];records=[];parent=candidate/'IntegerPLL_ProgrammedCore.v';save(output/'inputs.json',dict(input_sha256=pins,source_catalog=str(catalog),physical_layout_bound=False,clock_output_overapproximation='core.CLKDIV_RETIMED unconstrained',release_ready=False))
    try:
        for name in ('baseline','fast_reset_polarity_mutant'):
            folder=output/name;folder.mkdir();text=parent.read_text()
            if name!='baseline':
                before='if(!RESET_N) dco_reset_pipe<=0;'
                if text.count(before)!=1:raise ValueError('unique fast reset assignment required')
                text=text.replace(before,"if(!RESET_N) dco_reset_pipe<=2'b11;")
            source=folder/'top.v';source.write_text(text.replace('endmodule',PROPERTIES+'\nendmodule'));script=folder/'export.ys';script.write_text('read_verilog -formal -sv '+' '.join(str(source if p==parent else p) for p in sources)+f'\nchparam -set DLF_UPDATE_ON_PLLOUT 0 IntegerPLL_ProgrammedCore\nprep -top IntegerPLL_ProgrammedCore\nflatten\nselect -assert-count 1 w:core.CLKDIV_RETIMED\ncutpoint w:core.CLKDIV_RETIMED\nwrite_json {folder}/abstraction.json\nclk2fflogic\nopt\ndelete -output\ntechmap\nopt\naigmap\nopt_clean\nwrite_aiger -zinit -symbols -map {folder}/model.map {folder}/model.aig\n');pins[str(source)]=sha(source);pins[str(script)]=sha(script);verify(pins);save(output/'status.json',dict(state='checking_candidate_reset_contract',case=name,release_ready=False))
            with lease(1,4,deadline):
                execute([*prefix,YOSYS,'-s',script],folder/'export.log',deadline,4)
                abstraction=json.loads((folder/'abstraction.json').read_text())['modules']['IntegerPLL_ProgrammedCore'];cuts=[c['connections']['Y'] for c in abstraction['cells'].values() if c['type']=='$anyseq']
                if cuts!=[abstraction['netnames']['core.CLKDIV_RETIMED']['bits']]:raise ValueError('only declared feedback-clock output may become unconstrained')
                with (folder/'model.aig').open('rb') as stream:header=stream.readline().decode().split()
                fields=list(map(int,header[1:]));fields += [0]*(9-len(fields))
                if header[0]!='aig' or fields[5]!=7 or fields[6]!=1:raise ValueError('seven assertions and one initial-reset constraint required')
                solver='pdr -v -d -T 120' if name=='baseline' else 'bmc3 -F 32 -T 30 -v';execute([*prefix,str(Path(YOSYS).with_name('yosys-abc')),'-c',f'read_aiger {folder}/model.aig; fold; strash; {solver}'],folder/'proof.log',deadline,4)
            log=(folder/'proof.log').read_text();safe='Property proved' in log;unsafe='was asserted in frame' in log;valid=(safe and not unsafe) if name=='baseline' else (unsafe and not safe);records.append(dict(case=name,unbounded_proven=safe,counterexample=unsafe,expected_result=valid))
            if not valid:raise ValueError('candidate reset proof/control result differs: '+name)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file() and p.name not in ('inputs.json','status.json')},records=records,selected_leaf_reset_coassertion_contract_supplied_by_candidate=True,arbitrary_clock_stalls_allowed=True,assumptions=['external reset initially low','discrete RTL clocks'],physical_reset_skew_qualified=False,reset_recovery_removal_qualified=False,candidate_layout_bound=False,release_ready=False));save(output/'status.json',dict(state='candidate_sampled_reset_contract_proven',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('candidate','image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.candidate.resolve(),a.image.resolve(),a.output.resolve())
