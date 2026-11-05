"""Verify full positive-family G topology against independent conductor maps."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def raw_map(path,values,targets):path.write_bytes(b'CNETDOF1'+struct.pack('<QQ',len(values),targets)+struct.pack('<'+'I'*len(values),*values))


def matrix(path,edges):
    with path.open('wb') as out:
        out.write(b'SPCRUN01'+struct.pack('<Q',len(edges)))
        for a,b in edges:
            # Exactly -1 and absolute contribution +1 in x87, one source term.
            out.write(struct.pack('<Q',a<<32|b)+struct.pack('<QH',1<<63,0xbfff)+struct.pack('<QH',1<<63,0x3fff)+struct.pack('<Q',1)+bytes(4))


def run(output):
    output.mkdir(parents=True,exist_ok=False);base=Path('build/signoff400').resolve()
    assembly=base/'startup_timing_known_conductance_001/assessment.json'
    zero=base/'startup_timing_zero_R_voltage_map_002/assessment.json'
    conductors=base/'startup_timing_spatial_conductor_maps_001/assessment.json'
    certificate=base/'startup_timing_nominal_G_edge_graph_certificate_001/assessment.json'
    a,z,c,cert=[json.loads(p.read_text()) for p in (assembly,zero,conductors,certificate)]
    zero_map=zero.parent/'voltage_map.bin';net_map=conductors.parent/'native/voltage_nets.bin'
    matrices=[Path(a['zero_R_constrained_known_G_matrix']),*[Path(f['zero_R_constrained_unit_square_matrix']) for f in a['symbolic_material_families']['material_families']]]
    source=Path('tools/sheet_charge/audit_G_components.cpp').resolve();headers=[Path('tools/charge_compiler/json.hpp').resolve(),Path('tools/sheet_charge/sparse_runs_v2.hpp').resolve()]
    paths=[assembly,zero,conductors,certificate,zero_map,net_map,*matrices,source,*headers,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(2,4,deadline):
        pins={str(p):sha(p) for p in paths}
        if cert['input_sha256'][str(assembly)]!=pins[str(assembly)] or z['input_sha256'][str(conductors)]!=pins[str(conductors)]:raise ValueError('graph namespace lineage changed')
        for proof,path in ((z,zero_map),(c,net_map),*((a,p) for p in matrices)):
            if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('map or G artifact changed')
        binary=output/'audit_G_components'
        with (output/'build.log').open('x') as log:
            subprocess.run(['g++','-std=c++20','-O3',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        fixture=output/'controls';fixture.mkdir();fz=fixture/'zero.bin';fn=fixture/'nets.bin';fm=fixture/'G.bin'
        raw_map(fz,[0,1,2,2,3],4);raw_map(fn,[0,1,1,1,2],3);matrix(fm,[(1,2)])
        def config(where):
            where.mkdir();cfg=where/'config.json';save(cfg,dict(zero_map=str(fz),original_net_map=str(fn),matrices=[str(fm)],deadline_uptime=deadline,component_map=str(where/'components.bin'),report=str(where/'report.json')));return cfg
        where=fixture/'positive';cfg=config(where);execute([binary,cfg],where/'run.log',deadline,4)
        r=json.loads((where/'report.json').read_text())
        if r['positive_weight_graph_components']!=3 or r['constrained_voltage_nodes']!=4:raise ValueError('alias and component identity control')
        for name,edges,nets in (('cross_conductor',[(1,2),(2,3)],[0,1,1,1,2]),('fragmented',[],[0,1,1,1,2]),('cross_alias',[(1,2)],[0,1,1,2,2])):
            matrix(fm,edges);raw_map(fn,nets,3);where=fixture/name;cfg=config(where)
            r=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True);save(where/'result.json',dict(returncode=r.returncode,stderr=r.stderr))
            if r.returncode==0:raise ValueError('graph corruption accepted: '+name)
        cfg=output/'config.json';component_map=output/'constrained_voltage_conductors.bin';report=output/'report.json'
        save(cfg,dict(zero_map=str(zero_map),original_net_map=str(net_map),matrices=list(map(str,matrices)),deadline_uptime=deadline,component_map=str(component_map),report=str(report)))
        execute([binary,cfg],output/'native.log',deadline,4)
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('source changed during G topology proof')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,component_map,report)},results=json.loads(report.read_text()),
             all_conductance_graph_components_match_original_conductors=True,
             exact_edge_graph_kernel_is_original_conductor_constant_subspace=True,
             symbolic_family_multiplier_assumption='strictly positive for every included material family',
             corruption_alias_and_fragmentation_controls_pass=True,
             stored_matrix_exact_nullspace_verified=False,native_charge_constraints_implemented=False,
             final_projection_node_maps_reconciled=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
