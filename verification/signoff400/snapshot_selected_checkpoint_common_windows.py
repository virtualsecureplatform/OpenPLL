"""Freeze live native voltage prefixes and compare complete common-age windows.

A copied prefix is immutable evidence for its measured interval. It does not
claim normal completion of the original job or whole-model qualification.
"""
import argparse,csv,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned,metrics
from selected_spice_device_conditions import matching,reference_deck
from compare_selected_history_code_pair import increments


def run(cases,references,output):
    os.sched_setaffinity(0,{30});output.mkdir(parents=True,exist_ok=False)
    results=[];pins={};artifacts={}
    for fine,native,reference_provenance in zip((111,112),cases,references):
        folder=output/str(fine);folder.mkdir()
        manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        if (m['controls']['coarse'],m['controls']['fine'])!=(20,fine):raise ValueError('correct independent native programming pair required')
        process=native/'native.process.json';worker=json.loads(process.read_text())
        if identity(worker['pid'])!=worker['birth']:raise ValueError('live original native worker required for live-prefix capture')
        binaries=[p for p in m['input_sha256']if p.endswith('/Xyce')]
        if len(binaries)!=1 or sha(Path(f'/proc/{worker["pid"]}/exe'))!=m['input_sha256'][binaries[0]]:raise ValueError('live native executable differs')
        source=native/'control.raw';stat=source.stat();copied=folder/'observed_prefix.raw'
        with source.open('rb')as stream:payload=stream.read(stat.st_size)
        if len(payload)!=stat.st_size or identity(worker['pid'])!=worker['birth']:raise ValueError('source process or bounded byte snapshot changed')
        copied.write_bytes(payload)
        rows,info=read_prefix(copied,m['observed_roles']);candidate,startup=aligned(rows,1,2)
        if startup['end_age_ns']<40:raise ValueError('complete 10--40 ns common-age observation required')
        provenance=json.loads(reference_provenance.read_text());verify(provenance['input_sha256']);verify(provenance['artifacts'])
        reference=reference_provenance.parent/'signals.csv';assessment=reference_provenance.parent/'assessment.json'
        for path in (reference,assessment):
            if provenance['artifacts'].get(str(path))!=sha(path):raise ValueError('reference artifacts not bound to full native')
        a=json.loads(assessment.read_text())
        if a['end_ns']!=260 or a['coarse_code']['window_codes']!=[20] or a['dco_code']['window_codes']!=[fine]:raise ValueError('same complete native programming point required')
        base_paths=[Path(p)for p in m['input_sha256']if p.endswith('/manifest.json')]
        if len(base_paths)!=1:raise ValueError('unique original physical model manifest required')
        base=json.loads(base_paths[0].read_text());verify(base['input_sha256'])
        models={p:d for p,d in base['input_sha256'].items()if p.endswith('/model.spice')}
        if len(models)!=1 or any(provenance['native_input_sha256'].get(p)!=d for p,d in models.items()):raise ValueError('physical source model differs')
        physical=reference_deck(provenance);conditions=matching(native/'control.spice',physical)
        if conditions['corner']!='tt':raise ValueError('same TT native comparison required')
        with reference.open()as stream:
            reader=csv.reader(stream);names=next(reader);full=[[float(v)for v in row]for row in reader]
        if len(full)!=a['samples']:raise ValueError('full native sample count differs')
        edges,original=aligned(full,names.index('v(pllout)'),names.index('v(xpll:__parent_r_node_617)'))
        comparison=metrics(candidate,edges,40)
        result=dict(coarse=20,fine=fine,frequency_comparisons=comparison,candidate_startup=startup,
            original_native_worker=worker,source_RAW_path=str(source),copied_source_bytes=stat.st_size,
            source_file_identity_at_snapshot=[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns],
            prefix_waveform=info,source_worker_live_after_byte_copy=True,
            original_normal_full_horizon_completion_claimed=False,common_age_windows_fully_observed=True,
            model_family_qualified=False,release_ready=False)
        result_path=folder/'assessment.json';save(result_path,result);results.append(result)
        artifacts.update({str(p):sha(p)for p in (copied,result_path)})
        for path in (manifest,process,reference_provenance,reference,assessment,base_paths[0],native/'control.spice',physical):pins[str(path)]=sha(path)
    paths=[Path(__file__).resolve()]+[Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','assess_selected_detector_prefix.py','compare_selected_dco_startup_aligned_v5.py','assess_selected_detector_phase_probe_v2.py','selected_spice_device_conditions.py','compare_selected_history_code_pair.py')]
    pins.update({str(p):sha(p)for p in paths});verify(pins);verify(artifacts)
    record=increments(*results)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,common_age_frequency_comparisons=[r['frequency_comparisons']for r in results],tuning_increment_comparisons=record,
        both_common_age_windows_fully_observed=True,original_native_jobs_modified=False,
        normal_full_horizon_completion_claimed=False,scope='immutable snapshots of live native prefixes; TT coarse20/fine111 and fine112; common oscillator ages 10--40 ns and two subwindows only',
        uniform_uncertainty_bound_qualified=False,whole_model_qualified=False,release_ready=False))
    print(json.dumps(dict(frequency_errors_ppm=[{k:v['difference_ppm']for k,v in r['frequency_comparisons'].items()}for r in results],tuning_increment_comparisons=record)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('fine111-case','fine112-case','fine111-reference','fine112-reference','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run([a.fine111_case.resolve(),a.fine112_case.resolve()],[a.fine111_reference.resolve(),a.fine112_reference.resolve()],a.output.resolve())
