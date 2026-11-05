"""Classify exact G graph components without assigning floating charge values."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def raw_map(path,magic,values,targets):path.write_bytes(magic+struct.pack('<QQ',len(values),targets)+struct.pack('<'+'I'*len(values),*values))


def run(output):
    output.mkdir(parents=True,exist_ok=False);base=Path('build/signoff400').resolve()
    components=base/'startup_timing_G_components_001/assessment.json';zero=base/'startup_timing_zero_R_voltage_map_002/assessment.json'
    conductors=base/'startup_timing_spatial_conductor_maps_001/assessment.json';basis=base/'startup_timing_floating_basis_index_001/assessment.json'
    devices=base/'startup_timing_final_device_basis_audit_001/assessment.json';ports=base/'startup_timing_external_port_binding_001/assessment.json'
    proofs=[components,zero,conductors,basis,devices,ports];comp,z,c,b,d,p=[json.loads(f.read_text()) for f in proofs]
    component_map=components.parent/'constrained_voltage_conductors.bin';zero_map=zero.parent/'voltage_map.bin';field_nets=conductors.parent/'native/field_nets.bin'
    index=basis.parent/'fields.idx';joins=devices.parent/'native_device_terminal_join.jsonl';port_rows=ports.parent/'ports.json'
    floating=Path('/tmp/openpll-spatial-charge-9phv_ewr/native/floating_nodes.jsonl')
    source=Path('tools/sheet_charge/classify_G_components.cpp').resolve();headers=[Path('tools/charge_compiler/json.hpp').resolve(),Path('tools/sheet_charge/sparse_runs_v2.hpp').resolve()]
    paths=[*proofs,component_map,zero_map,field_nets,index,joins,port_rows,floating,source,*headers,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(2,4,deadline):
        pins={str(f):sha(f) for f in paths}
        for proof,path in ((comp,component_map),(z,zero_map),(c,field_nets),(b,index),(d,joins),(p,port_rows)):
            if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('component/binding artifact changed')
        if c['input_sha256'][str(floating)]!=pins[str(floating)]:raise ValueError('floating namespace source changed')
        for proof in (zero,conductors):
            if comp['input_sha256'][str(proof)]!=pins[str(proof)]:raise ValueError('G component namespace differs')
        binary=output/'classify_G_components'
        with (output/'build.log').open('x') as log:
            subprocess.run(['g++','-std=c++20','-O3',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        fixture=output/'controls';fixture.mkdir();fz=fixture/'zero.bin';fc=fixture/'components.bin';ff=fixture/'fields.bin';fi=fixture/'fields.idx';fn=fixture/'floating.jsonl';fd=fixture/'devices.jsonl';fp=fixture/'ports.json'
        raw_map(fz,b'CNETDOF1',[0,1,2,2,3,4],5);raw_map(fc,b'CNETDOF1',[0,1,1,2,2],3);raw_map(ff,b'CNETFLD1',[0,1,2],3)
        fi.write_bytes(b'FBSIDX01'+struct.pack('<Q',3)+bytes(32)+struct.pack('<QII',0,64,0));fn.write_text('[2,4,2]\n')
        fd.write_text(json.dumps(dict(terminals=[[1,'p1',1,'n1'],[2,'p2',2,'n2']]))+'\n');save(fp,[dict(original_voltage_id=3,constrained_voltage_id=2)])
        def config(where):
            where.mkdir();cfg=where/'config.json';save(cfg,dict(zero_map=str(fz),components=str(fc),field_nets=str(ff),floating_index=str(fi),floating_nodes=str(fn),devices=str(fd),ports=str(fp),expected_floating=1,deadline_uptime=deadline,role_output=str(where/'roles.bin'),unattached_output=str(where/'unattached.bin'),report=str(where/'report.json')));return cfg
        where=fixture/'positive';cfg=config(where);execute([binary,cfg],where/'run.log',deadline,4);r=json.loads((where/'report.json').read_text())
        if r['unextracted_floating_components']!=1 or r['device_or_port_attached_components']!=1 or r['other_native_R_components_without_device_or_port']!=0:raise ValueError('component role control')
        for name,text in (('wrong_basis','[2,2,2]\n'),('duplicate_field','[2,4,2]\n[2,4,2]\n')):
            fn.write_text(text);where=fixture/name;cfg=config(where);result=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True)
            save(where/'result.json',dict(returncode=result.returncode,stderr=result.stderr))
            if result.returncode==0:raise ValueError('invalid floating binding accepted')
        cfg=output/'config.json';roles=output/'component_roles.bin';unattached=output/'unattached_components.bin';report=output/'report.json'
        save(cfg,dict(zero_map=str(zero_map),components=str(component_map),field_nets=str(field_nets),floating_index=str(index),floating_nodes=str(floating),devices=str(joins),ports=str(port_rows),expected_floating=b['indexed_instances'],deadline_uptime=deadline,role_output=str(roles),unattached_output=str(unattached),report=str(report)))
        execute([binary,cfg],output/'native.log',deadline,4);result=json.loads(report.read_text())
        if result['native_devices']!=d['native_exported_devices'] or result['native_terminal_bindings']!=d['native_exported_terminal_bindings'] or result['external_ports']!=p['ports']:raise ValueError('complete terminal/port scan required')
        if any(sha(f)!=pins[str(f)] for f in paths):raise ValueError('source changed during component classification')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(f):sha(f) for f in (binary,roles,unattached,report)},results=result,
             every_graph_component_classified_against_all_devices_ports_and_floating_basis=True,
             all_floating_basis_voltages_match_their_physical_original_conductors=True,
             wrong_basis_and_duplicate_controls_rejected=True,
             role_format='GROLE001 then LE u64 component_count, u64 role_count, u8 per component',
             role_codes={'0':'abstract reference','1':'native device or external port attachment','2':'unextracted physical floating conductor','3':'other native R component without native device or port'},
             unattached_format='GUNATT01 then LE u64 entry_count, u64 component_count, u32 component IDs',
             floating_initial_charge_values_assigned=False,charge_constraints_implemented_in_native_solver=False,
             final_projection_node_maps_reconciled=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
