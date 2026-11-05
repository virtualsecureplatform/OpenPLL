"""Check spatial MPFR fringe matrices using exact triangle power-series integrals."""
import argparse
from fractions import Fraction as Q
import json
from pathlib import Path
import time
from common import ROOT, save, sha, verify
from compiled_charge import execute
from resources import lease
from test_fringe_interval import endpoint


def transform(d, u, direction):
    return {4:(d,u), 1:(-d,u), 2:(u,d), 8:(u,-d)}[direction]


def fixture(direction, distributed_source):
    points = [transform(x,y,direction) for x,y in ((0,0),(1,0),(1,1),(0,1))]
    triangles = [[0,1,2],[0,2,3]] if direction in (4,8) else [[0,2,1],[0,3,2]]
    rect = [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]
    start,end = transform(0,0,direction),transform(0,1,direction)
    edge = [start[0],start[1],end[0],end[1]]
    source = dict(points=points,triangles=triangles,prefix='S:') if distributed_source else dict(constant='S')
    return dict(id=f'{direction}_{distributed_source}', source_basis=source,
                target_basis=dict(points=points,triangles=triangles,prefix='T:'),
                operator=['F',1,2,1,edge,rect,direction,0.75,0.25])


def reference(distributed_source, terms):
    # Canonical triangles: 0<=u<=d<=1 and 0<=d<=u<=1.
    targets = [
        {'T:0':(1,-1,0),'T:1':(0,1,-1),'T:2':(0,0,1)},
        {'T:0':(1,0,-1),'T:2':(0,1,0),'T:3':(0,-1,1)},
    ]
    result = {}
    m = Q(1,4);factor = Q(.75)*Q(.6366)
    for triangle, target in enumerate(targets):
        values = {'S:0':(1,0,-1),'S:3':(0,0,1)} if distributed_source else {'S':(1,0,0)}
        values.update({name:tuple(-Q(v) for v in aff) for name,aff in target.items()})
        def moment(p,q):
            return Q(1,(q+1)*(p+q+2)) if triangle==0 else Q(1,(p+1)*(p+q+2))
        for a,x in values.items():
            for b,y in values.items():
                if a>b:continue
                polynomial={}
                for i,(p,q) in enumerate(((0,0),(1,0),(0,1))):
                    for j,(r,s) in enumerate(((0,0),(1,0),(0,1))):
                        polynomial[p+r,q+s]=polynomial.get((p+r,q+s),0)+Q(x[i])*Q(y[j])
                value = sum((-1)**n*m**(2*n+1)*sum(c*moment(p+2*n,q) for (p,q),c in polynomial.items())
                            for n in range(terms))
                error = m**(2*terms+1)*sum(abs(c)*moment(p+2*terms,q) for (p,q),c in polynomial.items())
                low,high = result.get((a,b),(Q(0),Q(0)))
                result[a,b] = low+factor*(value-error),high+factor*(value+error)
    return result


def run(output, headers):
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    source=ROOT/'tools/sheet_charge/main_registered_mpfr.cpp'
    paths=[source,ROOT/'tools/sheet_charge/main_registered_rational.cpp',ROOT/'tools/sheet_charge/fringe_interval.hpp',
           ROOT/'tools/charge_compiler/json.hpp',headers/'mpfr.h',
           Path('/lib/x86_64-linux-gnu/libmpfr.so.6').resolve(),Path(__file__).resolve()]
    pins={str(p):sha(p) for p in paths};binary=output/'main_registered_mpfr'
    with lease(1,2,deadline):
        execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off','-I'+str(headers),
                 source,'-l:libmpfr.so.6','-lgmpxx','-lgmp','-o',binary],output/'build.log',deadline,2)
        cases=[fixture(direction,source) for direction in (1,2,4,8) for source in (False,True)]
        casefile=output/'cases.json';save(casefile,cases);results=[]
        for bits in (128,256,512,1024):
            cfg,report=output/f'{bits}.json',output/f'{bits}.rows.jsonl'
            save(cfg,dict(precision_bits=bits,cases=str(casefile),output=str(report),deadline_uptime=deadline))
            execute([binary,cfg],output/f'{bits}.log',deadline,2)
            found=[json.loads(line) for line in report.read_text().splitlines()]
            assert len(found)==len(cases)
            references={distributed:reference(distributed,bits//4+48) for distributed in (False,True)}
            for case,row in zip(cases,found):
                assert case['id']==row['id'];names=row['nodes'];expected=references[case['id'].endswith('True')]
                observed={}
                for i,j,interval in row['upper_matrix_intervals']:
                    key=tuple(sorted((names[i],names[j])))
                    low,high=endpoint(interval['lower_dyadic']),endpoint(interval['upper_dyadic'])
                    observed[key]=(low,high)
                    ref=expected.get(key,(Q(0),Q(0)))
                    assert low<=ref[0]<=ref[1]<=high,(bits,case['id'],key)
                assert all(key in observed or bounds==(Q(0),Q(0)) for key,bounds in expected.items())
                # Every row sum enclosure contains the exact zero required by partition of unity.
                for name in names:
                    bounds=[v for key,v in observed.items() if name in key]
                    assert sum(v[0] for v in bounds)<=0<=sum(v[1] for v in bounds)
            results.append(dict(precision_bits=bits,spatial_cases=len(cases),
                                independent_triangle_series_enclosures_contained=True))
        verify(pins)
        artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
             spatial_MPFR_fringe_controls_pass=True,all_four_directions_checked=True,
             exact_local_partition_of_unity_checked=True,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--headers',required=True,type=Path)
    args=parser.parse_args();run(args.output.resolve(),args.headers.resolve())
