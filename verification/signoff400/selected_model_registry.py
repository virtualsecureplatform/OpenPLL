"""Versioned diagnostic model registry with separate analog/interface identity.

Controller sources belong to run receipts, not calibration cache keys. Qualification
still requires the prototype audit; this registry never manufactures qualification.
"""
import hashlib,json,math
from pathlib import Path
from common_v3 import sha,verify,save


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate(value):
    if value.get('schema_version')!=1 or value.get('qualification')!='diagnostic':
        raise ValueError('supported diagnostic registry required')
    if value.get('release_ready') is not False:raise ValueError('registry cannot qualify a release')
    for key in ['analog','interface']:
        identity=value[key]
        if not identity.get('input_sha256'):raise ValueError('pinned identity required')
        verify(identity['input_sha256'])
        if value[key+'_key']!=fingerprint(identity):raise ValueError('model identity mismatch')
    op=value['analog']['operating_point']
    if op['corner'] not in ['tt','ff','ss','sf','fs'] or op['temperature_c']!=27 or op['supply_v']!=1.8:
        raise ValueError('unsupported prototype operating point')
    seen=set()
    for row in value['points']:
        key=(row['coarse'],row['fine'])
        if any(type(x) is not int for x in key) or not 0<=key[0]<=47 or not 8<=key[1]<=247 or key in seen:
            raise ValueError('duplicate or unsupported measured code')
        seen.add(key)
        if not math.isfinite(row['frequency_hz']) or row['frequency_hz']<=0:raise ValueError('invalid frequency')
        p=Path(row['receipt']);
        if sha(p)!=row['receipt_sha256']:raise ValueError('measurement changed')
        from run_selected_mixed_signal import measured_point
        c,f,mhz=measured_point(p)
        if (c,f)!=key or round(row['frequency_hz']*1000)!=mhz:raise ValueError('measurement frequency/code mismatch')
    if not seen:raise ValueError('no measured points')
    return value


def create(analog,interface,receipts,output):
    from run_selected_mixed_signal import measured_point
    points=[]
    for p in receipts:
        p=p.resolve();c,f,mhz=measured_point(p)
        points.append(dict(coarse=c,fine=f,frequency_hz=mhz/1000,receipt=str(p),receipt_sha256=sha(p)))
    value=dict(schema_version=1,analog=analog,interface=interface,analog_key=fingerprint(analog),interface_key=fingerprint(interface),points=points,qualification='diagnostic',release_ready=False)
    validate(value)
    if output.exists():raise FileExistsError(output)
    save(output,value);return value
