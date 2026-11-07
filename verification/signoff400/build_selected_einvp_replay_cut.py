"""Extract an unreduced two-cell electrical cut; boundary replay remains conditional."""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from measure_selected_mos_terminal_extents import header
from check_selected_boundary_waveforms import bind
from capture_selected_native_initial_snapshot import fingerprint


def extract(lines,cells):
    internal=set();selected=set()
    for cell in cells:
        if len(cell['flat_MOS_instances'])!=6:raise ValueError('six MOS per cell required')
        selected.update(cell['flat_MOS_instances'])
        for pin in ['Z','a_27_47#','a_204_47#','a_276_297#']:
            nodes=cell['local_to_native_nodes'][pin]
            if len(nodes)!=1:raise ValueError('unique internal node required')
            internal.update(nodes)
    if len(internal)!=4*len(cells) or len(selected)!=6*len(cells):raise ValueError('disjoint cells required')
    blocks={};top=[];current=None
    for line in lines:
        f=line.split()
        if not f or f[0].startswith('*'):continue
        if f[0].lower()=='.subckt':
            if current is not None:raise ValueError('nested subcircuit')
            current=f[1];blocks[current]=[line];continue
        if f[0].lower()=='.ends':
            if current is None:raise ValueError('unmatched subcircuit end')
            blocks[current].append(line);current=None;continue
        if current is not None:blocks[current].append(line)
    if current is not None:raise ValueError('unterminated subcircuit')
    roots=[n for n in blocks if not n.startswith('__openpll')]
    if len(roots)!=1:raise ValueError('unique native top required')
    boundaries=set();kept=[];leaves=set();found=set();counts={'MOS':0,'R':0,'C':0}
    for line in blocks[roots[0]][1:-1]:
        f=line.split();kind=f[0][0].upper()
        if kind=='X':
            pos=[]
            for token in f[1:]:
                if '=' in token:break
                pos.append(token)
            nodes=pos[:-1];leaf=pos[-1]
            if f[0] not in selected:
                if internal.intersection(nodes):raise ValueError('outside primitive touches solved internal node')
                continue
            if f[0] in found or len(nodes)!=4:raise ValueError('unique four-terminal MOS required')
            found.add(f[0]);leaves.add(leaf);counts['MOS']+=1
        elif kind in ['R','C']:
            nodes=f[1:3]
            if not internal.intersection(nodes):continue
            if len(f)!=4:raise ValueError('literal two-terminal passive required')
            value=float(f[3])
            if not math.isfinite(value) or value<=0:raise ValueError('positive finite passive required')
            counts[kind]+=1
        else:
            raise ValueError('unsupported top-level card; cut completeness cannot be established')
        kept.append(line);boundaries.update(set(nodes)-internal-{'0'})
    if found!=selected:raise ValueError('missing selected MOS')
    definitions=[]
    for leaf in sorted(leaves):
        block=blocks.get(leaf,[])
        if len(block)!=3 or block[1].split()[0].lower()!='xdevice':raise ValueError('literal PDK MOS wrapper required')
        definitions.extend(block)
    ports=sorted(boundaries)
    text='* Conditional cut: original MOS geometry and incident R/C cards.\n'
    text+=''.join(definitions)+'.subckt selected_einvp_cut '+' '.join(ports)+'\n'+''.join(kept)+'.ends selected_einvp_cut\n'
    return text,dict(internal_nodes=sorted(internal),boundary_nodes=ports,counts=counts,selected_instances=sorted(selected))


def run(inspection,snapshot,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{31})
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        a=json.loads(inspection.read_text());verify(a['input_sha256'])
        models=[Path(p)for p in a['input_sha256']if p.endswith('/model.spice')]
        if len(models)!=1:raise ValueError('unique native model required')
        s=json.loads(snapshot.read_text());raw=Path(s['source_file_fingerprint']['path']) if 'path' in s['source_file_fingerprint'] else None
        # Native manifest pinned by the inspection identifies the immutable RAW.
        manifests=[Path(p)for p in a['input_sha256']if p.endswith('/native/manifest.json')]
        if len(manifests)!=1:raise ValueError('unique native manifest required')
        raw=manifests[0].parent/'profile.raw'
        if a['input_sha256'].get(str(snapshot))!=sha(snapshot) or fingerprint(raw)!=s['source_file_fingerprint']:
            raise ValueError('unchanged verified snapshot required')
        text,plan=extract(models[0].open(),a['cells'])
        names,points=header(raw);binding=bind(plan['internal_nodes']+plan['boundary_nodes'],names)
        if not binding['all_bound']:raise ValueError('complete saved boundary and internal waveform coverage required')
        files=[inspection,snapshot,models[0],manifests[0],Path(__file__).resolve()]
        files += [Path(__file__).with_name(n)for n in ['common_v3.py','resources.py','measure_selected_mos_terminal_extents.py','check_selected_boundary_waveforms.py','capture_selected_native_initial_snapshot.py']]
        pins={str(p):sha(p)for p in files};verify(pins)
        output.mkdir(parents=True);cut=output/'cut.spice';cut.write_text(text)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(cut):sha(cut)},**plan,waveform_bindings=binding['bindings'],raw=str(raw),source_file_fingerprint=s['source_file_fingerprint'],declared_samples=points,all_incident_passives_retained=True,boundaries_replayed=False,internal_waveforms_reproduced=False,causality_proven=False,electrical_rules_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['inspection','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.inspection.resolve(),a.snapshot.resolve(),a.output.resolve())
