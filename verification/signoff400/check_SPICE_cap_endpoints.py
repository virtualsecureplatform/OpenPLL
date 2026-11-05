"""Control and run compiled complete native capacitor endpoint name coverage."""
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
    base=Path('build/signoff400').resolve()
    mapping=base/'startup_timing_spatial_conductor_maps_001/assessment.json'
    core=base/'startup_timing_final_native_R_core_002/assessment.json'
    inventory=base/'startup_timing_SPICE_cap_token_inventory_003/assessment.json'
    names=base/'startup_timing_spatial_conductor_maps_001/native/net_names.jsonl'
    nodes=Path('/tmp/openpll-native-R-core-nh81fygy/native_core_nodes.jsonl')
    deck=Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/trace/retained_rc.spice')
    source=Path('tools/sheet_charge/audit_SPICE_cap_endpoints.cpp').resolve()
    header=Path('tools/charge_compiler/json.hpp').resolve()
    paths=[mapping,core,inventory,names,nodes,deck,source,header,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(8,8,deadline):
        pins={str(p):sha(p) for p in paths}
        m,c,i=[json.loads(p.read_text()) for p in (mapping,core,inventory)]
        for proof,path in ((m,names),(c,nodes)):
            if proof['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('native namespace artifact changed')
        if i['input_sha256'][str(deck)]!=pins[str(deck)]:raise ValueError('native deck changed')
        binary=output/'audit_SPICE_cap_endpoints'
        with (output/'build.log').open('x') as log:
            subprocess.run(['g++','-std=c++20','-O3','-pthread',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        fixture=output/'controls';fixture.mkdir()
        fn=fixture/'names.jsonl';fn.write_text('[0,"ref"]\n[1,"VGND"]\n[2,"signal"]\n')
        fr=fixture/'R.jsonl';fr.write_text(json.dumps(dict(original_conductor='signal',printed_name='signal.n0'))+'\n')
        fd=fixture/'deck.spice';fd.write_text('* comment\nC0 signal.n0 VGND 1f\nC1 fill VGND 0\nC2 signal signal.n0 -1f\nC3 unresolved VGND 1p\n')
        for threads in (1,4,8):
            cfg=fixture/f'config_{threads}.json';report=fixture/f'report_{threads}.json';unknown=fixture/f'unknown_{threads}.jsonl'
            save(cfg,dict(names=str(fn),native_nodes=str(fr),deck=str(fd),threads=threads,deadline_uptime=deadline,report=str(report),unknown_output=str(unknown)))
            execute([binary,cfg],fixture/f'run_{threads}.log',deadline,8)
            r=json.loads(report.read_text())
            expected=dict(capacitor_records=4,nonzero_capacitor_records=3,nonzero_capacitors_with_unresolved_endpoints=1,zero_capacitors_with_unresolved_endpoints=1,unresolved_endpoint_names=2,same_original_conductor_capacitors=1)
            if any(r[k]!=v for k,v in expected.items()):raise ValueError('endpoint coverage controls')
            if unknown.read_text()!='["fill",0,1]\n["unresolved",1,0]\n':raise ValueError('zero extension distinction control')
        fr.write_text(json.dumps(dict(original_conductor='signal',printed_name='VGND'))+'\n')
        failed=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True)
        save(fixture/'collision.result.json',dict(returncode=failed.returncode,stderr=failed.stderr))
        if failed.returncode==0:raise ValueError('conflicting native alias accepted')
        cfg=output/'config.json';report=output/'report.json';unknown=output/'unresolved_endpoints.jsonl'
        save(cfg,dict(names=str(names),native_nodes=str(nodes),deck=str(deck),threads=8,deadline_uptime=deadline,report=str(report),unknown_output=str(unknown)))
        execute([binary,cfg],output/'native.log',deadline,8)
        r=json.loads(report.read_text())
        if r['capacitor_records']!=i['results']['capacitor_records'] or r['nonzero_capacitor_records']!=i['results']['positive_capacitor_records']+i['results']['negative_capacitor_records']:raise ValueError('independent full token scan count mismatch')
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('source changed during endpoint audit')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,report,unknown)},
             all_native_SPICE_capacitor_endpoints_scanned=True,threads=8,controls_1_4_8_threads_zero_extension_and_alias_collision_pass=True,
             all_nonzero_native_SPICE_capacitor_endpoints_registered=r['nonzero_capacitors_with_unresolved_endpoints']==0,results=r,
             zero_extension_namespace_completed=False,full_SPICE_matrix_equivalence_verified=False,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
