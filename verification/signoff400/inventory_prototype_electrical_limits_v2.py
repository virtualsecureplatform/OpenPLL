"""Bind every reported routed slew failure to its actual source net and driver."""
import argparse
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify

def electrical_rows(text):
    rows=[]
    for heading,kind,unit in (('max slew','max_slew','ns'),('max capacitance','max_capacitance','pF')):
        blocks=re.findall(r'^'+heading+r'\n\nPin[^\n]*\n-+\n((?:[^\n]+\n)*)',text,re.M)
        if len(blocks)>1:raise ValueError('ambiguous electrical section')
        for line in blocks[0].splitlines() if blocks else []:
            match=re.fullmatch(r'([^\s]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+) \(VIOLATED\)',line)
            if match is None:raise ValueError('unparsed electrical violation row: '+line)
            rows.append((kind,unit,*match.groups()))
    return rows

def run(timing, inventory, output):
    receipt=inventory/'assessment.json'; inv=json.loads(receipt.read_text());verify(inv['artifacts'])
    routed=inventory/'routed.json'; module=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore']
    cells={n.lstrip('\\'):c for n,c in module['cells'].items()}
    drivers={}
    for n,c in cells.items():
        for pin,bits in c['connections'].items():
            if c['port_directions'].get(pin)=='output':
                for bit in bits:drivers.setdefault(bit,[]).append(dict(cell=n,pin=pin,master=c['type']))
    inputs={str(receipt):sha(receipt),str(routed):sha(routed),str(Path(__file__).resolve()):sha(Path(__file__).resolve())}; findings=[]
    for directory in timing:
        p=directory/'assessment.json'; a=json.loads(p.read_text());verify(a['artifacts'])
        if a['input_sha256'].get(str(receipt)) is not None:raise ValueError('unexpected baseline lineage')
        # Timing and inventory must pin the same routed-equivalence receipt.
        eq={n:h for n,h in inv['input_sha256'].items() if n.endswith('/assessment.json') and 'equivalence' in n}
        if len(eq)!=1 or any(a['input_sha256'].get(n)!=h for n,h in eq.items()):raise ValueError('different route lineage')
        log=directory/'fixed_divide16/screen.log'; text=log.read_text()
        if a['artifacts'].get(str(log))!=sha(log):raise ValueError('unbound timing log')
        for kind,unit,pin,limit,slew,slack in electrical_rows(text):
            name,port=pin.rsplit('/',1)
            if name not in cells or port not in cells[name]['connections']:raise ValueError('unbound physical pin '+pin)
            bits=cells[name]['connections'][port]
            if len(bits)!=1:raise ValueError('scalar electrical pin required')
            findings.append(dict(measurement_kind=kind,unit=unit,corner=a['native_model_corner'],pin=pin,net_bit=bits[0],limit=float(limit),measured=float(slew),slack=float(slack),drivers=drivers.get(bits[0],[])))
        inputs.update({str(p):sha(p),str(log):sha(log)})
    verify(inputs);output.mkdir(parents=True,exist_ok=False);detail=output/'violations.json';save(detail,findings)
    counts={c:sum(f['corner']==c and f['measurement_kind']=='max_slew' for f in findings) for c in ('tt','ff','ss','sf','fs')}
    caps={c:sum(f['corner']==c and f['measurement_kind']=='max_capacitance' for f in findings) for c in ('tt','ff','ss','sf','fs')}
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(detail):sha(detail)},reported_slew_violations_by_corner=counts,reported_capacitance_violations_by_corner=caps,all_five_corners_reviewed=len(timing)==5,electrical_limits_passed=len(timing)==5 and not findings,digital_timing_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--timing',type=Path,action='append',required=True)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run([v.resolve() for v in a.timing],a.inventory.resolve(),a.output.resolve())
