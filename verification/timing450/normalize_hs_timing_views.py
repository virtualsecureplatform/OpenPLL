#!/usr/bin/env python3
"""Correct pinned HS Verilog syntax/name defects in an isolated output copy.

Preserves timing checks and delayed signals. Does not add simulator support.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PINNED_SHA256 = 'd7e581615fd7962fc4acb362f11721f8626833e8225a2d7325f9bc31a1e62aaa'
ALIASES = {'RESETB_delayed':'RESET_B_delayed', 'SETB_delayed':'SET_B_delayed',
           'CLKN_delayed':'CLK_N_delayed', 'GATEN_delayed':'GATE_N_delayed',
           'AWAKE':'awake', **{f'COND{i}':f'cond{i}' for i in range(4)}}


def normalize(text):
    changes=[]
    def module(match):
        name=match[1];body=match[0]
        body,count=re.subn(r'^\s*wire\s+1\s*;[^\S\n]*$', '', body, flags=re.M)
        if count:changes.append({'module':name,'fix':'Remove invalid declaration of numeric literal 1','count':count})
        declared=set(re.findall(r'\b(?:wire|reg)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;',body))
        def check(row):
            line=row[0]
            for old,new in ALIASES.items():
                if re.search(r'\b'+old+r'\b',line):
                    if new not in declared:
                        raise RuntimeError(f'Expected declared timing signal {name}/{new}')
                    line,count=re.subn(r'\b'+old+r'\b',new,line)
                    changes.append({'module':name,'old':old,'new':new,'count':count})
            return line
        return re.sub(r'^\s*\$(?:setuphold|recrem|width|hold|setup|recovery|removal)\b[^\n]*$',check,body,flags=re.M)
    output=re.sub(r'^module\s+(\S+)\s*\([\s\S]*?^endmodule\s*$',module,text,flags=re.M)
    if not changes:raise RuntimeError('No expected timing-view corrections')
    return output,changes


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or sha(args.input)!=PINNED_SHA256:parser.error('Expected fresh output and exact pinned HS input')
    original=args.input.read_text();output,changes=normalize(original)
    if len(re.findall(r'\$(?:setuphold|recrem|width)\b',original))!=len(re.findall(r'\$(?:setuphold|recrem|width)\b',output)):
        raise RuntimeError('Timing checks altered')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(output)
    receipt={'release_qualified':False,'timing_check_support_established':False,'changes':changes,
             'limitations':['Requires a simulator implementing delayed timing-check signals and notifier behavior'],
             'sha256':{str(p.resolve()):sha(p) for p in (args.input,args.output,Path(__file__))}}
    args.output.with_suffix('.normalization.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'Applied {len(changes)} exact syntax/name corrections; simulator qualification remains open')

if __name__=='__main__':main()
