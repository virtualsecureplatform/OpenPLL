"""Control full printed EXT parsing, parallel boundaries and serialization bounds."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(merger_upgrade, output):
    merger_upgrade, out = merger_upgrade.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    proof = merger_upgrade/'assessment.json'
    upgrade = json.loads(proof.read_text())
    if not upgrade['actual_operator_merge_bytes_identical']:
        raise ValueError('controlled merger required')
    merger = Path(upgrade['merger_binary'])
    if sha(merger) != upgrade['input_sha256'][str(merger)]:
        raise ValueError('controlled merger changed')
    source = ROOT/'tools/sheet_charge'
    compiler = Path(shutil.which('g++')).resolve()
    programs = ('compile_printed_EXT_v2', 'compare_printed_EXT_matrix_v2', 'printed_EXT_fixtures')
    paths = [Path(__file__).resolve(), proof, merger, compiler,
             ROOT/'tools/charge_compiler/json.hpp', source/'sparse_runs_v2.hpp',
             *[source/(name+'.cpp') for name in programs]]
    pins = {str(p): sha(p) for p in paths}
    with lease(8, 8, deadline):
        for name in programs:
            execute([compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra',
                     '-Wpedantic', '-fno-fast-math', '-ffp-contract=off',
                     source/(name+'.cpp'), '-o', out/name], out/(name+'.build.log'), deadline, 8)
        names = out/'names.jsonl'
        names.write_text(''.join(json.dumps([i,n])+'\n' for i,n in enumerate(('VGND','a','b','c'))))
        ext = out/'fixture.ext'
        ext.write_text('scale 1000 1 500000\nsubstrate "VGND" 0 0 0 0 m1\n'
                       'node "a" 0 1.23457 0 0 m1\nnode "b" 0 0 0 0 m1\n'
                       'node "c" 0 0.0001 0 0 m1\ncap "a" "b" 89.1971\n'
                       'cap "a" "c" -0.000937054\ncap "b" "c" 1e+06\ncap "b" "b" 0.1\n'
                       'node "zero_fill" 0 0 0 0 fomfill\n')
        execute([out/'printed_EXT_fixtures', out], out/'fixture.log', deadline, 1)
        # Independent full symmetric edge assembly with exact decimal arithmetic.
        expected, errors = {}, {}
        for a,b,v,error in ((0,1,'1.23457','0.000005'),(0,3,'0.0001','0.0000000005'),
                            (1,2,'89.1971','0.00005'),(1,3,'-0.000937054','0.0000000005'),
                            (2,3,'1e6','5')):
            for i,j,sign in ((a,a,1),(b,b,1),(min(a,b),max(a,b),-1)):
                expected[i,j] = expected.get((i,j), F(0))+sign*F(v)
                errors[i,j] = errors.get((i,j), F(0))+F(error)
        for threads in (1,4,8):
            root = out/f'threads_{threads}'
            root.mkdir()
            cfg = root/'compile.json'
            save(cfg, dict(ext=str(ext), names=str(names), threads=threads,
                 max_accumulator_entries=16, output=str(root/'runs'), deadline_uptime=deadline,
                 native_internal_units_per_printed_EXT_unit=500000))
            execute([out/'compile_printed_EXT_v2', cfg], root/'compile.log', deadline, 8)
            summary = json.loads((root/'compile.log').read_text())
            assert summary['printed_cap_records']==4 and summary['printed_node_records']==4
            assert summary['same_conductor_edges_ignored']==1 and summary['substrate_records']==1
            assert summary['known_conductor_nodes']==4 and summary['conductor_nodes']==5
            assert summary['explicit_zero_extension_nodes']==1
            assert json.loads((root/'runs/zero_extension_nodes.jsonl').read_text())==[4,'zero_fill']
            for kind in ('value','error'):
                cfg = root/(kind+'.merge.json')
                save(cfg, dict(inputs=list(map(str,sorted((root/'runs').glob('*.'+kind+'.bin')))),
                     output=str(root/(kind+'.bin')), json_output=str(root/(kind+'.jsonl')),
                     deadline_uptime=deadline))
                execute([merger,cfg],root/(kind+'.merge.log'),deadline,1)
                actual = {(a,b):F(v) for a,b,v,absolute,terms in map(json.loads,
                         (root/(kind+'.jsonl')).read_text().splitlines())}
                wanted = expected if kind=='value' else errors
                assert actual.keys()==wanted.keys()
                for key in actual:
                    allowance = (F(1,10**15)*max(F(1),abs(wanted[key])) if kind=='value'
                                 else F(1,10**17)*max(F(1),abs(expected[key])))
                    assert abs(actual[key]-wanted[key]) <= allowance
                    if kind=='error':
                        assert actual[key] >= wanted[key]-F(1,10**18)
            for changed in (False,True):
                cfg = root/('changed.json' if changed else 'compare.json')
                report = cfg.with_suffix('.report.json')
                save(cfg,dict(actual=str(out/('changed.bin' if changed else 'actual.bin')),
                     printed=str(root/'value.bin'), serialization_bounds=str(root/'error.bin'),
                     absolute_tolerance=1e-8,relative_tolerance=2e-12,node_count=5,
                     deadline_uptime=deadline,report=str(report),require_match=False))
                execute([out/'compare_printed_EXT_matrix_v2',cfg],cfg.with_suffix('.log'),deadline,1)
                result=json.loads(report.read_text())
                assert result['within_bounds'] == (not changed)
                if changed:
                    assert result['outside_serialization_and_numerical_bounds']>=2
        for label, extra in (('nonzero_unmapped','node "unmapped" 0 1 0 0 m1\n'),
                             ('unmapped_coupling','cap "zero_fill" "a" 1\n'),
                             ('duplicate_zero_node','node "zero_fill" 0 0 0 0 fomfill\n')):
            bad_ext=out/(label+'.ext')
            bad_ext.write_text(ext.read_text()+extra)
            cfg=out/(label+'.json')
            save(cfg,dict(ext=str(bad_ext),names=str(names),threads=4,max_accumulator_entries=16,
                 output=str(out/(label+'_runs')),deadline_uptime=deadline,
                 native_internal_units_per_printed_EXT_unit=500000))
            try:
                execute([out/'compile_printed_EXT_v2',cfg],out/(label+'.log'),deadline,8)
            except RuntimeError:
                pass
            else:
                raise ValueError('invalid zero extension accepted: '+label)
        if any(sha(Path(p))!=h for p,h in pins.items()):
            raise ValueError('printed EXT control input changed')
        products=[*[out/name for name in programs],names,ext,*out.glob('*.bin'),
                  *out.glob('threads_*/*.bin'),*out.glob('threads_*/*.report.json')]
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in products},
             printed_EXT_matrix_controls_pass=True,thread_counts=[1,4,8],
             exact_decimal_matrix_and_serialization_bounds_checked=True,
             changed_coupling_detected=True,zero_extension_and_three_negative_controls_pass=True,
             full_printed_native_matrix_reconstruction_verified=False,
             physical_RC_qualified=False,release_qualified=False))
        print(json.dumps(dict(printed_EXT_matrix_controls_pass=True,thread_counts=[1,4,8])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--merger-upgrade',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.merger_upgrade,args.output)
