"""Bind the approved reliability scope and protocol obligations to actual routed registers."""
import argparse
from collections import Counter
import json
from pathlib import Path
from common import ROOT,save,sha,verify
from compare_mapped_routed_CDC import identifier,normalized


CHAIN_ROLES={
    'ref_reset_pipe':'reset_release','dco_reset_pipe':'reset_release','track_pipe':'reset_release',
    'gen_feedback_handoff.reset_pipe':'reset_release','gen_feedback_tracking.release_pipe':'reset_release',
    'core.gen_local_resets.fast_pipe':'reset_release','core.gen_local_resets.fine_pipe':'reset_release',
    'handoff.request_meta':'command_handshake','handoff.acknowledge_meta':'command_handshake',
    'gen_feedback_handoff.fine_handoff.request_meta':'command_handshake',
    'gen_feedback_handoff.fine_handoff.acknowledge_meta':'command_handshake',
    'core.gen_event_cdc.up_pipe':'bbpd_decision_noise','core.gen_event_cdc.dn_pipe':'bbpd_decision_noise'}
STATIC_PORTS={'STARTUP_COARSE','STARTUP_FINE','STARTUP_INCREASING','KI','KP'}
BUNDLES=('handoff.APPLIED_COMMAND','gen_feedback_handoff.fine_handoff.APPLIED_COMMAND')


def build(profile,mapped_module,routed_module,mapped_inventory):
    if (profile['startup']!='externally_programmed_static_until_reset'
            or profile['cdc_reliability']['scope']!='command_and_reset_synchronizers'
            or profile['cdc_reliability']['bbpd_decision_noise']!='characterize_separately'):
        raise ValueError('reviewed static-programming and command/reset reliability scope required')
    states,crossings=normalized(mapped_module,mapped_inventory)
    routed={identifier(n):(n,c) for n,c in routed_module['cells'].items()}
    if len(routed)!=len(routed_module['cells']):raise ValueError('ambiguous routed identifier normalization')
    raw={r['cell']:r for r in mapped_inventory['sequential_state']}
    chains=[];seen_roles=set();seen_stages=set()
    for chain in mapped_inventory['directly_connected_marked_two_stage_chains']:
        a,b=chain['first_cell'],chain['second_cell'];first,second=raw[a],raw[b]
        names=[q for q in first['output_aliases'] if q['async_reg']]
        if len(names)!=1 or names[0]['name'] not in CHAIN_ROLES:raise ValueError('unreviewed synchronizer identity')
        name=names[0]['name'];role=CHAIN_ROLES[name]
        if (name in seen_roles or a in seen_stages or b in seen_stages or a==b
                or not chain['matching_async_control'] or states[a]['clock_root']!=states[b]['clock_root']):
            raise ValueError('disjoint same-clock same-control two-stage synchronizers required')
        seen_roles.add(name);seen_stages.update((a,b));actual=[]
        for cell in (a,b):
            route_name,c=routed[cell]
            if c['type'].split('__')[1].rsplit('_',1)[0]!=raw[cell]['master'].split('__')[1].rsplit('_',1)[0]:
                raise ValueError('routed sequential cell polarity/family changed')
            actual.append(dict(mapped_cell=cell,routed_cell=route_name,routed_master=c['type']))
        chains.append(dict(id=name,role=role,in_aggregate_one_FIT_scope=role!='bbpd_decision_noise',
            stages=actual,clock_root=states[a]['clock_root'],first_stage_data_origins=states[a]['data_origins'],
            asynchronous_control_origins=states[a]['control_origins'],declared_event_rate_upper_hz=None,
            required_evidence=['worst_15_PVT_metastability_or_recovery_characterization',
                'routed_resolution_time_with_setup_skew_and_uncertainty','declared_event_rate_upper_bound',
                'characterization_and_timing_error_enclosures'],physical_reliability_qualified=False))
    if seen_roles!=set(CHAIN_ROLES):raise ValueError('reviewed synchronizer chain omitted')
    marked={r['cell'] for r in raw.values() if any(a['async_reg'] for a in r['output_aliases'])}
    if seen_stages!=marked:raise ValueError('marked sequential state omitted from chain obligations')
    bundles=[]
    for name in BUNDLES:
        registers=[]
        for cell,r in raw.items():
            aliases=[a for a in r['output_aliases'] if a['name']==name]
            for alias in aliases:
                route_name,c=routed[cell];registers.append(dict(logical_bit=alias['index'],mapped_cell=cell,
                    routed_cell=route_name,routed_master=c['type'],clock_root=states[cell]['clock_root']))
        if not registers or len({r['logical_bit'] for r in registers})!=len(registers):raise ValueError('unique implemented bundle registers required')
        bundles.append(dict(id=name,logical_width=34,implemented_destination_registers=sorted(registers,key=lambda r:r['logical_bit']),
            unimplemented_bits_are_not_implicitly_timed=True,
            required_evidence=['constant_or_unused_bit_provenance_for_removed_storage',
                'formal_payload_stability_and_capture_latency_for_reset_and_disable',
                'maximum_payload_arrival_before_earliest_capture_setup_at_all_15_PVT',
                'minimum_path_and_hold_checks_with_routed_clock_relationships'],
            multicycle_exception_authorized=False,bundled_data_timing_qualified=False))
    categories=Counter();review=[]
    first_cells={c['stages'][0]['mapped_cell']:c['id'] for c in chains}
    captures={r['mapped_cell']:b['id'] for b in bundles for r in b['implemented_destination_registers']}
    for crossing in crossings:
        cell=crossing['destination_cell'];tags=set()
        for kind,name,*_ in crossing['sources']:
            if kind=='primary_input':
                tags.add('static_programming_contract' if name in STATIC_PORTS else
                    'enable_withdrawal_and_release_protocol' if name=='PLL_ENABLE' else
                    'bbpd_decision_noise' if name=='BBPD' else 'unclassified_primary_input')
            else:tags.add('clock_or_protocol_relationship_review')
        if cell in first_cells:tags.add('synchronizer_first_stage')
        if cell in captures:tags.add('bundled_data_capture')
        categories.update(tags);review.append(dict(crossing,tags=sorted(tags),
             synchronizer_id=first_cells.get(cell),bundle_id=captures.get(cell),waived=False))
    return dict(profile=profile['profile'],aggregate_command_reset_max_FIT=profile['cdc_reliability']['aggregate_max_fit'],
        synchronizers=chains,bundles=bundles,static_programming_ports=sorted(STATIC_PORTS),
        static_contract_setup_at_initial_capture_qualified=False,
        crossing_candidates=review,candidate_tag_counts=dict(categories),
        source_inventory_complete=True,complete_structural_inventory_qualified=False,
        declared_event_rates_complete=False,physical_CDC_qualified=False,release_qualified=False)


