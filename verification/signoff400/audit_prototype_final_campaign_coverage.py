"""Replay final campaign coverage from native point receipts, superseding copied summary labels."""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify

CORNERS=('tt','ff','ss','sf','fs')
MASTERS=('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_2')
LOADS=dict(zip(MASTERS,(250,400,600,125,400)))


def expected(kind):
    if kind=='pulse':return {(c,m,k) for c in CORNERS for m in MASTERS for k in (20,400)}
    if kind=='expanded':return {(c,m,d,k) for c in CORNERS for m in MASTERS for d in (200,2000) for k in (200,400)}
    if kind=='fast':return {(c,m,d,k) for c in CORNERS for m in MASTERS for d in (20,200,2000) for k in (20,200,400) if d==20 or k==20}
    raise ValueError('unsupported final campaign')


def corrected_summary(kind, records):
    keys=set();cases=0
    for r in records:
        key=(r['corner'],r['master'],r['clock_ramp_ps']) if kind=='pulse' else (r['corner'],r['master'],r['data_ramp_ps'],r['clock_ramp_ps'])
        if key in keys:raise ValueError('duplicate native operating point')
        keys.add(key)
        if r['load_fF']!=LOADS[r['master']]:raise ValueError('expanded native load mismatch')
        if r['native_cases']!=(8 if kind=='pulse' else 30):raise ValueError('native point case count mismatch')
        cases+=r['native_cases']
    if keys!=expected(kind):raise ValueError('native corner/master/slew coverage incomplete or extra')
    return dict(corners=list(CORNERS),masters=list(MASTERS),characterization_load_fF_by_master=LOADS,
                complete_native_operating_points=len(records),native_cases=cases)


def run(campaign, kind, output):
    receipt=campaign/'assessment.json';record=json.loads(receipt.read_text())
    verify(record['input_sha256']);verify(record['artifacts'])
    points=campaign/'points.json';rows=json.loads(points.read_text());records=[]
    pins={str(p):sha(p) for p in (receipt,points,Path(__file__).resolve())}
    for row in rows:
        directory=Path(row['directory']);native=directory/'assessment.json'
        if sha(native)!=row['assessment_sha256']:raise ValueError('native point lineage changed')
        r=json.loads(native.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        master=r['master'].removeprefix('sky130_fd_sc_hs__')
        if r['corner']!=row['corner'] or master!=row['master']:raise ValueError('native master/corner binding differs')
        result=dict(corner=r['corner'],master=master,load_fF=r['load_fF'],
                    clock_ramp_ps=r['clock_full_ramp_ps'],native_cases=r['cases'],directory=str(directory))
        if kind=='pulse':
            detail=directory/'observations.json';observations=json.loads(detail.read_text())
            if len(observations)!=8 or {(x['kind'],x['nominal_width_ps']) for x in observations}!={(k,w) for k in ('high','low') for w in (400,600,1000,1600)}:
                raise ValueError('native pulse widths incomplete')
            result['reported_capture_failures']=sum(not x['full_output_trace_capture_verified'] for x in observations)
            result['pulse_waveform_independent_review_complete']=False
        else:
            result['data_ramp_ps']=r['input_full_ramp_ps']
            review=Path(row['review_directory'])/'assessment.json'
            if sha(review)!=row['review_sha256']:raise ValueError('capture independent review changed')
            a=json.loads(review.read_text());verify(a['input_sha256']);verify(a['artifacts'])
            if a['input_sha256'].get(str(native))!=sha(native):raise ValueError('review belongs to another native point')
            detail=review.parent/'observations.json';observations=json.loads(detail.read_text())['records']
            if len(observations)!=30:raise ValueError('capture review incomplete')
            result['independently_reviewed_unresolved_or_glitching_cases']=sum(x['unresolved_or_glitching'] for x in observations)
            pins[str(review)]=sha(review)
        pins[str(native)]=sha(native);pins[str(detail)]=sha(detail);records.append(result)
    summary=corrected_summary(kind,records)
    copied={k:record.get(k) for k in ('master','native_cases','complete_five_corner_slew_rectangle_grids')}
    consistent=record.get('native_cases')==summary['native_cases'] and ('master' not in record or len(summary['masters'])==1)
    verify(pins);output.mkdir(parents=True,exist_ok=False);detail=output/'points.json';save(detail,records)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},**summary,
         original_campaign_summary=copied,original_campaign_summary_metadata_consistent=consistent,
         original_summary_labels_superseded_by_native_point_coverage=True,
         exact_native_case_coverage_verified=True,native_receipts_modified=False,
         final_load_and_slew_envelope_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--kind',choices=('expanded','fast','pulse'),required=True)
    a=p.parse_args();run(a.campaign.resolve(),a.kind,a.output.resolve())
