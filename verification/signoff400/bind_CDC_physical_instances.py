"""Read synchronizer placements and actual pin/net identities from the frozen routed database."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def word(s):
    if any(c in s for c in '{}\n\r\t'):raise ValueError('unsupported Tcl identifier delimiter')
    return '{'+s+'}'


def inside(config):
    c=json.loads(config.read_text());verify({c['openroad']:c['openroad_sha256']})
    remaining=c['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    if remaining<=0:raise TimeoutError('CDC physical binding deadline')
    subprocess.run([c['openroad'],'-exit',c['script']],check=True,timeout=remaining)
    save(Path(c['native_receipt']),dict(openroad=c['openroad'],openroad_sha256=sha(Path(c['openroad'])),read_only_database_query_completed=True))


def run(obligations,route,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    def status(state,**kw):save(output/'status.json',dict(state=state,release_qualified=False,**kw))
    try:
        receipt=obligations/'assessment.json';a=json.loads(receipt.read_text());data=obligations/'obligations.json'
        rreceipt=route/'assessment.json';r=json.loads(rreceipt.read_text());db=route/'route.odb'
        if a.get('all_marked_two_stage_chains_bound_to_routed_cells') is not True:raise ValueError('complete routed chain obligations required')
        # The obligations must have been derived from this same route receipt.
        inventory_receipt=next(Path(p) for p in a['input_sha256'] if p.endswith('/startup_timing_routed_CDC_inventory_001/assessment.json'))
        inventory=json.loads(inventory_receipt.read_text())
        if inventory['input_sha256'].get(str(rreceipt))!=sha(rreceipt):raise ValueError('CDC obligations refer to another route')
        image=ROOT/'build/apptainer/openpll-release-modern.sif';openroad=next(p for p in r['input_sha256'] if p.endswith('/bin/openroad'))
        paths=[receipt,data,rreceipt,db,inventory_receipt,image,Path(__file__).resolve()]
        status('waiting_for_physical_CDC_query_lease')
        with lease(1,4,deadline):
            pins={str(p):sha(p) for p in paths}
            if pins[str(data)]!=a['artifacts'][str(data)] or pins[str(db)]!=r['artifacts'][str(db)] or pins[str(inventory_receipt)]!=a['input_sha256'][str(inventory_receipt)]:
                raise ValueError('physical CDC source changed')
            chains=json.loads(data.read_text())['synchronizers'];tsv=output/'physical.tsv';script=output/'query.tcl'
            text=f'read_db {word(str(db))}\nset block [ord::get_db_block]\nset out [open {word(str(tsv))} w]\n'
            text+='puts $out [join [list UNITS [$block getDbUnitsPerMicron]] "\\t"]\n'
            text+='''proc lookup {block candidates} {
 set found {}
 foreach name $candidates {
  set inst [$block findInst $name]
  if {$inst ne {NULL} && $inst ni $found} {lappend found $inst}
 }
 if {[llength $found]!=1} {error {missing or ambiguous physical instance}}
 return [lindex $found 0]
}
'''
            for chain in chains:
                name=word(chain['id'])
                for index,stage in enumerate(chain['stages']):
                    candidates=list(dict.fromkeys([stage['mapped_cell'],stage['routed_cell'],'\\'+stage['mapped_cell']]))
                    text+=f'set inst [lookup $block [list {" ".join(map(word,candidates))}]]\nlassign [$inst getLocation] x y\n'
                    text+=f'puts $out [join [list STAGE {name} {index} [$inst getName] [[$inst getMaster] getName] $x $y [$inst getOrient]] "\\t"]\n'
                    control='RESET_B' if '__dfrtp_' in stage['routed_master'] else 'SET_B'
                    text+=f'foreach pin {{CLK D Q {control}}} {{\n set term [$inst findITerm $pin]\n if {{$term eq {{NULL}} || [$term getNet] eq {{NULL}}}} {{error {{missing physical synchronizer terminal/net}}}}\n set net [$term getNet]\n'
                    text+=f' puts $out [join [list TERM {name} {index} $pin [$net getName] [$term getIoType] [expr {{[$net getWire] ne {{NULL}}}}]] "\\t"]\n'
                    if index==0:
                        text+=f' if {{$pin eq {{Q}}}} {{foreach fan [$net getITerms] {{puts $out [join [list FANOUT {name} [[$fan getInst] getName] [[$fan getMTerm] getName] [$fan getIoType]] "\\t"]}}}}\n'
                    text+='}\n'
            text+='close $out\n';script.write_text(text)
            cfg,native=output/'query.json',output/'native_receipt.json';save(cfg,dict(openroad=openroad,openroad_sha256=r['input_sha256'][openroad],
                 script=str(script),native_receipt=str(native),deadline_uptime=deadline))
            status('reading_actual_synchronizer_instances_and_nets')
            execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,
                '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',
                Path(__file__).resolve(),'--inside',cfg],output/'query.log',deadline,4)
            records={c['id']:dict(id=c['id'],stages={},first_Q_net_terminals=[]) for c in chains};units=None
            for line in tsv.read_text().splitlines():
                f=line.split('\t');kind=f[0]
                if kind=='UNITS':
                    if units is not None or len(f)!=2 or int(f[1])<=0:raise ValueError('unique positive physical unit scale required')
                    units=int(f[1]);continue
                record=records[f[1]]
                if kind=='STAGE':
                    if len(f)!=8 or f[2] in record['stages']:raise ValueError('unique complete physical stage required')
                    record['stages'][f[2]]=dict(instance=f[3],master=f[4],origin_dbu=[int(f[5]),int(f[6])],orientation=f[7],terminals={})
                elif kind=='TERM':
                    if len(f)!=7:raise ValueError('physical terminal schema')
                    terminals=record['stages'][f[2]]['terminals']
                    if f[3] in terminals:raise ValueError('duplicate physical terminal')
                    terminals[f[3]]=dict(net=f[4],direction=f[5],routed_wire_present=f[6]=='1')
                elif kind=='FANOUT':
                    if len(f)!=5:raise ValueError('physical fanout schema')
                    record['first_Q_net_terminals'].append(dict(instance=f[2],pin=f[3],direction=f[4]))
                else:raise ValueError('unknown physical query record')
            if units is None:raise ValueError('missing physical unit scale')
            direct=0
            for chain in chains:
                record=records[chain['id']]
                if set(record['stages'])!={'0','1'}:raise ValueError('incomplete physical chain')
                for index,stage in enumerate(chain['stages']):
                    actual=record['stages'][str(index)]
                    if actual['master']!=stage['routed_master'] or len(actual['terminals'])!=4:raise ValueError('physical master/pin coverage differs')
                first,second=[record['stages'][str(i)] for i in range(2)]
                record['direct_first_Q_to_second_D_net']=first['terminals']['Q']['net']==second['terminals']['D']['net']
                direct+=record['direct_first_Q_to_second_D_net']
                record['origin_manhattan_distance_dbu']=sum(abs(a-b) for a,b in zip(first['origin_dbu'],second['origin_dbu']))
                record['distance_is_not_routed_wire_length_or_timing']=True
            verify(pins);report=output/'binding.json';save(report,dict(database_units_per_micron=units,chains=list(records.values()),
                 placements_are_digital_block_local=True,final_parent_GDS_binding_qualified=False))
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (script,cfg,native,tsv,report)},
                 all_synchronizer_stages_bound_to_routed_database=True,synchronizers=len(chains),direct_interstage_data_nets=direct,
                 physical_pin_and_first_stage_fanout_inventory_complete=True,routed_database_modified=False,
                 delay_resolution_or_metastability_bound_qualified=False,final_GDS_connectivity_binding_qualified=False,
                 physical_CDC_qualified=False,release_qualified=False))
            status('physical_CDC_instance_and_net_binding_complete',synchronizers=len(chains),direct_interstage_data_nets=direct)
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',type=Path)
    for name in ('obligations','route','output'):p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.inside:inside(a.inside)
    elif all((a.obligations,a.route,a.output)):run(a.obligations.resolve(),a.route.resolve(),a.output.resolve())
    else:p.error('obligations, route and output required')
