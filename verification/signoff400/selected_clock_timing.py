"""Validate explicit diagnostic clock timing, separately from detector dynamics."""
import json
from common_v3 import verify

KEYS=tuple(f'{path}_{edge}_ps' for path in ['divided_output','feedback_wire','reference_wire'] for edge in ['rise','fall'])


def load(path,registry=None,diagnostic=True):
    value=json.loads(path.read_text())
    if value.get('schema_version')!=1 or value.get('diagnostic') is not diagnostic or value.get('release_ready') is not False:
        raise ValueError('clock timing packet scope mismatch')
    if not diagnostic and (value.get('clock_timing_qualified') is not True or value.get('unwrapped_causal_latency_qualified') is not True):
        raise ValueError('qualified clock timing model required')
    op=value['operating_point']
    if op.get('corner') not in ['tt','ff','ss','sf','fs'] or op.get('temperature_c')!=27 or op.get('supply_v')!=1.8:
        raise ValueError('unsupported clock timing operating point')
    delays=value['delay_ps']
    if set(delays)!=set(KEYS) or any(type(v) is not int or v<0 for v in delays.values()):raise ValueError('complete nonnegative integer-ps clock timing required')
    for edge in ['rise','fall']:
        if delays['divided_output_'+edge+'_ps']+delays['feedback_wire_'+edge+'_ps']>=10000 or delays['reference_wire_'+edge+'_ps']>=10000:
            raise ValueError('clock timing exceeds diagnostic reset/transport contract')
    verify(value['input_sha256']);verify(value['reference_model_sha256'])
    if registry:
        if value['operating_point']!=registry['analog']['operating_point']:raise ValueError('clock timing operating point mismatch')
        if any(registry['analog']['input_sha256'].get(k)!=v for k,v in value['reference_model_sha256'].items()):raise ValueError('clock timing physical identity mismatch')
    return value


def arguments(value):
    return ['+clock_'+key+'='+str(value['delay_ps'][key]) for key in KEYS]
