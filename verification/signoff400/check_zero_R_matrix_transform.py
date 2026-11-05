"""Compare ordered zero-R transformation with independent full symmetric sums."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import struct
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def run(collapse_controls,merger_upgrade,output):
    collapse_controls,merger_upgrade,out=(p.resolve() for p in (collapse_controls,merger_upgrade,output))
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    proofs=[p/'assessment.json' for p in (collapse_controls,merger_upgrade)]
    generic,upgrade=[json.loads(p.read_text()) for p in proofs]
    if not generic['spatial_conductor_collapse_controls_pass'] or not upgrade['actual_operator_merge_bytes_identical']:
        raise ValueError('controlled generic transform and merger required')
    baseline=collapse_controls/'collapse_spatial_matrix';merger=Path(upgrade['merger_binary'])
    if sha(baseline)!=generic['artifacts'][str(baseline)] or sha(merger)!=upgrade['input_sha256'][str(merger)]:
        raise ValueError('controlled binary changed')
    source=ROOT/'tools/sheet_charge';compiler=Path(shutil.which('g++')).resolve()
    programs=('collapse_zero_R_matrix','zero_R_matrix_fixture')
    paths=[*proofs,baseline,merger,compiler,Path(__file__).resolve(),ROOT/'tools/charge_compiler/json.hpp',
           *[source/(n+'.cpp') for n in programs],*[source/n for n in ('sparse_runs_v2.hpp','sparse_run_slice.hpp','conductor_map.hpp')]]
    pins={str(p):sha(p) for p in paths}
    with lease(8,8,deadline):
        for name in programs:
            execute([compiler,'-std=c++20','-O3','-Wall','-Wextra','-Wpedantic','-fno-fast-math',
                     '-ffp-contract=off',source/(name+'.cpp'),'-o',out/name],out/(name+'.build.log'),deadline,8)
        matrix=out/'fixture.bin';execute([out/'zero_R_matrix_fixture',matrix],out/'fixture.log',deadline,1)
        n=24;full=[[0]*n for _ in range(n)]
        for i in range(n):
            for j in range(i+1,n):
                weight=(i*7+j*3)%13-6
                full[i][i]+=weight;full[j][j]+=weight;full[i][j]-=weight;full[j][i]-=weight
        for case,roots in enumerate(({3:1,5:1},{3:1,5:1,19:13,21:13},{})):
            root=out/f'case_{case}';root.mkdir()
            active=[i for i in range(n) if i not in roots];numbered={i:j for j,i in enumerate(active)}
            mapping=[numbered[roots.get(i,i)] for i in range(n)]
            mapfile=root/'map.bin'
            mapfile.write_bytes(b'CNETDOF1'+struct.pack('<QQ',n,len(active))+struct.pack('<'+str(n)+'I',*mapping))
            aliases=root/'aliases.jsonl';aliases.write_text(''.join(json.dumps([i,roots[i],mapping[i]])+'\n' for i in sorted(roots)))
            expected=defaultdict(int)
            for i in range(n):
                for j in range(n):expected[mapping[i],mapping[j]]+=full[i][j]
            transformed={}
            for name,binary in (('generic',baseline),('ordered',out/'collapse_zero_R_matrix')):
                work=root/name;work.mkdir();cfg=work/'config.json'
                save(cfg,dict(matrix=str(matrix),voltage_map=str(mapfile),aliases=str(aliases),threads=4,
                     max_accumulator_entries=16,output=str(work/'runs'),deadline_uptime=deadline))
                execute([binary,cfg],work/'native.log',deadline,8)
                summary=json.loads((work/'native.log').read_text())
                assert summary['source_upper_entries']==n*(n+1)//2
                if name=='ordered':
                    assert summary['ordered_entries_without_sort']+summary['exceptional_entries_sorted']==summary['source_upper_entries']
                    assert summary['ordered_entries_without_sort']>0
                    if roots:assert summary['sparse_runs']>2
                cfg=work/'merge.json'
                save(cfg,dict(inputs=list(map(str,sorted((work/'runs').glob('*.bin')))),output=str(work/'matrix.bin'),
                     json_output=str(work/'matrix.jsonl'),deadline_uptime=deadline))
                execute([merger,cfg],work/'merge.log',deadline,1)
                actual={(a,b):int(value) for a,b,value,absolute,terms in map(json.loads,(work/'matrix.jsonl').read_text().splitlines())}
                assert actual=={k:v for k,v in expected.items() if k[0]<=k[1]}
                transformed[name]=work/'matrix.bin'
            assert transformed['generic'].read_bytes()==transformed['ordered'].read_bytes()
            if case==0:
                bad=root/'permuted_map.bin';wrong=mapping[:];wrong[6],wrong[7]=wrong[7],wrong[6]
                bad.write_bytes(b'CNETDOF1'+struct.pack('<QQ',n,len(active))+struct.pack('<'+str(n)+'I',*wrong))
                cfg=root/'bad.json';save(cfg,dict(matrix=str(matrix),voltage_map=str(bad),aliases=str(aliases),
                     max_accumulator_entries=16,output=str(root/'invalid_runs'),deadline_uptime=deadline))
                try:execute([out/'collapse_zero_R_matrix',cfg],root/'bad.log',deadline,8)
                except RuntimeError:pass
                else:raise ValueError('noncompacting map accepted')
        if any(sha(Path(p))!=h for p,h in pins.items()):raise ValueError('control input changed')
        products=[*[out/name for name in programs],matrix,*out.glob('case_*/*/matrix.bin'),*out.glob('case_*/*/matrix.jsonl')]
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in products},
             ordered_zero_R_transform_controls_pass=True,full_symmetric_reference_cases=3,
             controlled_generic_transform_output_bytes_identical=True,
             bounded_exceptional_flush_and_symmetry_factors_checked=True,
             no_alias_identity_and_noncompacting_negative_controls_pass=True,
             physical_RC_qualified=False,release_qualified=False))
        print(json.dumps(dict(ordered_zero_R_transform_controls_pass=True,reference_cases=3)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('collapse-controls','merger-upgrade','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(a.collapse_controls,a.merger_upgrade,a.output)
