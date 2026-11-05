"""Retain all non-target routes, including previously fixed routes."""
import re


def freeze_background(section, selected):
    frozen=[]
    def freeze(match):
        name,body=match[1],match[2]
        if name not in selected and re.search(r'\+\s+(?:ROUTED|FIXED)\b',body):
            body=re.sub(r'\+\s+ROUTED\b','+ FIXED',body)
            frozen.append(name)
        return '- '+name+' '+body+';'
    text=re.sub(r'^\s*-\s+(\S+)\s+(.*?);',freeze,section,flags=re.M|re.S)
    if len(frozen)!=len(set(frozen)):raise ValueError('duplicate background net')
    return text,frozen
