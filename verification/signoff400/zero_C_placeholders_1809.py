"""Reversibly encode literal zero-C records as comments for native simulation.

A zero capacitor contributes identically zero charge/current at all voltages.
Keep its exact original line in the model, without allocating empty equations.
No nonzero coefficient, resistor (including zero R), device or port is changed.
"""
from decimal import Decimal,InvalidOperation
PREFIX='* OPENPLL_LITERAL_ZERO_C '

def adapt(text):
    if PREFIX in text:raise ValueError('zero-C adapter already applied')
    output=[];count=0
    for line in text.splitlines(keepends=True):
        f=line.split()
        if f and f[0][0].lower()=='c':
            if len(f)!=4:raise ValueError('literal four-field C card required')
            try:value=Decimal(f[3])
            except InvalidOperation:raise ValueError('finite decimal C literal required')
            if not value.is_finite():raise ValueError('finite C literal required')
            if value.is_zero():line=PREFIX+line;count+=1
        output.append(line)
    result=''.join(output)
    if restore(result)!=text:raise ValueError('literal zero-C record reconstruction differs')
    return result,dict(literal_zero_C_records_retained=count,zero_C_records_electrically_omitted=count,all_other_bytes_unchanged=True,exact_source_reconstruction_verified=True,nonzero_C_modified=False,R_modified=False)

def restore(text):
    return ''.join(line[len(PREFIX):]if line.startswith(PREFIX)else line for line in text.splitlines(keepends=True))
