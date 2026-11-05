"""Remove only redundant constant-plateau PWL knots, without approximation."""
import argparse,json,math
from pathlib import Path


def compact_rows(rows):
    previous=None;pending=None
    for t,v in rows:
        if not math.isfinite(t) or not math.isfinite(v) or t<0:raise ValueError('finite nonnegative time and finite voltage required')
        if previous is not None and t<=(pending if pending is not None else previous)[0]:raise ValueError('strictly increasing knot times required')
        if previous is None:
            previous=(t,v);yield previous
        elif pending is None:pending=(t,v)
        elif previous[1]==pending[1]==v:pending=(t,v)
        else:
            yield pending;previous=pending;pending=(t,v)
    if pending is not None:yield pending


def compact_file(source,target):
    if target.exists():raise FileExistsError(target)
    count=0;written=0
    def rows():
        nonlocal count
        with source.open() as stream:
            for line in stream:
                if not line.strip():continue
                fields=line.split()
                if len(fields)!=2:raise ValueError('two-column PWL required')
                count+=1;yield tuple(map(float,fields))
    try:
        with target.open('x') as stream:
            for t,v in compact_rows(rows()):stream.write(f'{t:.17g} {v:.17g}\n');written+=1
        if count<2:raise ValueError('at least two knots required')
    except BaseException:
        target.unlink(missing_ok=True);raise
    return dict(input_knots=count,output_knots=written,method='remove_only_constant_plateau_interior_knots',approximation_used=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(compact_file(a.input,a.output)))
