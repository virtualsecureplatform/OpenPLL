"""Verify MPFR fringe enclosures against independent exact rational series."""
import argparse
from fractions import Fraction as Q
import json
from pathlib import Path
import time
from common import ROOT, save, sha, verify
from compiled_charge import execute
from resources import lease


def add(a, b): return a[0]+b[0], a[1]+b[1]
def scale(a, x): return tuple(sorted((a[0]*x, a[1]*x)))
def sub(a, b): return add(a, scale(b, -1))


def atan_series(x, terms):
    assert abs(x) <= Q(1, 2)
    value = sum((-1)**k*x**(2*k+1)/(2*k+1) for k in range(terms))
    next_term = (-1)**terms*x**(2*terms+1)/(2*terms+1)
    return tuple(sorted((value, value+next_term)))


def atan(x, terms):
    if x < 0: return scale(atan(-x, terms), -1)
    pi = scale(sub(scale(atan_series(Q(1, 5), terms), 4), atan_series(Q(1, 239), terms)), 4)
    if x > 1: return sub(scale(pi, Q(1, 2)), atan(1/x, terms))
    if x > Q(1, 2):
        return add(scale(pi, Q(1, 4)), atan_series((x-1)/(x+1), terms))
    return atan_series(x, terms)


def log_series(x, terms):
    # log(x) = 2*atanh((x-1)/(x+1)); x in [1,2]. Bound the positive tail.
    assert 1 <= x <= 2
    t = (x-1)/(x+1)
    value = 2*sum(t**(2*k+1)/(2*k+1) for k in range(terms))
    tail = 2*t**(2*terms+1)/((2*terms+1)*(1-t*t))
    return value, value+tail


def log(x, terms):
    assert x >= 1
    exponent = 0
    while x > 2: x /= 2; exponent += 1
    return add(log_series(x, terms), scale(log_series(Q(2), terms), exponent))


def primitive(d, m, terms):
    a, l = atan(m*d, terms), log(1+(m*d)**2, terms)
    return (a, scale(l, 1/(2*m)), sub((d/m, d/m), scale(a, 1/m**2)),
            sub((d*d/(2*m), d*d/(2*m)), scale(l, 1/(2*m**3))))


def reference(poly, lower, upper, m, terms):
    if m == 0 or lower == upper: return Q(0), Q(0)
    a, b = primitive(lower, m, terms), primitive(upper, m, terms)
    result = Q(0), Q(0)
    for k, coefficient in enumerate(poly): result = add(result, scale(sub(b[k], a[k]), coefficient))
    return result


def endpoint(row):
    n, exponent = int(row[0]), row[1]
    return Q(n)*Q(2)**exponent if n else Q(0)


def run(output, headers):
    output.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    runtime = Path('/lib/x86_64-linux-gnu/libmpfr.so.6').resolve()
    source = ROOT/'tools/sheet_charge/check_fringe_interval.cpp'
    paths = [source, ROOT/'tools/sheet_charge/fringe_interval.hpp', ROOT/'tools/charge_compiler/json.hpp',
             headers/'mpfr.h', runtime, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    binary = output/'check_fringe_interval'
    with lease(1, 2, deadline):
        execute(['g++', '-std=c++20', '-O3', '-fno-fast-math', '-ffp-contract=off', '-I'+str(headers),
                 source, '-l:libmpfr.so.6', '-lgmpxx', '-lgmp', '-o', binary], output/'build.log', deadline, 2)
        cases = []
        for lower, upper, m in ((Q(0), Q(1, 4), Q(1)), (Q(1, 8), Q(1, 2), Q(1)),
                                (Q(0), Q(127), Q(3)), (Q(8), Q(9), Q(1, 64)),
                                (Q(1), Q(2), Q(1, 1048576)), (Q(0), Q(1), Q(0))):
            for poly in ((Q(1), Q(0), Q(0), Q(0)), (Q(-3, 7), Q(2, 3), Q(-5, 11), Q(7, 13))):
                cases.append(dict(polynomial=list(map(str, poly)), lower=str(lower), upper=str(upper), multiplier=str(m)))
        results = []
        for bits in (128, 256, 512, 1024):
            cfg, report = output/f'{bits}.json', output/f'{bits}.report.json'
            save(cfg, dict(precision_bits=bits, cases=cases, report=str(report)))
            execute([binary, cfg], output/f'{bits}.log', deadline, 2)
            found = json.loads(report.read_text())
            assert len(found) == len(cases)
            for index, (case, row) in enumerate(zip(cases, found)):
                observed = endpoint(row['lower_dyadic']), endpoint(row['upper_dyadic'])
                exact = reference(list(map(Q, case['polynomial'])), Q(case['lower']), Q(case['upper']),
                                  Q(case['multiplier']), bits//2+48)
                # The independently computed series enclosure is narrower and inside the MPFR enclosure.
                assert observed[0] <= exact[0] <= exact[1] <= observed[1], (bits, index)
            results.append(dict(precision_bits=bits, cases=len(cases), independent_rational_enclosures_contained=True))
        verify(pins)
        artifacts = {str(p): sha(p) for p in output.iterdir() if p.is_file()}
        save(output/'assessment.json', dict(input_sha256=pins, artifacts=artifacts, results=results,
             independent_fringe_interval_controls_pass=True, source_constants_changed=False,
             full_layout_integration_certified=False, physical_RC_qualified=False, release_qualified=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--headers', required=True, type=Path)
    args = parser.parse_args()
    run(args.output.resolve(), args.headers.resolve())
