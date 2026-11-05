"""Build complete nominal floating-sheet G blocks from certified shared templates."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as F
import json
from pathlib import Path
import shutil
import struct
import tempfile
import time
from audit_substrate_reference_binding import x87
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def run(instances,audit,mapping,matrix_controls,output):
    instances,audit,mapping,matrix_controls,out=(p.resolve() for p in (instances,audit,mapping,matrix_controls,output))
    out.mkdir(parents=True,exist_ok=False)
    scratch=Path(tempfile.mkdtemp(prefix='openpll-floating-G-',dir='/tmp'))
    (out/'native').symlink_to(scratch,target_is_directory=True)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipts=[p/'assessment.json' for p in (instances,audit,mapping,matrix_controls)]
    spec,checked,voltage,structure=[json.loads(p.read_text()) for p in receipts]
    if not checked['all_instances_independently_checked'] or not checked['exact_saved_element_matrices_reconstructed']:
        raise ValueError('full independent instance/element audit required')
    if checked['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]) or not structure['matrix_structure_controls_pass']:
        raise ValueError('matching instance lineage and controlled matrix auditor required')
    geometry=json.loads((Path(voltage['source_projection'])/'config.json').read_text())['geometry']
    nodes=Path(json.loads((mapping/'config.json').read_text())['floating_nodes'])
    aliases,templates=map(Path,(geometry['template_aliases'],geometry['templates']))
    parts=list(map(Path,geometry['floating_parts']))
    source=ROOT/'tools/sheet_charge/compile_floating_G.cpp';compiler=Path(shutil.which('g++')).resolve()
    auditor=matrix_controls/'audit_sparse_matrix'
    paths=[*receipts,nodes,aliases,templates,*parts,source,source.parent/'sparse_runs_v2.hpp',
           ROOT/'tools/charge_compiler/json.hpp',compiler,auditor,Path(__file__).resolve(),
           Path(__file__).with_name('audit_substrate_reference_binding.py')]
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,**extra))
    try:
        with lease(8,16,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            for p in (aliases,templates,*parts):
                if pins[str(p)]!=spec['artifacts'][str(p)]:raise ValueError('certified sheet instance/template changed')
            if pins[str(nodes)]!=voltage['input_sha256'][str(nodes)] or pins[str(auditor)]!=structure['artifacts'][str(auditor)]:
                raise ValueError('floating voltage map or controlled auditor changed')
            binary=out/'compile_floating_G'
            execute([compiler,'-std=c++20','-O3','-Wall','-Wextra','-Wpedantic','-fno-fast-math','-ffp-contract=off',
                     source,'-lgmpxx','-lgmp','-o',binary],out/'build.log',deadline,8)
            control=out/'controls';control.mkdir()
            k=[[i,i,'1','1'] for i in range(4)]
            for a,b in ((0,1),(1,2),(2,3),(0,3)):
                k.extend([[a,b,'-1','2'],[b,a,'-1','2']])
            template=dict(global_template_id=0,refinement=1,points_native_internal=[[[str(x),'1'],[str(y),'1']] for x,y in ((0,0),(1,0),(1,1),(0,1))],unit_sheet_stiffness=k)
            (control/'templates.jsonl').write_text(json.dumps(template)+'\n')
            save(control/'aliases.json',[dict(local_template_id='shape',global_template_id=0)])
            (control/'nodes.jsonl').write_text('[1,1,4]\n[2,5,4]\n')
            rows=[dict(physical_field_id=f,nominal_sheet_milliohm=r,local_template_id='shape',
                native_type='test',arithmetic_bookkeeping_field_ids=[]) for f,r in ((2,250),(1,125))]
            (control/'instances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            cfg=dict(global_fields=3,global_voltage_nodes=9,first_floating_voltage=1,
                floating_nodes=str(control/'nodes.jsonl'),templates=str(control/'templates.jsonl'),
                template_aliases=str(control/'aliases.json'),floating_parts=[str(control/'instances.jsonl')],
                expected_instances=2,expected_floating_nodes=8,matrix=str(control/'G.bin'),
                instance_ledger=str(control/'instances_out.jsonl'),deadline_uptime=deadline)
            save(control/'config.json',cfg)
            execute([binary,control/'config.json'],control/'native.log',deadline,8)
            raw=(control/'G.bin').read_bytes();expected={}
            for base,rho in ((1,125),(5,250)):
                for a,b,num,den in k:
                    if a<=b:expected[base+a,base+b]=F(num)/F(den)*1000/rho
            actual={}
            assert raw[:8]==b'SPCRUN01' and len(raw)==16+40*struct.unpack_from('<Q',raw,8)[0]
            for offset in range(16,len(raw),40):
                key=struct.unpack_from('<Q',raw,offset)[0];value=x87(raw[offset+8:offset+18]);absolute=x87(raw[offset+18:offset+28])
                assert absolute==abs(value) and struct.unpack_from('<Q',raw,offset+28)[0]==1
                actual[key>>32,key&0xffffffff]=value
            assert actual==expected
            for label,rho in (('negative_sheet',-1),('zero_sheet',0)):
                bad=[dict(row,nominal_sheet_milliohm=rho) for row in rows]
                (control/(label+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in bad))
                settings=dict(cfg,floating_parts=[str(control/(label+'.jsonl'))],matrix=str(control/(label+'.bin')))
                save(control/(label+'.config.json'),settings)
                try:execute([binary,control/(label+'.config.json')],control/(label+'.log'),deadline,8)
                except RuntimeError:pass
                else:raise ValueError('nonpositive floating sheet accepted')
            config=out/'config.json';matrix=scratch/'floating_G.bin';ledger=scratch/'floating_G_instances.jsonl'
            save(config,dict(global_fields=geometry['global_fields'],global_voltage_nodes=voltage['voltage_nodes'],
                 first_floating_voltage=voltage['R_voltage_nodes']+1,floating_nodes=str(nodes),
                 templates=str(templates),template_aliases=str(aliases),floating_parts=list(map(str,parts)),
                 expected_instances=spec['basis_instances'],expected_floating_nodes=voltage['floating_voltage_nodes'],
                 matrix=str(matrix),instance_ledger=str(ledger),deadline_uptime=deadline))
            status('assembling_all_floating_nominal_conductance_blocks')
            execute([binary,config],out/'native.log',deadline,16)
            result=json.loads((out/'native.log').read_text())
            check_cfg,report=out/'matrix_audit.json',out/'matrix_audit.report.json'
            save(check_cfg,dict(matrix=str(matrix),node_count=voltage['voltage_nodes'],threads=8,
                 maximum_dense_bytes=16*1024**3,deadline_uptime=deadline,scaled_charge_residual_limit=1e-12,report=str(report)))
            status('checking_every_floating_G_row_and_principal_minor')
            execute([auditor,check_cfg],out/'matrix_audit.log',deadline,16)
            numeric=json.loads(report.read_text())
            if not numeric['necessary_checks_pass']:raise ValueError('nominal floating G numerical structure failed')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('floating G source changed')
            products=[binary,config,matrix,ledger,report,out/'native.log',*[p for p in control.iterdir() if p.is_file()]]
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in products},
                 complete_nominal_floating_sheet_G_assembled=True,results=result,numerical_matrix_structure=numeric,
                 exact_template_Laplacian_and_positive_sheet_scaling_verified=True,
                 exact_fixture_and_nonpositive_sheet_controls_pass=True,
                 source_projection_assessment_pending=True,full_spatial_G_matrix_assembled=False,
                 nominal_sheet_reference_temperature_known=False,resistance_PVT_qualified=False,
                 physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('complete_nominal_floating_sheet_G_assembled',results=result)
            print(json.dumps(result))
    except BaseException as error:
        status('failed',reason=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('instances','audit','mapping','matrix-controls','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(a.instances,a.audit,a.mapping,a.matrix_controls,a.output)
