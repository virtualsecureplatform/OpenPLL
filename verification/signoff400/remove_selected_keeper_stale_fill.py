"""Remove only old-route parent fill instances from an isolated keeper assembly."""
import argparse,json
from pathlib import Path
import klayout.db as k
from common_v3 import save,sha,verify
from assemble_selected_keeper_parent import signature


def run(source,output):
    receipt=source/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a['replaced_DCO_definition_only']:raise ValueError('isolated DCO replacement required')
    gds=source/'assembly.gds';l=k.Layout();l.read(str(gds));top=l.cell('IntegerPLL_400MHz_PrototypeTop')
    names=['PROTOTYPE_PARENT_DENSITY_FILL','PROTOTYPE_PARENT_METAL5_FILL']
    before={c.name:signature(l,c)for c in l.each_cell()if c!=top}
    inst=lambda i:(i.cell.name,str(i.cplx_trans),str(i.a),str(i.b),i.na,i.nb)
    retained=sorted(inst(i)for i in top.each_inst()if i.cell.name not in names);removed=[]
    for i in list(top.each_inst()):
        if i.cell.name in names:removed.append(inst(i));i.delete()
    if sorted(x[0]for x in removed)!=sorted(names):raise ValueError('one instance of each old fill domain required')
    if sorted(inst(i)for i in top.each_inst())!=retained:raise ValueError('functional parent instance changed')
    if any(signature(l,l.cell(n))!=v for n,v in before.items()):raise ValueError('cell definition changed')
    output.mkdir(parents=True,exist_ok=False);target=output/'assembly.gds';l.write(str(target))
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p)for p in [Path(__file__).resolve(),Path(__file__).with_name('assemble_selected_keeper_parent.py'),receipt,gds]},
        artifacts={str(target):sha(target)},isolated_keeper_parent=True,only_stale_fill_instances_removed=True,
        removed_instances=removed,all_macro_definitions_and_other_parent_instances_unchanged=True,
        density_fill_regeneration_required=True,parent_DRC_LVS_antenna_density_and_power_qualified=False,
        selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.source.resolve(),a.output.resolve())
