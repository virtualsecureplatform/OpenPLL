"""Internalize the measured active-output boundary without modifying earlier candidates."""
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from expand_keeper_receiver_boundary import expand
from audit_keeper_prescribed_boundary_roles import inventory


def run():
    base=ROOT/'build/signoff400'
    output=base/'selected_keeper_next_receiver_frontier_1523'
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{19})
    source=base/'selected_keeper_flat_geometry_C_1202/capacitance.spice'
    previous=base/'selected_keeper_receiver_expansion_1416'
    audit=base/'selected_keeper_prescribed_boundary_roles_1522'
    try:
        receipts=[p/'assessment.json' for p in (previous,audit)]
        a,b=[json.loads(p.read_text()) for p in receipts]
        for record in (a,b):
            verify(record['input_sha256'])
            verify(record['artifacts'])
        if a['input_sha256'].get(str(source)) != sha(source):
            raise ValueError('same original flat capacitance circuit required')
        old=json.loads((previous/'interface.json').read_text())
        rows=json.loads((audit/'boundaries.json').read_text())
        front=[r['node'] for r in rows if r['kind']=='retained_primitive_terminal' and 'MOS_diffusion' in r['terminal_roles']]
        if len(front)!=1:
            raise ValueError('exactly one audited nonrail diffusion frontier required')
        receiver=front[0]
        files=[source,*receipts,previous/'interface.json',audit/'boundaries.json',Path(__file__).resolve()]
        files += [Path(__file__).with_name(n) for n in ['expand_keeper_receiver_boundary.py',
            'export_keeper_conditional_DCO_v2.py','native_spice_comments.py',
            'audit_keeper_DCO_driver_C_cut.py','audit_keeper_prescribed_boundary_roles.py']]
        pins={str(p):sha(p) for p in files}
        save(output/'status.json',dict(state='preparing_next_native_receiver_frontier',release_ready=False))
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
            model,interface,added=expand(source.read_text(),set(old['selected_primitive_names']),receiver)
            if not set(old['interior_nodes']) <= set(interface['interior_nodes']):
                raise ValueError('previous unknown became prescribed')
            new_rows=inventory(model,interface)
        if len(added)>256:
            raise ValueError('expansion exceeded predeclared 256 primitive preparation limit')
        circuit,detail,boundaries=[output/n for n in ('conditional.spice','interface.json','boundaries.json')]
        circuit.write_text(model)
        save(detail,interface)
        save(boundaries,new_rows)
        remaining=[r['node'] for r in new_rows if r['kind']=='retained_primitive_terminal' and 'MOS_diffusion' in r['terminal_roles']]
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (circuit,detail,boundaries)},
             previous_prescribed_diffusion=receiver,previous_prescribed_diffusion_now_internal=True,
             added_primitive_names=added,added_primitives=len(added),selected_primitives=len(interface['selected_primitive_names']),
             previous_unknowns_preserved=True,retained_cards_unchanged=True,
             remaining_nonrail_prescribed_diffusions=remaining,
             boundary_ports=len(interface['boundary_ports']),PLLOUT_not_prescribed=True,
             earlier_candidates_unchanged=True,native_execution_allowed=False,
             native_correlation_complete=False,independent_environment_supplied=False,
             changed_controller_prediction_qualified=False,model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='next_receiver_frontier_prepared_without_native_execution',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__=='__main__':
    run()
