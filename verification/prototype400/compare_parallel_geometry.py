"""Compare serial and parallel native geometry results on identical inputs."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re

from common import save, sha, verify


def spef_without_date(text):
    return '\n'.join(line for line in text.splitlines() if not line.startswith('*DATE '))


def feedback_records(text):
    if not text:
        return []
    parts=re.split(r'^box ',text,flags=re.M)
    if parts[0]:raise ValueError('unexpected feedback preamble')
    rows=['box '+part for part in parts[1:]]
    for row in rows:
        if not re.fullmatch(r'box -?\d+ -?\d+ -?\d+ -?\d+\nfeedback add "[^\"]*" \w+\n?',row):
            raise ValueError('unexpected native feedback record')
    return sorted(rows)


def compare(serial, parallel, output):
    serial,parallel,output=map(lambda p:Path(p).resolve(),(serial,parallel,output))
    output.mkdir(parents=True,exist_ok=False)
    receipts=[]
    for folder in (serial,parallel):
        report=json.loads((folder/'assessment.json').read_text())
        verify(report['input_sha256']);verify(report['artifacts'])
        if not report['raw_checks_completed']:raise ValueError('incomplete native checks')
        receipts.append(report)
    before,after=receipts
    excluded=str(Path(__file__).resolve().with_name('check_parent_geometry_v3.py'))
    for path,digest in before['input_sha256'].items():
        if path!=excluded and after['input_sha256'].get(path)!=digest:
            raise ValueError('native input identity mismatch: '+path)
    if before['density_native_exit']!=after['density_native_exit']:
        raise ValueError('density native exit mismatch')
    if set(after['native_job_exit'])!={'rcx_min','rcx_nom','rcx_max','forming_antenna','native_antenna','density'}:
        raise ValueError('incomplete parallel job inventory')
    for name,code in after['native_job_exit'].items():
        if name!='density' and code:raise ValueError('parallel native stage failed')
    pins={str(path):sha(path) for path in (Path(__file__).resolve(),Path(__file__).resolve().with_name('common.py'))}
    for folder in (serial,parallel):
        pins[str(folder/'assessment.json')]=sha(folder/'assessment.json')
    for corner in ('min','nom','max'):
        paths=[folder/f'parent.{corner}.spef' for folder in (serial,parallel)]
        if spef_without_date(paths[0].read_text())!=spef_without_date(paths[1].read_text()):
            raise ValueError('SPEF values or identities differ: '+corner)
        pins.update({str(path):sha(path) for path in paths})
    for name in ('components.json',):
        paths=[folder/'forming_antenna'/name for folder in (serial,parallel)]
        if json.loads(paths[0].read_text())!=json.loads(paths[1].read_text()):
            raise ValueError('forming component records differ')
        pins.update({str(path):sha(path) for path in paths})
    feedback=[]
    for folder in (serial,parallel):
        path=folder/'antenna_feedback.txt';pins[str(path)]=sha(path)
        feedback.append(feedback_records(path.read_text()))
    if feedback[0]!=feedback[1]:raise ValueError('native feedback multiset differs')
    density=[]
    for folder in (serial,parallel):
        path=folder/'density.log';pins[str(path)]=sha(path)
        density.append(path.read_text().replace(str(folder),'<OUTPUT>'))
    if density[0]!=density[1]:raise ValueError('density transcript differs')
    times=[]
    for folder in (serial,parallel):
        status=json.loads((folder/'status.json').read_text())
        if status['state']!='parent_geometry_measurements_terminal':raise ValueError('native run not terminal')
        owner=json.loads((folder/'owner.json').read_text())
        times.append((datetime.fromisoformat(status['observed_utc'])-datetime.fromisoformat(owner['started_utc'])).total_seconds())
        pins.update({str(folder/name):sha(folder/name) for name in ('status.json','owner.json')})
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={},
        three_spef_views_equal_except_date=True,all_forming_component_records_equal=True,
        native_feedback_records_equal=True,native_feedback_count=len(feedback[0]),
        density_transcripts_equal_after_output_path_normalization=True,
        same_native_inputs_and_results_verified=True,serial_wall_s=times[0],parallel_wall_s=times[1],
        whole_check_speedup=times[0]/times[1],physical_model_qualified=False,release_qualified=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('serial','parallel','output'):parser.add_argument('--'+name,required=True,type=Path)
    a=parser.parse_args();compare(a.serial,a.parallel,a.output)
