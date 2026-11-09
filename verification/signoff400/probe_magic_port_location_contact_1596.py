"""Four native contact/residue controls against the isolated correction candidate."""
import json,os,time
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute

def run():
    output=ROOT/'build/signoff400/selected_magic_port_location_contact_controls_1596'
    output.mkdir(exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    status=output/'status.json'
    try:
        build=ROOT/'build/tools/magic_port_location_candidate_1594'
        receipt=build/'assessment.json';record=json.loads(receipt.read_text())
        binary=build/'install/bin/magic';library=build/'install/lib/magic/tcl/tclmagic.so'
        for path in [binary,library]:
            if record['artifacts'][str(path)]!=sha(path):raise ValueError('pinned native artifact changed')
        tech=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/magic/sky130A.tech')
        script=ROOT/'tools/magic_rcx/fringe_contact_probe.tcl'
        rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{tech}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        pins={str(p):sha(p) for p in [receipt,binary,library,tech,script,rc,Path(__file__).resolve()]}
        save(output/'inputs.json',dict(input_sha256=pins,memory_GiB=.5,CPU=19,
             queue_cap_s=86400,native_case_cap_s=60,maximum_native_cases=4,automatic_identical_retry=False,
             layout_DRC_qualified=False,extractor_fix_qualified=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
        save(status,dict(state='waiting_for_resources',release_ready=False))
        results=[];artifacts={}
        with lease(1,.5,deadline):
            for contact in [0,1]:
                for shield in [0,1]:
                    case=output/f'contact{contact}_shield{shield}';case.mkdir()
                    trace=case/'coupling.jsonl'
                    save(status,dict(state='running_native_control',contact=contact,shield=shield,release_ready=False))
                    command=['env',f'OPENPLL_PROBE_DIRECTORY={case}',f'OPENPLL_PROBE_CONTACT={contact}',
                             f'OPENPLL_PROBE_SHIELD={shield}',f'OPENPLL_COUPLING_TRACE={trace}',
                             'taskset','-c','19',str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)]
                    execute(command,case/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+60),.5)
                    # Only inspect a trace after the native process exits normally.
                    if trace.stat().st_size>16*1024**2:raise ValueError('minimal fixture trace unexpectedly large')
                    active=None;rules=leaves=0;differences=[]
                    for line in trace.read_text().splitlines():
                        row=json.loads(line);kind=row['kind']
                        if kind=='fringe_rule_begin':
                            if active is not None:raise ValueError('nested native fringe rule')
                            active=row;rules+=1
                        elif kind in ['fringe_shield_leaf','fringe_rule_end']:
                            if active is None or any(active[k]!=row[k] for k in ['cell','epoch','fringe_id']):
                                raise ValueError('unmatched native fringe record')
                            if kind=='fringe_shield_leaf':
                                leaves+=1
                                changed={k:dict(begin=active[k],leaf=row[k]) for k in ['reference_length','boundary','direction','coupling_multiplier_hex','substrate_multiplier_hex'] if active[k]!=row[k]}
                                if changed:differences.append(dict(fringe_id=row['fringe_id'],fields=changed))
                            else:active=None
                    if active is not None:raise ValueError('incomplete native fringe group')
                    for name in ['coupling.jsonl','native.log','probe.spice','FringeContactProbe.ext','FringeContactProbe.mag']:
                        path=case/name;artifacts[str(path)]=sha(path)
                    results.append(dict(contact=bool(contact),shield=bool(shield),rules=rules,leaves=leaves,kernel_differences=differences))
        for path,digest in pins.items():
            if sha(path)!=digest:raise ValueError('native control input changed')
        save(output/'assessment.json',dict(results=results,artifacts=artifacts,
             all_native_processes_completed=True,actual_PDK_tables_used=True,production_source_unchanged=True,isolated_contact_residue_candidate=True,
             full_layout_failure_explained=False,extractor_fix_qualified=False,release_ready=False))
        save(status,dict(state='completed_native_diagnostic',release_ready=False))
    except Exception as error:
        save(status,dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise

if __name__=='__main__':run()
