"""Compare raw-tile global density reviews with the unchanged stock aggregation code.

Only the original Python reporting statements are replayed; no native wrapper
exit code is changed. The filled positive and its unfilled negative share the
same geometry apart from the fill-purpose layers certified by the fill receipt.
"""
import argparse
import ast
from contextlib import redirect_stdout
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify

LAYERS=dict(FOM='fomfill',POLY='polyfill',LI1='lifill',MET1='met1fill',
            MET2='met2fill',MET3='met3fill',MET4='met4fill',MET5='met5fill')


def stock_global_report(code,raw):
    tree=ast.parse(code)
    mains=[n for n in tree.body if isinstance(n,ast.If) and
           isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='__name__']
    if len(mains)!=1:raise ValueError('unique stock command entry point required')
    body=mains[0].body
    starts=[i for i,n in enumerate(body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
            and isinstance(n.value.func,ast.Name) and n.value.func.id=='print'
            and n.value.args and isinstance(n.value.args[0],ast.Constant)
            and n.value.args[0].value=='Whole-chip (global) density results:']
    if len(starts)!=1:raise ValueError('unique stock global aggregation block required')
    first=starts[0]
    ends=[i for i,n in enumerate(body) if i>first and isinstance(n,ast.If)
          and isinstance(n.test,ast.UnaryOp) and isinstance(n.test.op,ast.Not)
          and isinstance(n.test.operand,ast.Name) and n.test.operand.id=='keepmode']
    if len(ends)!=1:raise ValueError('unique stock file-cleanup boundary required')
    nx=int(re.search(r'^XTILES: (\d+)$',raw,re.M)[1]);ny=int(re.search(r'^YTILES: (\d+)$',raw,re.M)[1])
    scope=dict(xtiles=nx,ytiles=ny,xfrac=float(re.search(r'^XFRAC: (\S+)$',raw,re.M)[1]),
               yfrac=float(re.search(r'^YFRAC: (\S+)$',raw,re.M)[1]))
    tiles={}
    for x,y,text in re.findall(r'Density results for tile x=(\d+) y=(\d+)\n(.*?)(?=Density results for tile|Ended:)',raw,re.S):
        key=(int(x),int(y));pairs=re.findall(r'^(FOM|POLY|LI1|MET[1-5]): (\S+)$',text,re.M)
        if key in tiles or len(pairs)!=8 or set(dict(pairs))!=set(LAYERS):raise ValueError('invalid native tile inventory')
        tiles[key]={k:float(v) for k,v in pairs}
    if set(tiles)!={(x,y) for x in range(nx) for y in range(ny)}:raise ValueError('incomplete native tile coverage')
    for layer,name in LAYERS.items():scope[name]=[tiles[x,y][layer] for y in range(ny) for x in range(nx)]
    selected=ast.Module(body=body[first:ends[0]],type_ignores=[]);capture=StringIO()
    with redirect_stdout(capture):
        exec(compile(selected,'<pinned-stock-global-density-report>','exec'),
             {'__builtins__':dict(print=print,sum=sum,range=range)},scope)
    return capture.getvalue()


def run(filled,unfilled,fill,output):
    fill_receipt=fill/'assessment.json';f=json.loads(fill_receipt.read_text())
    verify(f['input_sha256']);verify(f['artifacts'])
    if not f['all_original_parent_geometry_and_labels_preserved'] or not f['only_fill_purpose_layers_added']:
        raise ValueError('fill-only positive/negative geometry pair required')
    inputs={str(fill_receipt):sha(fill_receipt),str(Path(__file__).resolve()):sha(Path(__file__).resolve()),
            str(Path(__file__).with_name('common_v3.py')):sha(Path(__file__).with_name('common_v3.py'))}
    reports={};results={};methods=set()
    for label,directory,wanted_failures in (('filled',filled,0),('unfilled',unfilled,7)):
        receipt=directory/'assessment.json';a=json.loads(receipt.read_text())
        verify(a['input_sha256']);verify(a['artifacts'])
        raw=Path(next(n for n in a['input_sha256'] if n.endswith('/density.log')))
        manifest=raw.parent/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        method=Path(next(n for n in m['input_sha256'] if n.endswith('/check_density.py')))
        gds=[Path(n) for n in m['input_sha256'] if n.endswith('.gds')]
        if len(gds)!=1 or m['declared_die_nm']!=f['declared_parent_die_nm']:
            raise ValueError('same declared macro and one native measured GDS required')
        digest=sha(gds[0])
        if label=='filled':
            if not any(n.endswith('.gds') and h==digest for n,h in f['artifacts'].items()):raise ValueError('positive GDS differs from fill output')
        elif f['input_sha256'].get(str(gds[0]))!=digest:
            raise ValueError('negative GDS differs from original fill input')
        if a['stock_wrapper_passed'] or a['failed_global_checks']!=wanted_failures:
            raise ValueError('retained wrapper applicability failure or expected control result differs')
        text=stock_global_report(method.read_text(),raw.read_text());reports[label]=text
        if len(re.findall(r'^\*\*\*Error:',text,re.M))!=wanted_failures:
            raise ValueError('stock global threshold decisions differ from independent review')
        for layer,row in a['results'].items():
            name='LI' if layer=='LI1' else layer
            matches=re.findall(r'^'+name+r' Density: (\S+)$',text,re.M)
            if len(matches)!=1 or abs(Decimal(matches[0])-Decimal(row['global_density']))>Decimal('0.000501'):
                raise ValueError('stock and independently integrated global values differ')
        methods.add(sha(method));results[label]=dict(global_checks=7,failed_checks=wanted_failures,raw_tiles=a['raw_tiles'])
        inputs.update({str(p):sha(p) for p in (receipt,raw,manifest,method,gds[0])})
    if len(methods)!=1:raise ValueError('controls must use identical stock method bytes')
    verify(inputs);output.mkdir(parents=True,exist_ok=False);artifacts={}
    for label,text in reports.items():
        target=output/(label+'_stock_global_report.txt');target.write_text(text);artifacts[str(target)]=sha(target)
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts=artifacts,controls=results,
        stock_global_code_replayed_without_threshold_changes=True,
        all_eight_reported_values_match_independent_area_weighting=True,
        unfilled_native_negative_control_rejected=True,filled_native_positive_control_passed=True,
        fill_only_geometry_pair_proved=True,stock_wrapper_exit_codes_unchanged=True,
        chip_integration_window_density_qualified=False,final_candidate_density_qualified=False,release_ready=False))
    print(json.dumps(results))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('filled','unfilled','fill','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ('filled','unfilled','fill','output')))
