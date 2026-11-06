"""Validate the completed clear-clock witness proof and its reachability control.

Re-export the same baseline AIG and require byte identity before reusing its
completed proof. Does not prove seed equality or physical clear arrival timing.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from prove_selected_clear_before_unmask_v3 import CORE_MONITOR,PARENT_CONTRACT,ROOT,YOSYS,source_pins


def run(previous,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
    old=previous/'clear_witness';original_inputs=previous/'inputs.json';a=json.loads(original_inputs.read_text());verify(a['input_sha256']);pins=source_pins()
    log=(old/'proof.log').read_text()
    if 'Property proved' not in log or 'Property UNDECIDED' in log or 'was asserted in frame' in log:raise ValueError('completed safe witness proof required')
    monitor=CORE_MONITOR.replace('assert(f_last_clear_seed==DLF_Ext_Data);','')
    for name,addition in (('IntegerPLL_DigitalCore.v',monitor),('IntegerPLL_ProgrammedCore.v',PARENT_CONTRACT)):
        expected=(ROOT/'rtl/selected400'/name).read_text().replace('endmodule',addition+'\nendmodule')
        if (old/name).read_text()!=expected:raise ValueError('previous baseline source does not match selected witness')
    paths=[image,original_inputs,Path(__file__).resolve(),*(old/name for name in ('proof.log','model.aig','model.map','export.ys','IntegerPLL_DigitalCore.v','IntegerPLL_ProgrammedCore.v')),*(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','compiled_charge_v2.py','prove_selected_clear_before_unmask_v3.py','selected_physical_rtl.py','prove_handoff_v2.py'))]
    pins.update({str(p):sha(p) for p in paths});prefix=['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image]
    for name in ('baseline_reexport','witness_removed_control'):
        folder=output/name;folder.mkdir()
        for filename in ('IntegerPLL_DigitalCore.v','IntegerPLL_ProgrammedCore.v'):
            text=(old/filename).read_text()
            if name=='witness_removed_control' and filename=='IntegerPLL_DigitalCore.v':
                if text.count('f_last_clock_clear<=DLF_Clear;')!=1:raise ValueError('unique witness update required')
                text=text.replace('f_last_clock_clear<=DLF_Clear;','f_last_clock_clear<=0;')
            p=folder/filename;p.write_text(text);pins[str(p)]=sha(p)
        script=folder/'export.ys';script.write_text((old/'export.ys').read_text().replace(str(old),str(folder)));pins[str(script)]=sha(script)
        save(output/'status.json',dict(state='checking_clear_clock_witness',case=name,release_ready=False));verify(pins)
        with lease(1,4,deadline):execute([*prefix,YOSYS,'-s',script],folder/'export.log',deadline,4)
        if name=='baseline_reexport':
            if sha(folder/'model.aig')!=sha(old/'model.aig'):raise ValueError('independently re-exported baseline AIG differs')
        else:
            abstraction=json.loads((folder/'abstraction.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
            cuts=[c['connections']['Y'] for c in abstraction['cells'].values() if c['type']=='$anyseq']
            if sorted(cuts)!=sorted(abstraction['netnames'][n]['bits'] for n in ('core.CLKDIV_RETIMED','core.DCO_CODE')):raise ValueError('declared abstraction cuts differ')
            with lease(1,4,deadline):execute([*prefix,str(Path(YOSYS).with_name('yosys-abc')),'-c',f'read_aiger {folder}/model.aig; fold; strash; pdr -v -d -T 300'],folder/'proof.log',deadline,4)
            text=(folder/'proof.log').read_text()
            if 'was asserted in frame' not in text or 'Property proved' in text:raise ValueError('witness-removed control must expose abstract unmask reachability')
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file() and p.name!='status.json'},baseline_AIG_independently_reexported_identically=True,sampled_clear_clock_witness_unbounded_proven=True,witness_removed_monitor_counterexample=True,control_changes_monitor_only=True,abstract_unmask_reachable=True,concrete_unmask_reachability_proven_by_this_control=False,scope='Selected reset/startup/handshake RTL with unconstrained feedback-clock and fine-code outputs; initial reset for two global samples and static programming between resets.',seed_equality_proven=False,physical_clear_arrival_qualified=False,reset_recovery_removal_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='clear_clock_witness_and_control_verified',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('previous','image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.previous.resolve(),a.image.resolve(),a.output.resolve())
