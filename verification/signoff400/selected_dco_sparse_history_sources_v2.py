"""Replay observed programming to 170 ns, then hold; retain actual reset history."""
import bisect,json
from pathlib import Path
from common_v3 import save,sha,verify
from selected_native_clock_shapes import load
from bounded_programming_history_sources import simplify


def hold_after(rows, stop=170e-9, end=260e-9):
    if not rows or rows[0][0]!=0 or rows[-1][0]<end or not 0<stop<end:
        raise ValueError('native coverage must enclose the requested hold interval')
    index=bisect.bisect_left([t for t,v in rows],stop)
    if rows[index][0]==stop:value=rows[index][1]
    else:
        a,v=rows[index-1];b,w=rows[index];value=v+(w-v)*(stop-a)/(b-a)
    return [p for p in rows if p[0]<stop]+[(stop,value),(end,value)]


def prepare(capture, controls, reset, output, max_program_error_v=1e-3):
    data=json.loads(capture.read_text());items=data['clock_driver_waveforms']
    if not data.get('exact_saved_knots_preserved') or not data.get('source_complete_and_all_values_finite'):
        raise ValueError('complete exact native programming capture required')
    if set(items)!=set(controls)|{'DCO_reset_driver_input'}:raise ValueError('complete programming input capture required')
    output.mkdir(exist_ok=False)
    pins={str(capture):sha(capture)}
    for name in ['selected_dco_sparse_history_sources_v2.py','selected_native_clock_shapes.py','bounded_programming_history_sources.py']:
        path=Path(__file__).with_name(name).resolve();pins[str(path)]=sha(path)
    sources={};records={}
    for i,(role,entry) in enumerate(items.items()):
        node=reset if role=='DCO_reset_driver_input' else controls[role]['driver_input_node']
        if entry['node']!=node or node in sources:raise ValueError('independent physical input identity required')
        path=Path(entry['file']);verify({str(path):data['artifacts'][str(path)]})
        rows=load(path)
        if role!='DCO_reset_driver_input':rows=hold_after(rows)
        bounded,record=simplify(rows,1e-6 if role=='DCO_reset_driver_input' else max_program_error_v)
        dest=output/f'input_{i}.pwl'
        with dest.open('x') as f:
            for t,v in bounded:f.write(f'{t:.17g} {v:.17g}\n')
        if load(dest)!=bounded:raise ValueError('PWL serialization changed certified values')
        pins[str(path)]=sha(path);pins[str(dest)]=sha(dest)
        sources[node]=f'PWL FILE "{dest}"'
        records[role]=dict(node=node,source=str(path),hold_after_ns=None if role=='DCO_reset_driver_input' else 170,**record)
    verify(pins)
    receipt=output/'assessment.json'
    save(receipt,dict(input_sha256=pins,sources=records,recorded_programming_initial_state_retained=True,
         reset_history_replayed=True,programming_after_170ns_held=True,maximum_programming_waveform_error_v=max_program_error_v,maximum_reset_waveform_error_v=1e-6,voltage_derivative_equivalence_proven=False,
         charge_error_bounded=False,frequency_correlation_qualified=False,release_ready=False))
    pins[str(receipt)]=sha(receipt)
    return sources,pins
