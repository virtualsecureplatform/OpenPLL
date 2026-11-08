"""Reuse closed diagnostic receipts only when their exact model and case identities match."""
import json
from pathlib import Path
from common_v3 import sha,verify


def load_case(receipt,arguments,required_inputs):
    receipt=Path(receipt);record=json.loads(receipt.read_text())
    verify(record['input_sha256']);verify(record['artifacts'])
    inputs=receipt.with_name('inputs.json')
    if record['input_sha256'].get(str(inputs))!=sha(inputs):raise ValueError('case arguments must be pinned')
    domain=json.loads(inputs.read_text())
    if domain.get('case_arguments')!=arguments or domain.get('frequency_table_kind')!='linear_frequency':
        raise ValueError('case arguments or interpolation differs')
    if any(record['input_sha256'].get(p)!=digest for p,digest in required_inputs.items()):
        raise ValueError('required model, source or build identity differs')
    if record.get('release_ready') is not False or record.get('diagnostic') is not True:
        raise ValueError('diagnostic-only case required')
    if record['state']=='needs_native_tuning_points':
        if not record.get('measurement_requests') or record.get('functional_trace_pass') is not False:
            raise ValueError('missing-model case must remain unresolved')
        return record
    count=1 if arguments['scenario']==0 else 2
    if (record.get('native_exit')!=0 or not record.get('terminal_marker_present')
            or not record.get('reference_phase_coverage_pass') or record.get('failure')
            or len(record.get('segments',[]))!=count):
        raise ValueError('completed scenario required; infrastructure failures cannot be reused as gain failures')
    return record
