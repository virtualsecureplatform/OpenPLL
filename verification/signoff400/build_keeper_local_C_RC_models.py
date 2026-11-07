"""Build unchanged full-C plus wire-R diagnostics with exact zero-R recovery checks."""
import argparse,json,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from build_prototype_full_C_wire_R_v6 import build,rows
from prepare_prototype_analog_reference import subcircuits
from check_prototype_capacitance_paths import certify
from project_prototype_fixed_rail_C_v2 import project,RAILS
from audit_hierarchical_capacitance import number
from resources import lease


def run(extraction,rc,binding,passivity,output):
    receipts=[p/'assessment.json'for p in [extraction,rc,binding,passivity]]
    e,r,b,p=[json.loads(f.read_text())for f in receipts]
    for record in [e,r,b,p]:verify(record['input_sha256']);verify(record['artifacts'])
    if not b['all_RC_terminals_bound_and_connected']or not p['ideal_supply_passivity_certified']:raise ValueError('complete terminal binding and ideal-supply passivity required')
    raw=next(extraction.glob('*/capacitance.spice'));top=raw.parent.name
    if p['input_sha256'].get(str(raw))!=sha(raw)or b['input_sha256'].get(str(raw))!=sha(raw):raise ValueError('capacitor source differs')
    join=binding/'join.json';mapping={re.sub(r'\\(.)',r'\1',x['routed_instance']):x['extracted_instance']for x in json.loads(join.read_text())['mapping']}
    folder=Path(__file__).resolve().parent
    files=[Path(__file__).resolve(),raw,join,*receipts,*[folder/n for n in ['build_prototype_full_C_wire_R_v6.py','project_prototype_fixed_rail_C_v2.py','check_prototype_capacitance_paths.py']]]
    pins={str(f):sha(f)for f in files};output.mkdir(parents=True,exist_ok=False);artifacts={};results=[]
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for corner in ['nom','min','max']:
            parsed=rc/(corner+'.json');pins[str(parsed)]=sha(parsed)
            if r['artifacts'].get(str(parsed))!=pins[str(parsed)]:raise ValueError('wire view differs')
            for attachment in ['driver','farthest']:
                model,metrics,lift=build(raw.read_text(),top,json.loads(parsed.read_text()),mapping,attachment)
                for rail in RAILS:
                    if rail in lift and lift[rail]!=rail:raise ValueError('supply conductor moved')
                pairs={}
                for line in rows(subcircuits(model)[top])[1:-1]:
                    f=line.split()
                    if f[0].startswith('Cflat'):
                        key=tuple(sorted(f[1:3]))
                        if key in pairs:raise ValueError('duplicate emitted capacitor pair')
                        pairs[key]=number(f[3])
                proof=certify(project(pairs,set(RAILS)))
                if not proof['passivity_certified']:raise ValueError('emitted ideal-supply network lacks passivity certificate')
                name=corner+'_'+attachment
                target=output/(name+'.spice');target.write_text(model)
                proof_file=output/(name+'.passivity.json');save(proof_file,proof)
                lift_file=output/(name+'.lift.json');save(lift_file,lift)
                artifacts.update({str(f):sha(f)for f in [target,proof_file,lift_file]})
                results.append(dict(corner=corner,**metrics))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
        ideal_supply_passivity_certified=True,zero_wire_R_exact_device_topology_and_C_operator_match=True,
        SPEF_capacitance_added=False,physical_capacitance_placement_qualified=False,
        attachment_variants_bound_uncertainty=False,cell_internal_wire_resistance_included=False,
        parent_loading_complete=False,native_transient_qualified=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['extraction','rc','binding','passivity','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['extraction','rc','binding','passivity','output']))
