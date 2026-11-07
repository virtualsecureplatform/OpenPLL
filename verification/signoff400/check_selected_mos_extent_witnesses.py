"""Recover extrema samples independently by RAW byte offset and Python arithmetic."""
import argparse,json,os,shutil,subprocess,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from capture_selected_native_initial_snapshot import fingerprint


TERMINALS={'DS':(0,2),'GS':(1,2),'GD':(1,0),'GB':(1,3),'BS':(3,2),'BD':(3,0)}


def run(measurement,snapshot,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{31})
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        receipt=measurement/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        sr=snapshot/'assessment.json';s=json.loads(sr.read_text())
        if a['input_sha256'].get(str(sr))!=sha(sr):raise ValueError('same verified snapshot required')
        manifests=[Path(p)for p in a['input_sha256']if p.endswith('/native/manifest.json')]
        if len(manifests)!=1:raise ValueError('unique source native manifest required')
        raw=manifests[0].parent/'profile.raw';before=fingerprint(raw)
        if before!=s['source_file_fingerprint']:raise ValueError('RAW changed after verified snapshot')
        plan=measurement/'terminal_plan.json';p=json.loads(plan.read_text());table=measurement/'extents.tsv'
        primary={}
        for line in table.read_text().splitlines():
            f=line.split('\t')
            if f[0]=='EXT':primary[(int(f[1]),f[2])]=f
        selected=set()
        for model,relations in a['voltage_extents'].items():
            _,relation,side=max((abs(v[side+'_V']),r,side)for r,v in relations.items()for side in ['minimum','maximum'])
            selected.add((model,relation,side))
        selected.add(('sky130_fd_pr__nfet_01v8','DS','maximum'))
        selected.add(('sky130_fd_pr__pfet_01v8_hvt','DS','minimum'))
        witnesses=[]
        for model,relation,side in sorted(selected):
            f=primary[p['models'].index(model),relation];start=5 if side=='minimum'else 8
            witnesses.append(dict(model=model,relation=relation,side=side,sample=int(f[start]),seconds=float(f[start+1]),card=int(f[start+2]),expected_V=float(f[3 if side=='minimum'else 4])))
        samples=sorted({r['sample']for r in witnesses});rg=Path(shutil.which('rg')).resolve()
        command=[str(rg),'--no-filename','--byte-offset','--max-count',str(len(samples))]
        for sample in samples:command+=['-e',r'^[ \t]*'+str(sample)+r'[ \t]+[-+0-9.eE]+[ \t]*$']
        command.append(str(raw));result=subprocess.run(command,capture_output=True,text=True,check=True,timeout=300)
        offsets={}
        for line in result.stdout.splitlines():
            offset,text=line.split(':',1);fields=text.split()
            if len(fields)!=2:raise ValueError('unique sample marker required')
            sample=int(fields[0])
            if sample in offsets:raise ValueError('duplicate native sample marker')
            offsets[sample]=int(offset)
        if set(offsets)!=set(samples):raise ValueError('all witness markers required')
        records=[];columns=int(table.read_text().splitlines()[-1].split('\t')[2])
        for sample in samples:
            targets=[r for r in witnesses if r['sample']==sample]
            required={i for r in targets for i in p['records'][r['card']]['indices']if i>=0};values={-1:0.}
            with raw.open('rb') as stream:
                stream.seek(offsets[sample]);row=stream.readline().split()
                if int(row[0])!=sample:raise ValueError('sample offset mismatch')
                seconds=float(row[1])
                for col in range(1,columns):
                    line=stream.readline()
                    if not line:raise ValueError('incomplete witness sample')
                    if col in required:values[col]=float(line)
            for r in targets:
                card=p['records'][r['card']];terminal=[values[i]for i in card['indices']];first,second=TERMINALS[r['relation']];actual=terminal[first]-terminal[second]
                if seconds!=r['seconds'] or actual!=r['expected_V']:raise ValueError('independent witness differs from scanner')
                records.append(dict(**r,actual_V=actual,external_terminal_voltages_V=dict(zip(['D','G','S','B'],terminal)),native_terminal_nodes=card['native_nodes'],exact_double_result_matches=True))
        if fingerprint(raw)!=before:raise ValueError('RAW changed during witness validation')
        offsets_path=output/'offsets.txt';offsets_path.write_text(result.stdout)
        paths=[receipt,sr,plan,table,rg,offsets_path,Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('capture_selected_native_initial_snapshot.py')]
        save(output/'assessment.json',dict(input_sha256={str(x):sha(x)for x in paths},witnesses_verified=len(records),distinct_native_samples=len(samples),records=records,all_independent_double_results_match=True,parser='ripgrep sample byte offsets plus Python direct sample reads',RAW_checksum_recomputed_this_run=False,reliability_rules_applied=False,electrical_rules_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['measurement','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.measurement.resolve(),a.snapshot.resolve(),a.output.resolve())