def run(mapped,routed,comparison,output):
    output.mkdir(parents=True,exist_ok=False);profile=ROOT/'verification/signoff400/requirements_v2.json'
    receipts=[p/'assessment.json' for p in (mapped,routed,comparison)];a,b,c=[json.loads(p.read_text()) for p in receipts]
    if c.get('state_source_cones_and_clock_roots_match') is not True:raise ValueError('matching exhaustive mapped/routed cone comparison required')
    source=next(Path(p) for p in a['input_sha256'] if p.endswith('/mapped.json'));target=routed/'routed.json';report=mapped/'inventory.json'
    paths=[profile,*receipts,source,target,report,Path(__file__).resolve(),Path(__file__).with_name('compare_mapped_routed_CDC.py')]
    pins={str(p):sha(p) for p in paths}
    expected={str(source):a['input_sha256'][str(source)],str(target):b['artifacts'][str(target)],str(report):a['artifacts'][str(report)]}
    expected.update({str(p):c['input_sha256'][str(p)] for p in receipts[:2]})
    if any(pins[p]!=h for p,h in expected.items()):raise ValueError('CDC obligation lineage changed')
    result=build(json.loads(profile.read_text()),json.loads(source.read_text())['modules']['IntegerPLL_ProgrammedCore'],
        json.loads(target.read_text())['modules']['IntegerPLL_ProgrammedCore'],json.loads(report.read_text()))
    artifact=output/'obligations.json';save(artifact,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(artifact):sha(artifact)},
         all_marked_two_stage_chains_bound_to_routed_cells=True,
         command_reset_chains=sum(c['in_aggregate_one_FIT_scope'] for c in result['synchronizers']),
         separate_bbpd_chains=sum(c['role']=='bbpd_decision_noise' for c in result['synchronizers']),
         logical_bundles=len(result['bundles']),implemented_bundle_capture_registers=sum(len(b['implemented_destination_registers']) for b in result['bundles']),
         all_normalized_crossing_candidates_retained=len(result['crossing_candidates'])==c['routed_normalized_crossing_candidates'],
         complete_structural_inventory_qualified=False,physical_CDC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('mapped','routed','comparison','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.mapped.resolve(),a.routed.resolve(),a.comparison.resolve(),a.output.resolve())
