"""Eliminate unobserved ideal zero-volt sources tied to SPICE ground.

This changes algebraic coordinates only. Finite-R interior nodes and nonlinear
devices are not approximated. Bare node identifiers and scalar V(node) probes
are handled; current probes on a removed source are rejected.
"""
import re


def canonicalize(text):
    aliases={};removed=[]
    lines=text.splitlines()
    for line in lines[1:]:
        words=line.split()
        if len(words)!=4 or not words[0].upper().startswith('V') or words[2]!='0':continue
        try:value=float(words[3])
        except ValueError:continue
        if value==0:
            assert words[1]!='0'
            aliases[words[1].upper()]='0'
            removed.append(dict(source=words[0],node=words[1]))
    for row in removed:
        if re.search(r'\bI\(\s*'+re.escape(row['source'])+r'\s*\)',text,re.I):
            raise ValueError('Cannot remove an observed ideal-source current')
    removed_names={r['source'].upper() for r in removed}
    output=[lines[0]]
    for line in lines[1:]:
        words=line.split()
        if words and words[0].upper() in removed_names:continue
        converted=[]
        for token in words:
            if token.upper() in aliases:token='0'
            elif token.upper().startswith('V(') and token.endswith(')'):
                name=token[2:-1].strip().upper()
                if name in aliases:token='V(0)'
            converted.append(token)
        output.append(' '.join(converted))
    return '\n'.join(output)+'\n',aliases,removed
