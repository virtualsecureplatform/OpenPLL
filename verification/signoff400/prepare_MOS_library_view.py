"""Conservative private include view; omit only unused pure definition leaves."""
import argparse,json,os,re,shlex,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from model_preparation_fast import model_closure,line_edits,apply_line_edits


def prepare(first,out,deadline,needed):
    out.mkdir(parents=True,exist_ok=False);files=model_closure(first,deadline);texts={p:p.read_text() for p in files};pins={str(p):sha(p) for p in files};omitted={}
    def wanted(name):return name in needed or any(name.startswith(n+'__model') for n in needed)
    for p,text in texts.items():
        depth=0;definitions=[];outside=False;includes=False;model_continuation=False
        for raw in text.splitlines():
            line=raw.strip()
            if not line or line.startswith('*'):continue
            if line.startswith('+'):
                if not depth and not model_continuation:outside=True
                continue
            tokens=line.split();directive=tokens[0].lower();model_continuation=directive=='.model'
            if directive=='.subckt':
                if len(tokens)<2:raise ValueError('subcircuit name required')
                definitions.append(tokens[1].lower());depth+=1
            elif directive=='.ends':
                depth-=1
                if depth<0:raise ValueError('unbalanced model wrapper')
            elif directive=='.model':
                if len(tokens)<2:raise ValueError('model name required')
                definitions.append(tokens[1].lower())
            elif directive in ('.include','.inc','.lib'):includes=True;outside=True
            elif not depth:outside=True
        if depth:raise ValueError('unterminated wrapper')
        if definitions and not outside and not includes and not any(wanted(n) for n in definitions):omitted[p]=definitions
    if not omitted:raise ValueError('no conservative omission opportunity')
    transformed={};artifacts=[];edits=[];visiting=set()
    def visit(p):
        p=p.resolve()
        if p in omitted:return None
        if p in transformed:return transformed[p]
        if p in visiting:raise ValueError('cyclic include graph')
        visiting.add(p);original=texts[p];lines=[];changed=False
        for raw in original.splitlines(keepends=True):
            stripped=raw.strip();directive=stripped.split(None,1)[0].lower() if stripped else ''
            if directive not in ('.include','.inc','.lib'):lines.append(raw);continue
            tokens=shlex.split(stripped)
            if directive=='.lib' and len(tokens)==2:lines.append(raw);continue
            if len(tokens) not in (2,3) or (directive!='.lib' and len(tokens)!=2):raise ValueError('strict include directive required')
            child=(p.parent/tokens[1]).resolve();replacement=visit(child);newline='\n' if raw.endswith('\n') else ''
            if replacement is None:line='* OpenPLL unused pure-definition include omitted: '+stripped+newline
            else:line=directive+' "'+str(replacement)+'"'+(' '+tokens[2] if len(tokens)==3 else '')+newline
            lines.append(line);changed|=line!=raw
        visiting.remove(p)
        if not changed:transformed[p]=p;return p
        target=out/(str(len(transformed)).zfill(4)+'_'+p.name);content=''.join(lines);ledger=line_edits(original.encode(),content.encode())
        if apply_line_edits(original.encode(),ledger)!=content.encode():raise ValueError('exact include-edit reconstruction failed')
        target.write_text(content);patch=target.with_suffix(target.suffix+'.edits.json');save(patch,ledger);artifacts.extend([target,patch]);edits.append(dict(source=str(p),private=str(target),ledger=str(patch)));transformed[p]=target;return target
    root=visit(first.resolve());closure=model_closure(root,deadline)
    if any(p in omitted for p in closure):raise ValueError('omitted definition remains reachable')
    kept_text='\n'.join(texts[p] for p in files if p not in omitted)
    if any(not re.search(r'(?im)^\s*\.subckt\s+'+re.escape(n)+r'\s',kept_text) for n in needed):raise ValueError('every requested wrapper retained')
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('foundry input changed')
    report=dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},library=str(root),requested_wrappers=sorted(needed),original_dependency_files=len(files),private_view_dependency_files=len(closure),unused_pure_definition_leaf_files_omitted=len(omitted),omitted_definitions={str(p):names for p,names in omitted.items()},include_edits=edits,all_retained_model_parameter_and_global_parameter_bytes_unchanged=True,all_edits_reconstruct_exactly=True,foundry_files_modified=False,native_response_equivalence_verified=False,performance_improvement_demonstrated=False,release_qualified=False);save(out/'assessment.json',report);return root,report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--inside',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args();out=args.output.resolve()
    if args.inside:
        inventory=ROOT/'build/signoff400/startup_timing_MOS_backend_profiles_001/profiles.jsonl';needed={json.loads(line)['model'].lower() for line in inventory.read_text().splitlines()};library=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice');prepare(library,out/'view',args.deadline,needed);save(out/'status.json',dict(state='private_MOS_library_view_prepared_pending_native_controls',release_qualified=False));return
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
