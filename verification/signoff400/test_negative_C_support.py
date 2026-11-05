"""Independent fixtures for shared P1 support and complete R-mesh coverage."""
import argparse
import copy
import json
from pathlib import Path
import struct
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/extract_negative_C_support.cpp'
    paths=[source,ROOT/'tools/charge_compiler/json.hpp',Path('/usr/bin/g++').resolve(),Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths};binary=output/'extract_negative_C_support'
    with lease(4,2,deadline):
        execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',source,'-o',binary],output/'build.log',deadline,2)
        targets=output/'targets.json';save(targets,dict(negative_nodes=[
            dict(row=1,original_voltage_nodes=[dict(node=11,name='b',candidate_global_fields=[1,2])]),
            dict(row=2,original_voltage_nodes=[dict(node=12,name='d',candidate_global_fields=[2])])]))
        index=output/'index.bin';index.write_bytes(b'RBSIDX01'+struct.pack('<Q',3)+
            struct.pack('<QII',2**64-1,0,0)+struct.pack('<QII',0,2,0)+struct.pack('<QII',2,1,1))
        bundles=output/'bundles.jsonl';bundles.write_text('\n'.join(json.dumps(r) for r in [
            dict(bundle_id=0,tile_references=[[0,0,'g1',11],[0,0,'g1',13]]),
            dict(bundle_id=1,tile_references=[[1,0,'g1',12]])])+'\n')
        meshes=[dict(tile_serial=11,points=[[0,0],[1,0],[0,1]],point_nodes=['a','b','c'],triangles=[[0,1,2]]),
                dict(tile_serial=12,points=[[1,0],[1,1],[0,1]],point_nodes=['b','d','c'],triangles=[[0,1,2]]),
                dict(tile_serial=13,points=[[10,10],[11,10],[10,11]],point_nodes=['e','f','g'],triangles=[[0,1,2]])]
        parts=[]
        for number,rows in enumerate(([meshes[0],meshes[2]],[meshes[1]])):
            part=output/f'part{number}.jsonl';part.write_text(''.join(json.dumps(r)+'\n' for r in rows));parts.append(str(part))
        geometry=dict(global_fields=3,R_index=str(index),R_bundles=str(bundles),R_parts=parts,expected_R_tiles=3)
        base=dict(targets=str(targets),geometry=geometry,deadline_uptime=deadline)
        vectors=[]
        for threads in (1,4):
            cfg,triangles,report=(output/f'{threads}{suffix}' for suffix in ('.json','.triangles.jsonl','.report.json'))
            save(cfg,dict(base,threads=threads,triangles=str(triangles),report=str(report)))
            execute([binary,cfg],output/f'{threads}.log',deadline,2)
            found=[json.loads(line) for line in triangles.read_text().splitlines()];vectors.append(found)
            self_report=json.loads(report.read_text())
            assert self_report['all_R_tiles_scanned']==3 and self_report['target_nodes']==2
            assert self_report['selected_support_triangles']==2
            assert [(r['tile_serial'],r['global_field'],r['affected_names']) for r in found]==[(11,1,['b']),(12,2,['b','d'])]
            assert {r['name']:r['support_triangles'] for r in self_report['node_support_incidence']}=={'b':2,'d':1}
            assert [r['box'] for r in found]==[[0,0,1,1],[0,0,1,1]]
        assert vectors[0]==vectors[1]
        for fault in ('missing_part','duplicate_tile','unknown_target','wrong_field','bad_triangle','wrong_count'):
            bad=copy.deepcopy(base)
            if fault=='missing_part':bad['geometry']['R_parts']=parts[:1]
            if fault=='duplicate_tile':
                part=output/'duplicate.jsonl';part.write_text(json.dumps(meshes[0])+'\n');bad['geometry']['R_parts']=[*parts,str(part)]
            if fault in ('unknown_target','wrong_field'):
                modified=json.loads(targets.read_text())
                if fault=='unknown_target':modified['negative_nodes'][0]['original_voltage_nodes'][0]['name']='missing'
                else:modified['negative_nodes'][0]['original_voltage_nodes'][0]['candidate_global_fields']=[2]
                f=output/(fault+'.targets.json');save(f,modified);bad['targets']=str(f)
            if fault=='bad_triangle':
                modified=copy.deepcopy(meshes[1]);modified['triangles']=[[0,1,99]]
                f=output/'bad_triangle.jsonl';f.write_text(json.dumps(modified)+'\n');bad['geometry']['R_parts']=[parts[0],str(f)]
            if fault=='wrong_count':bad['geometry']['expected_R_tiles']=4
            cfg=output/(fault+'.json');save(cfg,dict(bad,threads=4,triangles=str(output/(fault+'.triangles')),report=str(output/(fault+'.report'))))
            p=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True,timeout=60)
            save(output/(fault+'.result.json'),dict(returncode=p.returncode,stderr=p.stderr));assert p.returncode!=0,fault
        verify(pins)
        artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
             negative_C_P1_support_controls_pass=True,shared_node_cross_field_support_checked=True,
             complete_mesh_and_target_coverage_guards_checked=True,threads_checked=[1,4],
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
