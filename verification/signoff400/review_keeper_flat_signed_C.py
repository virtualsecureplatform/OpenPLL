"""Recover completed native flat exports after FLOATING-comment parse failure."""
import argparse,json
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from audit_hierarchical_capacitance import number
from native_spice_comments import strip_floating_annotation
from resources import identity


def run(replay,output):
    manifest=replay/'inputs.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    process=replay/'native.process.json';p=json.loads(process.read_text())
    if identity(p['pid'])==p['birth']:raise ValueError('native exporter still live')
    log=replay/'native.log';text=log.read_text()
    if text.count('exttospice finished.')!=2 or 'Error:'in text:raise ValueError('both native conversions must finish without errors')
    pins={str(p):sha(p)for p in [manifest,process,log,Path(__file__).resolve(),Path(__file__).with_name('native_spice_comments.py'),Path(__file__).with_name('audit_hierarchical_capacitance.py')]};artifacts={};results=[];positive_parts=[]
    for name in ['default_threshold','signed_threshold']:
        path=replay/(name+'.spice');pins[str(path)]=sha(path);counts=dict(capacitors=0,negative=0,zero=0,positive=0);positive=defaultdict(F);negative_sum=F();coarse_diagonal=F()
        for line in path.open():
            f=strip_floating_annotation(line).split()
            if not f or not f[0].upper().startswith('C'):continue
            if len(f)!=4:raise ValueError('unreviewed flat capacitor syntax')
            value=number(f[-1]);counts['capacitors']+=1
            if value<0:counts['negative']+=1;negative_sum+=value
            elif value==0:counts['zero']+=1
            else:counts['positive']+=1;positive[tuple(sorted(f[1:3]))]+=value
            if 'COARSE_CODE[0]'in f[1:3]and f[1]!=f[2]:coarse_diagonal+=value
        if not counts['capacitors']:raise ValueError('empty native export')
        results.append(dict(export=name,**counts,negative_sum_F=str(negative_sum),literal_COARSE_CODE_0_incident_sum_F=str(coarse_diagonal)))
        positive_parts.append(dict(positive));artifacts[str(path)]=sha(path)
    if positive_parts[0]!=positive_parts[1]:raise ValueError('positive coefficients differ between native exports')
    verify(pins);verify(m['input_sha256']);output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,both_native_exports_completed=True,positive_part_exactly_equal=True,FLOATING_annotation_stripped_without_coefficient_change=True,original_review_failed=True,extraction_rerun=False,geometry_reextracted=False,default_threshold_does_not_qualify_signed_operator=True,coefficient_equivalence_to_hierarchical_model_qualified=False,passivity_qualified=False,native_simulation_allowed=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--replay',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.replay.resolve(),a.output.resolve())
