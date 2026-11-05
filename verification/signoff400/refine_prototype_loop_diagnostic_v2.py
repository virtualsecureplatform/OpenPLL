"""Add measured interior DCO points to a diagnostic model without qualification."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
from common_v3 import save, sha, verify
from prepare_prototype_loop_diagnostic import interpolate_period


def measurement_rc_identity(receipt):
    record=json.loads(receipt.read_text());verify(record['input_sha256']);verify(record['artifacts'])
    manifests=[Path(p) for p in record['input_sha256'] if p.endswith('/input_manifest.json')]
    if len(manifests)!=1:raise ValueError('one pinned measurement manifest required')
    recorded=json.loads(manifests[0].read_text())['input_sha256']
    identities={digest for path,digest in recorded.items() if path.endswith('/nom.spice')}
    if len(identities)!=1:raise ValueError('one analog RC identity required')
    return next(iter(identities))


def run(base, points, output):
    model=json.loads(base.read_text());verify(model['input_sha256'])
    if model.get('synthetic') is not True or model.get('physical_models_qualified') is not False:
        raise ValueError('only explicitly unqualified diagnostic models may be refined')
    provenance=Path(model['dco_table']).parent/'interpolation.json'
    original=json.loads(provenance.read_text())['endpoints']
    measured=list(original);pins=dict(model['input_sha256'])
    endpoints=[Path(p) for p in pins if p.endswith('/all_cycle_assessment/assessment.json')]
    if len(endpoints)!=2:raise ValueError('two pinned endpoint receipts required')
    identities={measurement_rc_identity(p) for p in endpoints}
    if len(identities)!=1:raise ValueError('baseline endpoint analog models differ')
    identity=next(iter(identities))
    for directory in points:
        receipt=directory/'all_cycle_assessment/assessment.json'
        record=json.loads(receipt.read_text());verify(record['input_sha256']);verify(record['artifacts'])
        if measurement_rc_identity(receipt)!=identity:raise ValueError('interior point belongs to a different analog candidate')
        metrics=receipt.parent/'all_cycle_metrics.json'
        if not record['all_captured_measurement_cycles_assessed'] or record['artifacts'].get(str(metrics))!=sha(metrics):
            raise ValueError('pinned complete all-cycle measurements required')
        value=json.loads(metrics.read_text())
        if value['corner']!=model['corner'] or value['coarse_code']!=model['coarse']:
            raise ValueError('corner/coarse identity mismatch')
        if not original[0]['fine_code']<value['fine_code']<original[-1]['fine_code']:
            raise ValueError('interior measured points required')
        measured.append(value);pins.update({str(p):sha(p) for p in (receipt,metrics)})
    measured.sort(key=lambda p:p['fine_code'])
    if len({p['fine_code'] for p in measured})!=len(measured):raise ValueError('duplicate measured code')
    table={}
    for a,b in zip(measured,measured[1:]):table.update(interpolate_period(a,b))
    output.mkdir(parents=True,exist_ok=False)
    dco=output/'dco_table.txt'
    dco.write_text(''.join(f"{model['coarse']} {code} {round(frequency*1000)}\n" for code,frequency in sorted(table.items())))
    detail=output/'interpolation.json'
    save(detail,dict(method='piecewise_linear_period_between_native_points',endpoints=[measured[0],measured[-1]],measured_points=measured,
        analog_RC_model_sha256=identity,all_measured_points_share_analog_model=True,interior_native_holdouts_verified=False,final_loading_complete=False,uncertainty_included=False,synthetic=True,release_ready=False))
    pins.update({str(p):sha(p) for p in (base,provenance,Path(__file__).resolve(),dco,detail)})
    verify(pins);model.update(input_sha256=pins,dco_table=str(dco),model_kind='unqualified_multipoint_native_period_interpolation')
    save(output/'models.json',model)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (dco,detail,output/'models.json')},
        diagnostic=True,synthetic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',required=True,type=Path);p.add_argument('--point',required=True,action='append',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run(a.base.resolve(),[x.resolve() for x in a.point],a.output.resolve())
