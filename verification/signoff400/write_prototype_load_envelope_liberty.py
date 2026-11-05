"""Change only input loads for a supplied-library timing sensitivity screen."""
import argparse
import json
import math
from pathlib import Path
import re
from common_v3 import save,sha,verify

PIN=re.compile(r'(pin\s*\(([^)]+)\)\s*\{\s*direction\s*:\s*input\s*;\s*capacitance\s*:\s*)([0-9.eE+-]+)(\s*;)')

def rewrite(text,bounds,edge):
    starts=list(re.finditer(r'\n cell \(([^)]+)\)',text));changes=[];parts=[text[:starts[0].start()]]
    for index,match in enumerate(starts):
        master=match[1];block=text[match.start():starts[index+1].start() if index+1<len(starts) else len(text)]
        def replace(pin):
            key=(master,pin[2]);old=float(pin[3])
            if key not in bounds:
                if '__diode_' in master:return pin[0]
                raise ValueError('input pin missing supplied envelope')
            row=bounds[key]
            if not math.isclose(old,row['native_assumed_TT_capacitance_pf'],rel_tol=1e-9,abs_tol=1e-15):raise ValueError('original native capacitance differs from inventory')
            new=row['supplied_minimum_pf' if edge=='early' else 'supplied_maximum_pf']
            if not 0<new:raise ValueError('positive screening capacitance required')
            changes.append(dict(master=master,pin=pin[2],original_pf=old,screened_pf=new))
            return pin[1]+f'{new:.12g}'+pin[4]
        parts.append(PIN.sub(replace,block))
    result=''.join(parts)
    if PIN.sub(lambda m:m[1]+'<INPUT_CAP>'+m[4],text)!=PIN.sub(lambda m:m[1]+'<INPUT_CAP>'+m[4],result):
        raise ValueError('screen changed a function, delay, constraint or other non-input-load content')
    result=result.replace('Input pin capacitances are supplied TT25 data, including the conditional diode screen.',
                          'Input loads use supplied-library sensitivity bounds; diode loads remain conditional TT data.')
    return result,changes

def run(source,envelope,output):
    receipt=source/'assessment.json';er=envelope/'assessment.json';a,e=[json.loads(p.read_text()) for p in (receipt,er)]
    for record in (a,e):verify(record['input_sha256']);verify(record['artifacts'])
    detail=envelope/'pin_capacitances.json';rows=json.loads(detail.read_text());bounds={(r['master'],r['pin']):r for r in rows['pins']}
    if len(bounds)!=e['supplied_input_pins_reviewed']:raise ValueError('unique complete load envelope required')
    output.mkdir(parents=True,exist_ok=False);inputs=dict(a['input_sha256']);inputs.update({str(p):sha(p) for p in (receipt,er,detail,Path(__file__).resolve())});artifacts={};changes=[]
    for corner in ('tt','ff','ss','sf','fs'):
        for edge in ('early','late'):
            path=source/f'{corner}_{edge}.lib';target=output/path.name
            if a['artifacts'].get(str(path))!=sha(path):raise ValueError('source view changed')
            text,rows=rewrite(path.read_text(),bounds,edge)
            if len(rows)!=len(bounds):raise ValueError('every supplied input pin must receive its screening load')
            target.write_text(text);inputs[str(path)]=sha(path);artifacts[str(target)]=sha(target)
            changes.append(dict(corner=corner,view=edge,pins=rows))
    proof=output/'changes.json';save(proof,changes);artifacts[str(proof)]=sha(proof);verify(inputs)
    result=dict(a);result.update(input_sha256=inputs,artifacts=artifacts,
         supplied_TT25_pin_capacitances_used=False,supplied_minimum_loads_in_early_views=True,
         supplied_maximum_loads_in_late_views=True,all_non_input_load_library_content_preserved=True,
         conditional_TT_diode_capacitance_retained=True,screening_envelope_only=True,
         native_PVT_pin_capacitance_and_routed_path_correlation_complete=False,physical_timing_qualified=False,release_ready=False)
    save(output/'assessment.json',result)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','envelope','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.source.resolve(),args.envelope.resolve(),args.output.resolve())
