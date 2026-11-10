"""Bind the completed ground-copy observation to unchanged copy-stage source."""
import json,re,time
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease


def run():
    base=ROOT/'build/tools';engines=[base/n for n in ['magic_drive_type_1726','magic_reference_alias_1757']]
    probe=ROOT/'build/signoff400/selected_ground_copy_original_1732/assessment.json';pr=json.loads(probe.read_text())
    if pr['copy_seed_from_driver'] or not pr['driver_type_present_after_copy']:raise ValueError('completed original-seed M5 observation required')
    records=[json.loads((p/'assessment.json').read_text()) for p in engines]
    paths=[probe,Path(__file__).resolve()];work=[]
    for engine,record in zip(engines,records):
        paths.extend([engine/'assessment.json',engine/'workspace.json'])
        work.append(Path(json.loads((engine/'workspace.json').read_text())['local_source']))
        for p in [engine/'install/bin/magic',engine/'install/lib/magic/tcl/tclmagic.so']:
            if record['artifacts'][str(p)]!=sha(p):raise ValueError('native engine changed')
            paths.append(p)
    for name,digest in pr['artifacts'].items():
        if sha(name)!=digest:raise ValueError('completed copy evidence changed')
    keys={Path('resis')/n for n in ['ResMain.c','ResRex.c','ResReadExt.c']}
    for directory in ['database','tiles','calma','cif','utils','extract']:
        for p in (work[0]/directory).rglob('*'):
            if p.is_file() and (p.suffix in ['.c','.h'] or p.name.endswith('.h.in')):keys.add(p.relative_to(work[0]))
    rows=[]
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+300):
        for key in sorted(keys):
            a,b=[w/key for w in work]
            rows.append(dict(source=str(key),old_sha256=sha(a),current_sha256=sha(b),identical=sha(a)==sha(b)))
            paths.extend([a,b])
        structs=[]
        for tag,typename in [('resextnode','ResExtNode')]:
            blocks=[]
            for w in work:
                text=(w/'resis/resis.h').read_text();pattern=r'typedef struct '+tag+r'\s*\{.*?\}\s*'+typename+r';'
                matches=re.findall(pattern,text,re.S)
                if len(matches)!=1:raise ValueError('unique copy input structure required')
                blocks.append(matches[0]);paths.append(w/'resis/resis.h')
            structs.append(dict(type=typename,identical=blocks[0]==blocks[1]))
        passed=all(r['identical'] for r in rows+structs)
        pins={str(p):sha(p) for p in paths}
        out=ROOT/'build/signoff400/selected_reference_copy_stage_1763.json'
        if out.exists():raise FileExistsError(out)
        save(out,dict(input_sha256=pins,source_comparisons=rows,input_structure_comparisons=structs,
            copy_stage_source_unchanged=passed,current_binary_copy_only_run_performed=False,
            completed_original_seed_M5_observation_reused=True,full_current_binary_validation_required=True,
            RC_export_fixed=False,release_ready=False))
        print(json.dumps(dict(copy_stage_source_unchanged=passed,source_files=len(rows),differences=[r['source'] for r in rows if not r['identical']]),indent=2))
        if not passed:raise ValueError('copy-stage source changed; no inherited admission')

if __name__=='__main__':run()
