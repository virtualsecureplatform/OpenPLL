"""Measure saved-sample external MOS terminal voltages in a completed native run.

No reliability limits or inter-sample bounds are inferred. This measurement
includes the whole native hierarchy, not just linked digital-cell STA pins.
"""
import argparse,json,math,os,shutil,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from selected_matching_corner_sender import validate
from selected_spice_device_conditions import read
from capture_selected_native_initial_snapshot import fingerprint
from prepare_prototype_analog_reference import subcircuits
from selected_native_mos_terminals import mos_cards,plan


def header(raw):
    names=[];columns=points=None
    with raw.open() as f:
        for line in f:
            if line.startswith('No. Variables:'):columns=int(line.split(':',1)[1])
            if line.startswith('No. Points:'):points=int(line.split(':',1)[1])
            if line.strip()=='Variables:':break
        for line in f:
            if line.strip()=='Values:':break
            index,name,kind=line.split()
            if int(index)!=len(names):raise ValueError('invalid native variable order')
            names.append(name)
    if len(names)!=columns or not points or points<2 or names[0].lower()!='time':
        raise ValueError('complete native header required')
    return names,points


def run(native,snapshot,waveforms,reference,bulk_review,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{31})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
        with lease(1,4,deadline):
            save(output/'status.json',dict(state='binding_whole_native_MOS_terminals',release_ready=False))
            op,pins=validate(native,snapshot,waveforms,read(native/'profile.spice')['corner'])
            manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
            models=[Path(p) for p in m['input_sha256'] if p.endswith('/model.spice')]
            if len(models)!=1:raise ValueError('unique native physical model required')
            provenance=reference/'provenance.json';p=json.loads(provenance.read_text())
            verify(p['input_sha256']);verify(p['native_input_sha256']);verify(p['artifacts'])
            sr=json.loads((snapshot/'assessment.json').read_text());raw=native/'profile.raw';before=fingerprint(raw)
            if p['input_sha256'].get(str(manifest))!=sha(manifest) or p['raw_sha256']!=sr['input_sha256'].get(str(raw)):
                raise ValueError('same completed full-native reference required')
            review=json.loads(bulk_review.read_text());verify(review['input_sha256'])
            if not review['extracted_MOS_bulk_terminals_connected_to_correct_separate_rails']:
                raise ValueError('reviewed external MOS inventory required')
            top_lines=[l for l in (native/'profile.spice').read_text().splitlines() if l.lower().startswith('xpll ')]
            if len(top_lines)!=1:raise ValueError('unique native top instance required')
            top=top_lines[0].split()[-1];cards=mos_cards(subcircuits(models[0].read_text()),top)
            names,declared_points=header(raw);binding=plan(cards,top,names)
            if binding['expanded_MOS']!=review['expanded_MOS_instances']:raise ValueError('complete reviewed MOS count required')
            plan_path=output/'terminal_plan.json';save(plan_path,binding)
            mapping=output/'indices.txt'
            with mapping.open('x') as f:
                f.write(f"{len(binding['models'])} {len(names)} {binding['expanded_MOS']} {binding['unique_MOS_cards']}\n")
                for r in binding['records']:f.write(' '.join(map(str,[r['model_index'],*r['indices'],r['multiplicity']]))+'\n')
            source=ROOT/'tools/xyce_waveform/measure_mos_extents.cpp';compiler=Path(shutil.which('g++')).resolve();binary=output/'scan'
            paths=[manifest,models[0],provenance,bulk_review,source,compiler,Path(__file__).resolve()]
            paths += [Path(__file__).with_name(n) for n in ['common_v3.py','resources.py','selected_native_mos_terminals.py','prepare_prototype_analog_reference.py','audit_hierarchical_capacitance.py','common.py','check_selected_boundary_waveforms.py','selected_matching_corner_sender.py','selected_spice_device_conditions.py','capture_selected_native_initial_snapshot.py']]
            pins.update({str(p):sha(p) for p in paths});verify(pins)
            save(output/'inputs.json',dict(input_sha256=pins,source_RAW_sha256=p['raw_sha256'],source_RAW_fingerprint=before,RAW_checksum_recomputed_this_run=False,declared_samples=declared_points,native_simulations_launched=0,CPU=31,memory_GiB=4,release_ready=False))
            with (output/'compile.log').open('x') as log:
                subprocess.run([str(compiler),'-O2','-std=c++17',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            save(output/'status.json',dict(state='measuring_complete_native_MOS_voltage_extents',release_ready=False))
            table=output/'extents.tsv'
            with table.open('x') as stream,(output/'scan.log').open('x') as log:
                subprocess.run([str(binary),str(raw),str(mapping)],check=True,stdout=stream,stderr=log,timeout=1800)
            if fingerprint(raw)!=before:raise ValueError('native RAW changed during scan')
            rows=table.read_text().splitlines();summary=rows[-1].split('\t')
            if len(summary)!=6 or summary[0]!='COMPLETE' or list(map(int,summary[1:5]))!=[declared_points,len(names),binding['expanded_MOS'],binding['unique_MOS_cards']] or abs(float(summary[5])-260e-9)>1e-18:
                raise ValueError('complete finite native scan required')
            results={name:{} for name in binding['models']}
            for line in rows[:-1]:
                f=line.split('\t')
                if len(f)!=11 or f[0]!='EXT' or f[2] not in ['DS','GS','GD','GB','BS','BD']:raise ValueError('invalid terminal extent row')
                model=int(f[1]);lo,hi=map(float,f[3:5])
                if not 0<=model<len(binding['models']) or not math.isfinite(lo) or not math.isfinite(hi) or lo>hi:raise ValueError('finite ordered terminal extents required')
                witnesses={}
                for label,start in [('minimum',5),('maximum',8)]:
                    sample,seconds,card=int(f[start]),float(f[start+1]),int(f[start+2])
                    if not 0<=sample<declared_points or not math.isfinite(seconds) or not 0<=seconds<=260e-9 or not 0<=card<len(binding['records']) or binding['records'][card]['model_index']!=model:
                        raise ValueError('invalid native extent witness')
                    witnesses[label]=dict(sample=sample,time_ns=seconds*1e9,card=card,native_terminal_nodes=binding['records'][card]['native_nodes'])
                name=binding['models'][model]
                if f[2] in results[name]:raise ValueError('duplicate terminal extent')
                results[name][f[2]]=dict(minimum_V=lo,maximum_V=hi,witnesses=witnesses)
            if any(set(r)!=set(['DS','GS','GD','GB','BS','BD']) for r in results.values()):raise ValueError('all model/terminal relations required')
            verify(pins)
            artifacts={str(x):sha(x)for x in [plan_path,mapping,table,binary,output/'compile.log',output/'scan.log']}
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,operating_point=op,samples=declared_points,end_ns=260,expanded_MOS=binding['expanded_MOS'],unique_MOS_cards=binding['unique_MOS_cards'],unique_terminal_nodes=binding['unique_terminal_nodes'],all_external_MOS_terminals_bound=True,all_saved_native_values_finite=True,voltage_extents=results,
                RAW_identity_scope='prior verified checksum plus unchanged source file fingerprint',RAW_checksum_recomputed_this_run=False,
                measurement_scope='external MOS wrapper terminal differences at saved samples only; no source/drain reorientation',
                intrinsic_BSIM_terminal_extents_measured=False,inter_sample_peak_bounds_qualified=False,voltage_stress_rules_applied=False,model_validity_ranges_qualified=False,reliability_qualified=False,
                native_simulations_launched=0,parent_analog_hierarchy_included=True,electrical_rules_qualified=False,physical_integrity_qualified=False,release_ready=False))
            save(output/'status.json',dict(state='native_MOS_terminal_extents_measured',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),original_native_jobs_unchanged=True,release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['native','snapshot','waveforms','reference','bulk-review','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.native.resolve(),a.snapshot.resolve(),a.waveforms.resolve(),a.reference.resolve(),a.bulk_review.resolve(),a.output.resolve())
