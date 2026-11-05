"""Control complete byte partitions, stable offsets, and independent scalar intervals."""
import argparse
import copy
from fractions import Fraction as Q
import json
from pathlib import Path
import struct
import subprocess
import time
from common import ROOT, save, sha, verify
from compiled_charge import execute
from resources import lease
from test_fringe_interval import atan, endpoint


def run(output, headers):
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/trace_reference_intervals.cpp'
    paths=[source,ROOT/'tools/sheet_charge/fringe_interval.hpp',ROOT/'tools/sheet_charge/conductor_map.hpp',
           ROOT/'tools/sheet_charge/bounded_jsonl_range.hpp',ROOT/'tools/charge_compiler/json.hpp',
           headers/'mpfr.h',Path('/lib/x86_64-linux-gnu/libmpfr.so.6').resolve(),Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths};binary=output/'trace_reference_intervals'
    with lease(4,2,deadline):
        execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off','-I'+str(headers),
                 source,'-l:libmpfr.so.6','-lgmpxx','-lgmp','-o',binary],output/'build.log',deadline,2)
        fields=output/'field_nets.bin'
        fields.write_bytes(b'CNETFLD1'+struct.pack('<QQ',5,3)+struct.pack('<5I',0,1,2,1,0))
        mapping=[0,2,1,4,3];mapfile=output/'field_map.json';save(mapfile,mapping)
        # global fields 0 and 4 alias reference; 1 and 3 alias conductor 1.
        operators=[['A',0,2,1,[0,0,2,3],.75], ['A',3,1,2,[0,0,1,1],.5],
                   ['A',2,4,3,[0,0,1,1],99], ['A',1,2,4,[0,0,1,1],99],
                   ['L',0,2,5,[0,0,0,3],[1,0,1,3],.5,4,0]]
        for direction,edge,rect in ((4,[0,0,0,1],[0,0,1,1]),(1,[0,0,0,1],[-1,0,0,1]),
                                    (2,[0,0,1,0],[0,0,1,1]),(8,[0,0,1,0],[0,-1,1,0])):
            operators.append(['F',0,2,6,edge,rect,direction,.75,.25])
        tasks=[];sources=[]
        for number,group in enumerate((operators[:4],operators[4:])):
            path=output/f'operators_{number}.jsonl'
            path.write_text(''.join(json.dumps(op)+'\n' for op in group));sources.append(path)
            size=path.stat().st_size
            for k in range(8):tasks.append(dict(operators=str(path),field_map=str(mapfile),begin_byte=size*k//8,end_byte=size*(k+1)//8))
        base=dict(precision_bits=128,threads=4,field_map=str(fields),shards=tasks,
                  expected_operators=len(operators),deadline_uptime=deadline)
        reports=[]
        for threads in (1,4):
            cfg,report=output/f'{threads}.json',output/f'{threads}.report.json'
            native=output/f'native_{threads}'
            save(cfg,dict(base,threads=threads,output=str(native),report=str(report)))
            execute([binary,cfg],output/f'{threads}.log',deadline,2)
            found=json.loads(report.read_text());reports.append(found)
            selected=[]
            for task,spec in enumerate(tasks):
                raw=(native/f'task_{task}.operators.jsonl').read_text().splitlines()
                offsets=(native/f'task_{task}.offsets.bin').read_bytes()
                assert len(offsets)==len(raw)*8
                for line,(offset,) in zip(raw,struct.iter_unpack('<Q',offsets)):
                    assert spec['begin_byte']<=offset<spec['end_byte']
                    with Path(spec['operators']).open('rb') as stream:
                        stream.seek(offset);assert stream.readline().decode().rstrip('\n')==line
                    selected.append((spec['operators'],offset))
            assert len(selected)==len(set(selected))==7
            assert found['operators']==len(operators)
            # A01 contributes 4.5 and A02 contributes .5 to diagonal 0 only.
            # L01 contributes 1.5; four F01=.75*original_binary64(.6366)*atan(.25).
            a=atan(Q(1,4),160);factor=Q(.75)*Q(.6366)*4
            expected=(Q(13,2)+factor*a[0],Q(13,2)+factor*a[1])
            edge_expected=(-Q(6)-factor*a[1],-Q(6)-factor*a[0])
            for key,truth in (('diagonal_0_interval',expected),('edge_0_1_interval',edge_expected)):
                v=found[key];low,high=endpoint(v['lower_dyadic']),endpoint(v['upper_dyadic'])
                assert low<=truth[0]<=truth[1]<=high,(key,low,truth,high)
        assert reports[0]==reports[1]
        for label in ('gap','overlap','missing_task','wrong_count','changed_map'):
            bad=copy.deepcopy(base);bad['output']=str(output/label);bad['report']=str(output/(label+'.report.json'))
            if label=='gap':bad['shards'][0]['end_byte']-=1
            if label=='overlap':bad['shards'][0]['end_byte']+=1
            if label=='missing_task':bad['shards']=bad['shards'][1:]
            if label=='wrong_count':bad['expected_operators']+=1
            if label=='changed_map':
                other=output/'other_map.json';save(other,[0,1,2,3,4]);bad['shards'][1]['field_map']=str(other)
            cfg=output/(label+'.json');save(cfg,bad)
            failed=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True,timeout=60)
            save(output/(label+'.result.json'),dict(returncode=failed.returncode,stderr=failed.stderr))
            assert failed.returncode!=0,label
        verify(pins)
        artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
             trace_reference_interval_controls_pass=True,stable_source_offsets_checked=True,
             independent_scalar_reference_checked=True,thread_counts_checked=[1,4],
             gap_overlap_missing_task_count_and_map_changes_rejected=True,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--headers',required=True,type=Path)
    args=parser.parse_args();run(args.output.resolve(),args.headers.resolve())
