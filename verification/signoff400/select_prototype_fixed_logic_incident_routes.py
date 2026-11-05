"""Retain nonincident wires when all existing non-spacer cells are unchanged.

Native detailed routing must repair actual conflicts with inserted cells.
Completed zero-DRC routing and independent physical checks remain mandatory.
"""
import json
import os
from pathlib import Path
from common_v3 import save,sha,verify
from select_prototype_local_ECO_routes import change_windows,poses,spacer,tcl_literal


def fixed_changes(before,after):
    changed,_=change_windows(before,after,0)
    if any(name in before and not spacer(before[name]['master']) for name in changed):
        raise ValueError('existing non-spacer cells moved or changed master')
    if not changed:raise ValueError('nonempty inserted-cell ECO required')
    return changed


def run(config):
    import odb
    if config.get('selection_mode')!='incident_only_fixed_logic':
        raise ValueError('explicit fixed-logic incident-only mode required')
    source=Path(config['source']).resolve();checkpoint=Path(config['checkpoint']).resolve()
    output=Path(config['output']).resolve();rr=source/'assessment.json';cr=checkpoint/'assessment.json'
    r,c=[json.loads(f.read_text()) for f in (rr,cr)]
    for record in (r,c):verify(record['input_sha256']);verify(record['artifacts'])
    if (c['input_sha256'].get(str(rr))!=sha(rr)
            or c.get('all_existing_non_spacer_instances_unchanged') is not True):
        raise ValueError('same-source native fixed-logic checkpoint required')
    before_db=odb.dbDatabase.create();odb.read_db(before_db,str(source/'route.odb'))
    after_db=odb.dbDatabase.create();odb.read_db(after_db,str(checkpoint/'pre_antenna.odb'))
    before=before_db.getChip().getBlock();after=after_db.getChip().getBlock()
    changed=fixed_changes(poses(before),poses(after));dirty=set();reasons={};retained=0
    for name in changed:
        inst=after.findInst(name)
        for term in inst.getITerms():
            net=term.getNet()
            if net is not None and str(net.getSigType()) not in ('POWER','GROUND'):
                dirty.add(net.getName());reasons.setdefault(net.getName(),set()).add('inserted_instance_terminal')
    for net in after.getNets():
        if str(net.getSigType()) in ('POWER','GROUND'):continue
        name=net.getName();wire=net.getWire()
        if wire is None:
            dirty.add(name);reasons.setdefault(name,set()).add('unrouted_signal');continue
        if name in dirty:odb.dbWire.destroy(wire)
        else:retained+=1
    if not retained or not dirty:raise ValueError('retained routes and local repair required')
    output.mkdir(parents=True,exist_ok=False)
    script=output/'dirty_nets.tcl'
    script.write_text('set local_eco_dirty_nets [list '+' '.join(tcl_literal(n) for n in sorted(dirty))+']\n')
    odb.write_db(after_db,str(output/'local_unrouted.odb'))
    detail=output/'selection.json';save(detail,dict(changed_instances=changed,
         dirty_nets={n:sorted(v) for n,v in sorted(reasons.items())}))
    files=(rr,cr,source/'route.odb',checkpoint/'pre_antenna.odb',Path(__file__).resolve(),
           Path(__file__).with_name('select_prototype_local_ECO_routes.py'),Path(config['config_path']))
    save(output/'assessment.json',dict(input_sha256={str(f):sha(f) for f in files},
         artifacts={str(f):sha(f) for f in (script,detail,output/'local_unrouted.odb')},
         changed_instances=len(changed),dirty_signal_nets=len(dirty),retained_signal_wires=retained,
         selection_mode='incident_only_fixed_logic',all_existing_non_spacer_instances_unchanged=True,
         neighboring_wire_conflicts_deferred_to_native_detailed_router=True,
         special_power_wires_not_modified=True,postroute_validation_required=True,
         physical_timing_qualified=False,release_ready=False))
    print(json.dumps(dict(changed_instances=len(changed),dirty_nets=len(dirty),retained_wires=retained)))


if __name__=='__main__':
    path=Path(os.environ['OPENPLL_LOCAL_ECO_CONFIG']).resolve();config=json.loads(path.read_text())
    config['config_path']=str(path);run(config)
