"""Bind a reproduced clear-clock witness theorem to a bounded monitor control.

Seed equality and physical timing remain separate, unresolved requirements.
"""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from selected_physical_rtl import ROOT,source_pins
from prove_selected_clear_before_unmask_v3 import CORE_MONITOR,PARENT_CONTRACT


def run(previous,reexport,bounded,output):
    if output.exists():raise FileExistsError(output)
    pins=source_pins();inputs=previous/'inputs.json';a=json.loads(inputs.read_text());verify(a['input_sha256'])
    old=previous/'clear_witness';base=reexport/'baseline_reexport';mutant=reexport/'witness_removed_control'
    for folder,mutation in ((old,False),(base,False),(mutant,True)):
        monitor=CORE_MONITOR.replace('assert(f_last_clear_seed==DLF_Ext_Data);','')
        if mutation:monitor=monitor.replace('f_last_clock_clear<=DLF_Clear;','f_last_clock_clear<=0;')
        for name,properties in (('IntegerPLL_DigitalCore.v',monitor),('IntegerPLL_ProgrammedCore.v',PARENT_CONTRACT)):
            expected=(ROOT/'rtl/selected400'/name).read_text().replace('endmodule',properties+'\nendmodule')
            if (folder/name).read_text()!=expected:raise ValueError('selected source/monitor binding differs')
        script=(folder/'export.ys').read_text()
        if folder!=old and script!=(old/'export.ys').read_text().replace(str(old),str(folder)):raise ValueError('export protocol differs')
        abstraction=json.loads((folder/'abstraction.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
        cuts=[c['connections']['Y'] for c in abstraction['cells'].values() if c['type']=='$anyseq']
        if sorted(cuts)!=sorted(abstraction['netnames'][n]['bits'] for n in ('core.CLKDIV_RETIMED','core.DCO_CODE')):raise ValueError('only declared feedback output cuts allowed')
        for name in ('IntegerPLL_DigitalCore.v','IntegerPLL_ProgrammedCore.v','export.ys','abstraction.json','model.aig','export.log'):pins[str(folder/name)]=sha(folder/name)
    if sha(old/'model.aig')!=sha(base/'model.aig'):raise ValueError('baseline AIG not reproduced identically')
    log=old/'proof.log';text=log.read_text()
    if 'Property proved' not in text or 'Property UNDECIDED' in text or 'was asserted in frame' in text:raise ValueError('unbounded safe baseline required')
    control=bounded/'assessment.json';c=json.loads(control.read_text());verify(c['input_sha256']);verify(c['artifacts'])
    if c['input_sha256'].get(str(mutant/'model.aig'))!=sha(mutant/'model.aig') or c['rejecting_counterexample'] is not True:raise ValueError('counterexample must bind actual monitor mutant')
    native=bounded/'native.log';match=re.search(r'was asserted in frame (\d+)',native.read_text())
    if not match:raise ValueError('bounded rejecting trace required')
    for p in(inputs,log,control,native,Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','selected_physical_rtl.py','prove_selected_clear_before_unmask_v3.py','prove_handoff_v2.py'))):pins[str(p)]=sha(p)
    verify(pins)
    save(output,dict(input_sha256=pins,baseline_AIG_independently_reproduced_identically=True,sampled_clear_clock_precedes_each_unmask_unbounded_proven=True,witness_removed_monitor_counterexample_frame=int(match[1]),abstract_unmask_reachable=True,control_changes_monitor_only=True,concrete_reachability_established_by_this_control=False,assumptions=['initial external reset for two global samples','programming inputs stable between resets','discrete RTL clocks'],abstraction='Only core.CLKDIV_RETIMED and core.DCO_CODE become unconstrained; selected startup/reset/handshake RTL retained.',seed_equality_proven=False,physical_clear_arrival_qualified=False,metastability_resolution_qualified=False,reset_recovery_removal_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('previous','reexport','bounded','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.previous.resolve(),a.reexport.resolve(),a.bounded.resolve(),a.output.resolve())
