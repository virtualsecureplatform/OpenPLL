"""Complete a two-group initial-voltage factorial with unchanged112 boundaries.

Group A is the twelve context nodes with >100 mV111/112 initial difference.
Group B is every other private node. Hybrid physical reachability is not assumed.
"""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from run_selected_checkpoint_IC_swap import initial
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def partition(target, donor):
    if set(target) != set(donor) or len(target) != 5980:
        raise ValueError('exact common5980-node private state required')
    context = {n for n in target if n.startswith('__context_node_') and abs(target[n]-donor[n]) > .1}
    if len(context) != 12:
        raise ValueError('predeclared twelve large-difference context nodes required')
    return context, set(target)-context


def run(target, donor, all_swap, image, group, cpu, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {cpu})
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        records = []
        paths = [Path(__file__).resolve(), image, *(Path(__file__).with_name(n) for n in
                 ('common_v3.py','resources.py','compiled_charge_v2.py','run_selected_checkpoint_IC_swap.py',
                  'assess_selected_detector_prefix.py','assess_selected_isolated_control.py'))]
        for folder, code in ((target,112), (donor,111)):
            m = json.loads((folder/'manifest.json').read_text())
            verify(m['input_sha256'])
            if (m['controls']['coarse'],m['controls']['fine'],m['initialized_private_nodes']) != (20,code,5980):
                raise ValueError('selected neighboring own-state references required')
            if m['operating_point'] != {'corner':'tt','supply_v':1.8,'temperature_c':27}:
                raise ValueError('selected nominal TT operating point required')
            if json.loads((folder/'status.json').read_text())['state'] != 'saved_state_DCO_diagnostic_complete':
                raise ValueError('normally completed own-state references required')
            records.append(m)
            paths += [folder/n for n in ('manifest.json','assessment.json','status.json','devices.spice',
                                         'sources.spice','initial_conditions.spice','control.spice')]
        if sha(target/'devices.spice') != sha(donor/'devices.spice'):
            raise ValueError('identical physical circuit required')
        all_m = json.loads((all_swap/'manifest.json').read_text())
        all_a = json.loads((all_swap/'assessment.json').read_text())
        verify(all_a['input_sha256'])
        verify(all_a['artifacts'])
        if json.loads((all_swap/'status.json').read_text())['state'] != 'checkpoint_IC_swap_assessed' or all_a['normal_native_completion'] is not True:
            raise ValueError('completed all-donor-state factorial corner required')
        for folder in (target,donor):
            if all_m['input_sha256'].get(str(folder/'manifest.json')) != sha(folder/'manifest.json'):
                raise ValueError('existing all-state control must bind these exact references')
        paths += [all_swap/n for n in ('manifest.json','assessment.json','status.json')]
        before, after = [initial(p/'initial_conditions.spice') for p in (target,donor)]
        context, complement = partition(before, after)
        selected = context if group == 'context' else complement
        source_lines = {line.split('(')[1].split(')')[0]:line
                        for line in (donor/'initial_conditions.spice').read_text().splitlines()}
        lines = [source_lines[line.split('(')[1].split(')')[0]]
                 if line.split('(')[1].split(')')[0] in selected else line
                 for line in (target/'initial_conditions.spice').read_text().splitlines()]
        ic = output/'initial_conditions.spice'
        ic.write_text('\n'.join(lines)+'\n')
        actual = initial(ic)
        if any(actual[n] != (after[n] if n in selected else before[n]) for n in before):
            raise ValueError('exact group intervention required')
        selection = output/'state_partition.json'
        save(selection, dict(group=group, context_nodes=sorted(context), context_size=len(context),
            complement_size=len(complement), donor_nodes_selected=len(selected),
            actual_changed_nodes=sum(before[n] != actual[n] for n in before),
            grouping_uses_frequency_results=False, hybrid_physical_reachability_assumed=False))
        deck = output/'control.spice'
        text = (target/'control.spice').read_text()
        for old,new in ((target/'initial_conditions.spice',ic),(target/'control.raw',output/'control.raw')):
            if text.count(str(old)) != 1:
                raise ValueError('unique IC/observation substitution required')
            text = text.replace(str(old),str(new))
        deck.write_text(text)
        paths += [ic,selection,deck,target/'control.raw']
        pins = dict(records[0]['input_sha256'])
        pins.update({str(p):sha(p) for p in paths})
        verify(pins)
        binaries = [Path(p) for p in pins if p.endswith('/Xyce')]
        if len(binaries) != 1:
            raise ValueError('unique pinned native simulator required')
        save(output/'manifest.json', dict(input_sha256=pins, group=group, CPU=cpu,
            observed_roles=records[0]['observed_roles'], context_nodes=sorted(context),
            operating_point=records[0]['operating_point'], physical_cards_sources_reset_solver_unchanged=True,
            memory_GiB=8, native_cap_s=10800, automatic_identical_retry=False,
            hybrid_physical_reachability_assumed=False, release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+10800
        save(output/'status.json', dict(state='checkpoint_IC_factorial_native_running', release_ready=False))
        with lease(1,8,deadline):
            execute(['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,
                     binaries[0],'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,8)
        verify(pins)
        raw = output/'control.raw'
        rows, info = read_prefix(raw,records[0]['observed_roles'])
        reference, ri = read_prefix(target/'control.raw',records[0]['observed_roles'])
        if any(i['incomplete_final_sample_discarded'] or abs(r[-1][0]-records[0]['simulation_end_s']) > 1e-18
               for r,i in ((rows,info),(reference,ri))):
            raise ValueError('complete common native horizon required')
        windows = []
        for start,stop in ((35,45),(40,55),(45,55),(50,59),(70,84)):
            f, baseline = [frequency(r,start,stop) for r in (rows,reference)]
            windows.append(dict(window_ns=[start,stop],group_control=f,own_state112=baseline,
                difference_ppm=(f['frequency_mhz']/baseline['frequency_mhz']-1)*1e6))
        save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(raw):sha(raw)},
            group=group, normal_native_completion=True, windows=windows,
            hybrid_physical_reachability_assumed=False, model_family_qualified=False, release_ready=False))
        save(output/'status.json', dict(state='checkpoint_IC_factorial_assessed', release_ready=False))
    except BaseException as error:
        save(output/'status.json', dict(state='stopped_without_qualification', reason=repr(error),release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('target','donor','all-swap','image','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--group',choices=('context','complement'),required=True)
    p.add_argument('--cpu',type=int,choices=(19,22),required=True)
    a = p.parse_args()
    run(a.target.resolve(),a.donor.resolve(),a.all_swap.resolve(),a.image.resolve(),a.group,a.cpu,a.output.resolve())
