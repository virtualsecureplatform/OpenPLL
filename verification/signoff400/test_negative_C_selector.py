"""Check conservative operator selection against a linear support scan and exact bytes."""
import argparse
import copy
import json
from pathlib import Path
import random
import struct
import subprocess
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/select_negative_C_operators.cpp'
    paths=[source,ROOT/'tools/sheet_charge/target_support_index.hpp',ROOT/'tools/sheet_charge/bounded_jsonl_range.hpp',
           ROOT/'tools/charge_compiler/json.hpp',Path('/usr/bin/g++').resolve(),Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths};binary=output/'select_negative_C_operators'
    with lease(4,2,deadline):
        execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',source,'-o',binary],output/'build.log',deadline,2)
        supports=[]
        for field,x,y in [(1,0,0),(2,10,10),*[(3,5*i-60,5*j-60) for i in range(12) for j in range(12)]]:
            supports.append(dict(global_field=field,box=[x,y,x+1,y+1],points=[[x,y],[x+1,y],[x,y+1]],affected_names=['target']))
        support=output/'triangles.jsonl';support.write_text(''.join(json.dumps(r)+'\n' for r in supports))
        mapping=[0,3,2,1];mapfile=output/'fields.json';save(mapfile,mapping)
        operators=[['A',3,0,1,[0,0,1,1],1],['A',0,3,2,[0,0,1,1],1],
            ['A',3,0,3,[2,2,3,3],1],['L',3,0,4,[-1,0,0,0],[10,10,11,10],1,4,0],
            ['L',0,2,5,[0,0,1,0],[10,10,11,10],1,4,0],
            ['F',0,3,6,[-1,0,-1,1],[0,0,1,1],4,1,.25],
            ['F',3,0,7,[0,0,0,1],[2,0,3,1],4,1,.25]]
        rng=random.Random(400)
        for k in range(500):
            x,y=rng.randrange(-70,15),rng.randrange(-70,15)
            operators.append(['A',rng.randrange(4),rng.randrange(4),k+8,[x,y,x+rng.randrange(4),y+rng.randrange(4)],1])
        expected=set()
        def overlap(a,b):return all(max(a[d],b[d])<=min(a[d+2],b[d+2]) for d in (0,1))
        tasks=[];all_expected=set()
        for number,group in enumerate((operators[:251],operators[251:])):
            path=output/f'operators_{number}.jsonl';path.write_text(''.join(json.dumps(op)+'\n' for op in group))
            offset=0
            for line,op in zip(path.read_text().splitlines(keepends=True),group):
                if any((r['global_field']==mapping[op[1]] and overlap(r['box'],op[4]))
                    or (r['global_field']==mapping[op[2]] and overlap(r['box'],op[4] if op[0]=='A' else op[5])) for r in supports):
                    all_expected.add((str(path),offset))
                offset+=len(line.encode())
            size=path.stat().st_size
            for k in range(7):tasks.append(dict(operators=str(path),field_map=str(mapfile),begin_byte=size*k//7,end_byte=size*(k+1)//7))
        base=dict(shards=tasks,support_triangles=str(support),global_fields=4,expected_operators=len(operators),deadline_uptime=deadline)
        reports=[]
        for threads in (1,4):
            cfg,report=output/f'{threads}.json',output/f'{threads}.report.json';native=output/f'native_{threads}'
            save(cfg,dict(base,threads=threads,output=str(native),report=str(report)))
            execute([binary,cfg],output/f'{threads}.log',deadline,2);found=json.loads(report.read_text());reports.append(found)
            observed=set();affected=[]
            for i,task in enumerate(tasks):
                records=(native/f'task_{i}.operators.jsonl').read_text().splitlines();raw=(native/f'task_{i}.offsets.bin').read_bytes()
                assert len(raw)==8*len(records)
                if records:affected.append(i)
                for line,(offset,) in zip(records,struct.iter_unpack('<Q',raw)):
                    assert task['begin_byte']<=offset<task['end_byte']
                    with Path(task['operators']).open('rb') as stream:stream.seek(offset);assert stream.readline().decode().rstrip('\n')==line
                    key=(task['operators'],offset);assert key not in observed;observed.add(key)
            assert observed==all_expected
            assert found['selected_operators']==len(all_expected) and found['affected_tasks']==affected
        assert reports[0]==reports[1]
        for fault in ('gap','overlap','missing_task','wrong_count','wrong_map','bad_support_box'):
            bad=copy.deepcopy(base)
            if fault=='gap':bad['shards'][0]['end_byte']-=1
            if fault=='overlap':bad['shards'][0]['end_byte']+=1
            if fault=='missing_task':bad['shards']=bad['shards'][1:]
            if fault=='wrong_count':bad['expected_operators']+=1
            if fault=='wrong_map':
                other=output/'other_map.json';save(other,[0,1,2,3]);bad['shards'][1]['field_map']=str(other)
            if fault=='bad_support_box':
                other=output/'bad_support.jsonl';r=dict(supports[0],box=[0,0,0,0]);other.write_text(json.dumps(r)+'\n');bad['support_triangles']=str(other)
            cfg=output/(fault+'.json');save(cfg,dict(bad,threads=4,output=str(output/fault),report=str(output/(fault+'.report.json'))))
            p=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True,timeout=60)
            save(output/(fault+'.result.json'),dict(returncode=p.returncode,stderr=p.stderr));assert p.returncode!=0,fault
        verify(pins);artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
             negative_C_operator_selector_controls_pass=True,all_records_match_independent_linear_support_scan=True,
             A_L_F_source_target_and_boundary_cases_checked=True,stable_byte_ownership_checked=True,
             partition_map_count_and_support_box_guards_checked=True,threads_checked=[1,4],
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    run(p.parse_args().output.resolve())
