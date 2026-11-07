"""Bind exact operator certificates to unchanged diagnostic model bytes."""
import argparse,json,shutil
from pathlib import Path
from common_v3 import save,sha,verify


def run(models,first,remaining,output):
    original=models/'assessment.json';a=json.loads(original.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    certificates=[first/'assessment.json',*[remaining/n/'assessment.json'for n in ['nom_farthest','min_driver','min_farthest','max_driver','max_farthest']]]
    covered={};pins={str(original):sha(original),str(Path(__file__).resolve()):sha(Path(__file__))}
    for receipt in certificates:
        c=json.loads(receipt.read_text());verify(c['input_sha256']);verify(c['artifacts'])
        if not c['result']['passivity_certified']or c['result']['remaining']!=0:raise ValueError('complete exact PSD certificate required')
        source=[Path(p)for p in c['input_sha256']if p.endswith('.spice')]
        if len(source)!=1 or source[0].parent!=models or a['artifacts'].get(str(source[0]))!=sha(source[0]):raise ValueError('certificate model mismatch')
        if source[0].name in covered:raise ValueError('duplicate certificate')
        covered[source[0].name]=source[0];pins[str(receipt)]=sha(receipt)
    expected={c+'_'+v+'.spice'for c in ['min','nom','max']for v in ['driver','farthest']}
    if set(covered)!=expected:raise ValueError('all six operator views required')
    output.mkdir(parents=True,exist_ok=False);artifacts={}
    for name,p in covered.items():
        dest=output/name;shutil.copy2(p,dest);artifacts[str(dest)]=sha(dest)
        if sha(dest)!=sha(p):raise ValueError('model copy changed')
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,ideal_supply_passivity_certified=True,certificate_method='exact GMP rational LDL congruence',original_sufficient_path_certificate_passed=False,zero_wire_R_exact_device_topology_and_C_operator_match=a['zero_wire_R_exact_device_topology_and_C_operator_match'],SPEF_capacitance_added=a['SPEF_capacitance_added'],native_diagnostic_allowed=True,physical_capacitance_placement_qualified=False,parent_loading_complete=False,model_family_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['models','first','remaining','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['models','first','remaining','output']))
