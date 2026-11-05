"""Pin native EXT-to-SI conversion and exercise the actual native formatter."""
import argparse
import json
from pathlib import Path
import subprocess
from common import save,sha


def function(source,name):
    start=source.index('void\n'+name+'(');brace=source.index('{',start);depth=1;end=brace+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    source=Path('/tmp/openpll-magic-origin-source-zi_pqp3t/source/ext2spice/ext2spice.c')
    reader=source.parent.parent/'extflat/EFread.c'
    parent=Path('build/signoff400/startup_timing_native_printed_cap_scale_003/assessment.json').resolve()
    paths=[source,reader,parent,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    text=source.read_text();r=reader.read_text();p=json.loads(parent.read_text())
    if p['native_internal_units_per_printed_EXT_unit']!='1':raise ValueError('EXT scale must be one')
    if 'cap = cscale*atoCap(argv[3]);' not in r:raise ValueError('EXT reader scaling')
    for marker in ('spccapVisit(','spcnodeVisit('):
        # Locate definition rather than a forward declaration or invocation.
        body=text.split('\n'+marker,1)[1]
        if 'cap = cap / 1000;' not in body and 'cap = cap  / 1000;' not in body:raise ValueError('native capacitance conversion')
        if 'esSIvalue(esSpiceF, 1.0E-15 * cap);' not in body:raise ValueError('native SI conversion')
    harness=output/'native_formatter.c'
    harness.write_text('#include <stdio.h>\n#include <string.h>\n#include <math.h>\n'+
        '\n'.join(function(text,n) for n in ('nDecimals','morphNumericString','esSIvalue'))+
        '\nint main(void){double a[]={0,0.000937054,0.0358377,0.999,1,2,89.1971,1000};for(int i=0;i<8;i++){printf("%.17g ",a[i]);esSIvalue(stdout,1e-18*a[i]);puts("");}return 0;}\n')
    binary=output/'native_formatter'
    subprocess.run(['cc','-O2',str(harness),'-lm','-o',str(binary)],check=True)
    result=subprocess.run([str(binary)],check=True,capture_output=True,text=True).stdout
    (output/'native_formatter.log').write_text(result)
    cases=[]
    factors={'f':1e-15,'p':1e-12,'n':1e-9,'u':1e-6,'m':1e-3,'k':1e3,'G':1e9}
    for line in result.splitlines():
        raw,token=line.split();expected=float(raw)*1e-18
        actual=float(token[:-1])*factors[token[-1]] if token[-1] in factors else float(token)
        cases.append(dict(raw_EXT=float(raw),expected_SI_F=expected,SPICE_token=token,serialized_SI_F=actual))
    if not all(c['serialized_SI_F']==0 for c in cases[:4]):raise ValueError('sub-attofarad behavior changed')
    if any(c['serialized_SI_F']<=0 for c in cases[4:]):raise ValueError('nonzero SI conversion controls')
    if any(abs(c['serialized_SI_F']-c['expected_SI_F'])>1e-20 for c in cases[4:]):raise ValueError('engineering suffix scale')
    if any(sha(f)!=pins[str(f)] for f in paths):raise ValueError('source changed')
    save(output/'cases.json',cases)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(f):sha(f) for f in (harness,binary,output/'native_formatter.log',output/'cases.json')},
         native_EXT_trace_unit_SI_farads='1e-18',actual_native_formatter_compiled_and_exercised=True,
         positive_sub_attofarad_capacitances_serialize_as_zero=True,
         printed_EXT_equivalence_does_not_prove_SPICE_equivalence=True,
         full_SPICE_matrix_equivalence_verified=False,physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
