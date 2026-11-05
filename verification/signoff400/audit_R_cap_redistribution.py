"""Audit per-conductor native R capacitance redistribution against EXT inputs."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    base=Path('build/signoff400').resolve();trace=Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/trace')
    snapshot=base/'startup_timing_interface_final_snapshot_export_001/assessment.json'
    core=base/'startup_timing_final_native_R_core_002/assessment.json'
    units=base/'startup_timing_native_printed_cap_scale_003/assessment.json'
    selected=snapshot.parent/'native_result.json';nodes=Path('/tmp/openpll-native-R-core-nh81fygy/native_core_nodes.jsonl')
    ext=trace/'Prototype400_FilledCapacitanceView.ext';res_ext=trace/'Prototype400_FilledCapacitanceView.res.ext'
    source=Path('tools/sheet_charge/audit_R_cap_redistribution.cpp').resolve()
    headers=[Path('tools/charge_compiler/json.hpp').resolve(),Path('tools/sheet_charge/sparse_runs_v2.hpp').resolve()]
    native=Path('/tmp/openpll-magic-origin-source-zi_pqp3t/source/resis')
    native_sources=[native/n for n in ('ResReadExt.c','ResRex.c','ResSimple.c','ResPrint.c')]
    domain=trace.parent/'assessment.json'
    paths=[domain,snapshot,core,units,selected,nodes,ext,res_ext,source,*headers,*native_sources,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(8,8,deadline):
        pins={str(p):sha(p) for p in paths};s,c,u=[json.loads(p.read_text()) for p in (snapshot,core,units)]
        for proof,path in ((s,selected),(c,nodes)):
            if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('native identity artifact changed')
        if s['input_sha256'].get(str(res_ext))!=pins[str(res_ext)] or json.loads(domain.read_text())['artifacts'][str(ext)]!=pins[str(ext)]:raise ValueError('native EXT source changed')
        with ext.open() as stream:
            scale=next(line.split()[1:] for line in stream if line.startswith('scale '))
        if scale!=['1000','1','500000']:raise ValueError('corrected native EXT R C D scale changed')
        if u['native_internal_units_per_printed_EXT_unit']!='1':raise ValueError('native cap scale mismatch')
        read,rex,simple,printer=[p.read_text() for p in native_sources]
        node_body=read.split('ResReadNode(int argc',1)[1].split('\n}',1)[0]
        if 'capacitance' in node_body:raise ValueError('native node-ground import behavior changed')
        if 'ResOptionsFlags |= ResOpt_Signal;' not in rex or 'node1->capacitance += MagAtof(argv[COUPLEVALUE]);' not in read or 'node2->capacitance += MagAtof(argv[COUPLEVALUE]);' not in read:raise ValueError('native coupling import behavior changed')
        if 'capperarea = totalcap / totalarea;' not in simple or 'workingNode->rn_float.rn_area *= capperarea;' not in simple or '(snode->rn_float.rn_area / ExtCurStyle->exts_capScale)' not in printer:raise ValueError('native R cap distribution/output behavior changed')
        binary=output/'audit_R_cap_redistribution'
        with (output/'build.log').open('x') as log:
            subprocess.run(['g++','-std=c++20','-O3','-pthread','-fno-fast-math',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        fixture=output/'controls';fixture.mkdir();fs=fixture/'selected.json';fn=fixture/'nodes.jsonl';fe=fixture/'original.ext';fr=fixture/'final.res.ext'
        save(fs,dict(selected_groups=[dict(group=i,original=n) for i,n in ((1,'signal'),(2,'other'),(3,'VGND'))]))
        fn.write_text(''.join(json.dumps(dict(original_conductor=n,native_group_id=str(i),printed_name=p))+'\n' for i,n,p in ((1,'signal','s0'),(1,'signal','s1'),(2,'other','o0'),(3,'VGND','VGND'))))
        fe.write_text('node "signal" 0 100 0 0 m1\nnode "other" 0 50 0 0 m1\nsubstrate "VGND" 0 0 0 0 pwell\ncap "signal" "other" 3\ncap "signal" "VGND" 7\n')
        fr.write_text('rnode "s0" 0 -2 0 0 0\nrnode "s1" 0 12 0 0 0\nrnode "o0" 0 3 0 0 0\nrnode "VGND" 0 7 0 0 0\n')
        for threads in (1,4,8):
            cfg=fixture/f'config_{threads}.json';report=fixture/f'report_{threads}.json';groups=fixture/f'groups_{threads}.jsonl'
            save(cfg,dict(selected=str(fs),native_nodes=str(fn),ext=str(fe),res_ext=str(fr),threads=threads,deadline_uptime=deadline,report=str(report),group_output=str(groups)))
            execute([binary,cfg],fixture/f'run_{threads}.log',deadline,8)
            r=json.loads(report.read_text())
            if r['selected_incident_coupling_C_sum_raw']!=20 or r['selected_exported_R_node_C_sum_raw']!=20 or r['selected_original_ground_C_sum_raw']!=150 or r['absolute_group_coupling_prediction_error_sum_raw']!=0:raise ValueError('independent native C conservation controls')
        cfg=output/'config.json';report=output/'report.json';groups=output/'groups.jsonl'
        save(cfg,dict(selected=str(selected),native_nodes=str(nodes),ext=str(ext),res_ext=str(res_ext),threads=8,deadline_uptime=deadline,report=str(report),group_output=str(groups)))
        execute([binary,cfg],output/'native.log',deadline,8)
        result=json.loads(report.read_text())
        if result['selected_groups']!=s['selected_group_count']:raise ValueError('full selected-group coverage')
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('source changed during audit')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,report,groups)},
             all_selected_R_groups_original_and_exported_capacitances_audited=True,
             exact_signed_fixture_controls_1_4_8_pass=True,
             native_source_imports_incident_coupling_into_R_node_capacitance=True,
             native_source_does_not_import_node_ground_C_in_ResReadNode=True,
             results=result,prediction_errors_are_diagnostic_not_qualification_bounds=True,
             native_R_capacitance_distribution_physical_qualified=False,
             full_SPICE_matrix_equivalence_verified=False,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
