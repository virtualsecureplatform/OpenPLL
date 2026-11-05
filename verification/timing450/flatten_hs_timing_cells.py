#!/usr/bin/env python3
"""Inline generic HS base models so SDF paths/checks belong to physical cells.

Input must be an explicitly preprocessed nonfunctional timing-view copy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

MODULE = re.compile(r'^module\s+(\S+)\s*\((.*?)\);([\s\S]*?)^endmodule',re.M|re.S)
BASE = re.compile(r'^[ \t]*(sky130_fd_sc_hs__\w+)\s+base\s*\(([\s\S]*?)\);',re.M)
NO_TIMING = {'sky130_fd_sc_hs__'+name for name in
             ('conb','decap','diode','fill','fill_diode','tap','tapmet1',
              'tapvgnd','tapvgnd2','tapvpwrvgnd')}


def flatten(text):
    if re.search(r'`(?:ifdef|ifndef|else|endif)\b',text):
        raise RuntimeError('Expected preprocessed timing views')
    modules={}
    for match in MODULE.finditer(text):
        if match[1] in modules:raise RuntimeError('Duplicate preprocessed module')
        modules[match[1]]=(match[2],match[3])
    changes=[]
    def replace(match):
        name,ports,body=match.groups();bases=list(BASE.finditer(body))
        if not bases:return match[0]
        if len(bases)!=1:raise RuntimeError('Ambiguous base instance')
        instance=bases[0];generic=instance[1]
        if generic not in modules:raise RuntimeError('Missing generic base model')
        base_ports,base_body=modules[generic]
        if generic in NO_TIMING:
            if 'specify' in base_body:raise RuntimeError('Unexpected passive/constant timing model')
            return match[0]
        connected=re.findall(r'\.(\w+)\(\s*(\w+)\s*\)',instance[2])
        required=set(p.strip() for p in base_ports.split(','))
        if (set(p for p,_ in connected)!=required or len(connected)!=len(required)
                or any(p!=net for p,net in connected)):
            raise RuntimeError('Base instance requires an unsupported port remapping')
        if BASE.search(base_body):raise RuntimeError('Nested base models are unsupported')
        # The owning strength wrapper already declares its ports and supplies.
        declarations=set(re.findall(r'^\s*(?:input|output|inout)\s+(\w+)\s*;',base_body,re.M))
        if declarations!=required:raise RuntimeError('Unexpected generic port declarations')
        inline=re.sub(r'^\s*(?:input|output|inout)\s+\w+\s*;[^\S\n]*$', '',base_body,flags=re.M)
        if 'specify' not in inline:raise RuntimeError('Base model has no timing paths')
        new_body=body[:instance.start()]+inline+body[instance.end():]
        changes.append({'cell':name,'base':generic,'timing_checks':len(re.findall(r'\$(?:setuphold|recrem|width)\b',inline))})
        return 'module '+name+' ('+ports+');'+new_body+'endmodule'
    result=MODULE.sub(replace,text)
    if not changes:raise RuntimeError('No timing wrappers flattened')
    return result,changes


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use fresh output')
    output,changes=flatten(args.input.read_text());args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(output)
    args.output.with_suffix('.flattening.json').write_text(json.dumps({'cells':changes,'release_qualified':False,'timing_check_support_established':False,'sha256':{str(p.resolve()):sha(p) for p in (args.input,args.output,Path(__file__))}},indent=2)+'\n')
    print(f'Flattened {len(changes)} cell wrappers; timing checks and notifier behavior remain required')

if __name__=='__main__':main()
