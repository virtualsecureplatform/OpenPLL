"""Join DCO voltage witnesses to six-MOS cell topology and actual sampled biases."""
import argparse,json,math,os,time
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from capture_selected_native_initial_snapshot import fingerprint
from check_selected_boundary_waveforms import bind
from measure_selected_mos_terminal_extents import header


def run(measurement,witnesses,locations,truth,snapshot,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{31})
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        mr=measurement/'assessment.json';wr=witnesses/'assessment.json';tr=truth/'assessment.json'
        a,w,loc,logic=[json.loads(p.read_text())for p in [mr,wr,locations,tr]]
        for receipt in [a,w,loc,logic]:verify(receipt['input_sha256']);verify(receipt.get('artifacts',{}))
        if w['input_sha256'].get(str(mr))!=sha(mr) or not w['all_independent_double_results_match']:
            raise ValueError('independently verified witnesses from this measurement required')
        if logic['cell']!='sky130_fd_sc_hd__einvp_1' or logic['functional_truth_cases_passed']!=4 or not logic['TE0_disables_output']:
            raise ValueError('checked matching PDK cell truth required')
        npaths=[Path(p)for p in loc['input_sha256']if p.endswith('/nodes.json')]
        if len(npaths)!=1:raise ValueError('unique physical node map required')
        nodes_path=npaths[0];metadata=json.loads(nodes_path.read_text());physical=metadata['physical_instances']
        phys={r['instance']:r for r in physical}
        if len(phys)!=len(physical):raise ValueError('unique flat physical instance identities required')
        cells={}
        for record in loc['records']:
            for node,item in record['terminal_locations'].items():
                for label in item['original_hierarchy_labels']:
                    if '/sky130_fd_sc_hd__einvp_1_' in label and label.endswith('/Z'):
                        if metadata['original_to_emitted'].get(label)!=node:raise ValueError('cell output mapping differs')
                        cells[node]=dict(cell=label.rsplit('/',1)[0],output_node=node)
        if not cells:raise ValueError('mapped e-inverter output witnesses required')
        models=[Path(p)for p in a['input_sha256']if p.endswith('/model.spice')]
        manifests=[Path(p)for p in a['input_sha256']if p.endswith('/native/manifest.json')]
        if len(models)!=1 or len(manifests)!=1:raise ValueError('unique native model and manifest required')
        if loc['input_sha256'].get(str(models[0]))!=sha(models[0]):raise ValueError('same physical source model required')
        calls={};leaf_models={};resistors=defaultdict(list);cap_counts=defaultdict(int);subckt=None
        for line in models[0].open():
            f=line.split()
            if not f:continue
            if f[0].lower()=='.subckt':subckt=f[1]
            if f[0].lower()=='xdevice' and len(f)>5:leaf_models[subckt]=f[5]
            if f[0].startswith('Xflat'):
                positional=[]
                for token in f[1:]:
                    if '=' in token:break
                    positional.append(token)
                calls[f[0]]=(positional[:-1],positional[-1])
            if f[0][0].upper()=='R' and len(f)>=4:
                for node in f[1:3]:
                    if node in cells:resistors[node].append(f[0])
            if f[0][0].upper()=='C' and len(f)>=4:
                for node in f[1:3]:
                    if node in cells:cap_counts[node]+=1
        for z,cell in cells.items():
            seeds=[name for name,(nn,model)in calls.items()if len(nn)==4 and nn[0]==z and name in phys and phys[name]['leaf_master']==logic['cell']]
            identities={json.dumps(phys[name]['physical_hierarchy_identity'],sort_keys=True)for name in seeds}
            if len(identities)!=1:raise ValueError('unique physical cell group required')
            identity=next(iter(identities));group=[r for r in physical if json.dumps(r['physical_hierarchy_identity'],sort_keys=True)==identity and r['leaf_master']==logic['cell']]
            if len(group)!=6:raise ValueError('reviewed six-MOS e-inverter topology required')
            local=defaultdict(set);names=[]
            for row in group:
                name=row['instance'];names.append(name);nn,leaf=calls[name];family,ports,parameters=row['local_primitive_signature']
                if len(nn)!=4 or len(ports)!=4 or leaf_models.get(leaf)!=family:raise ValueError('native and physical primitive signatures differ')
                for pin,node in zip(ports,nn):local[pin].add(node)
            if not {'A','TE','Z','a_27_47#','a_204_47#','a_276_297#'}<=set(local):raise ValueError('complete e-inverter node labeling required')
            outside=[name for name,(nn,leaf)in calls.items()if z in nn and name not in names]
            cell.update(flat_MOS_instances=sorted(names),local_to_native_nodes={k:sorted(v)for k,v in local.items()},physical_hierarchy_identity=phys[seeds[0]]['physical_hierarchy_identity'],outside_cell_primitive_connections_to_Z=outside,explicit_resistors_on_Z=resistors[z],external_capacitor_cards_on_Z=cap_counts[z])
        native=manifests[0].parent;raw=native/'profile.raw';sr=snapshot/'assessment.json';s=json.loads(sr.read_text());before=fingerprint(raw)
        if a['input_sha256'].get(str(sr))!=sha(sr) or before!=s['source_file_fingerprint']:raise ValueError('unchanged verified native RAW required')
        names,points=header(raw);required=sorted({n for c in cells.values()for values in c['local_to_native_nodes'].values()for n in values})
        binding=bind([n for n in required if n!='0'],names)
        if not binding['all_bound']:raise ValueError('all reviewed cell nodes must have saved native values')
        offsets_path=witnesses/'offsets.txt'
        if w['input_sha256'].get(str(offsets_path))!=sha(offsets_path):raise ValueError('independently verified sample offsets required')
        samples=[]
        for line in offsets_path.read_text().splitlines():
            offset,text=line.split(':',1);sample,seconds=text.split();sample=int(sample);seconds=float(seconds);values={'0':0.}
            index_to_nodes=defaultdict(list)
            for node,b in binding['bindings'].items():index_to_nodes[b['index']].append(node)
            with raw.open('rb')as stream:
                stream.seek(int(offset));row=stream.readline().split()
                if int(row[0])!=sample or float(row[1])!=seconds:raise ValueError('native witness marker changed')
                for index in range(1,len(names)):
                    line=stream.readline()
                    if not line:raise ValueError('incomplete native witness')
                    if index in index_to_nodes:
                        value=float(line)
                        if not math.isfinite(value):raise ValueError('nonfinite cell voltage')
                        for node in index_to_nodes[index]:values[node]=value
            rows=[]
            for cell in cells.values():
                rows.append(dict(cell=cell['cell'],local_voltages_V={label:[dict(node=n,voltage_V=values[n])for n in ns]for label,ns in cell['local_to_native_nodes'].items()}))
            samples.append(dict(sample=sample,time_ns=seconds*1e9,cells=rows))
        if fingerprint(raw)!=before:raise ValueError('RAW changed during cell inspection')
        for cell in cells.values():
            rows=[r for sample in samples for r in sample['cells']if r['cell']==cell['cell']]
            for pin,key in [('TE','TE_at_witnesses_range_V'),('Z','Z_at_witnesses_range_V'),('a_27_47#','enable_complement_at_witnesses_range_V')]:
                vals=[x['voltage_V']for row in rows for x in row['local_voltages_V'][pin]];cell[key]=[min(vals),max(vals)]
        files=[mr,wr,locations,tr,sr,nodes_path,models[0],manifests[0],offsets_path,Path(__file__).resolve()]
        files += [Path(__file__).with_name(n)for n in ['common_v3.py','resources.py','capture_selected_native_initial_snapshot.py','check_selected_boundary_waveforms.py','measure_selected_mos_terminal_extents.py']]
        save(output/'assessment.json',dict(input_sha256={str(p):sha(p)for p in files},cells=list(cells.values()),sampled_witnesses=samples,functional_TE0_disables_output=True,bias_scope='selected independently verified extrema times only; not a complete TE waveform or causal proof',electrical_rules_qualified=False,model_validity_ranges_qualified=False,reliability_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['measurement','witnesses','locations','truth','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.measurement.resolve(),a.witnesses.resolve(),a.locations.resolve(),a.truth.resolve(),a.snapshot.resolve(),a.output.resolve())
