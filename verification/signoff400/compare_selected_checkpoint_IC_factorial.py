"""Audit complementary IC interventions, wait, then measure their interaction."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import save, sha, verify
from resources import identity, lease
from run_selected_checkpoint_IC_swap import initial
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def run(target, donor, all_swap, context, complement, runtime, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {24})
    save(output/'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        before, after = [initial(p/'initial_conditions.spice') for p in (target,donor)]
        if set(before) != set(after) or len(before) != 5980:
            raise ValueError('exact full shared private-node inventory required')
        group = {n for n in before if n.startswith('__context_node_') and abs(before[n]-after[n]) > .1}
        if len(group) != 12:
            raise ValueError('twelve predeclared context nodes required')
        paths = [Path(__file__).resolve(), target/'initial_conditions.spice', donor/'initial_conditions.spice',
                 donor/'manifest.json', *(Path(__file__).with_name(n) for n in
                 ('common_v3.py','resources.py','run_selected_checkpoint_IC_swap.py',
                  'assess_selected_detector_prefix.py','assess_selected_isolated_control.py'))]
        folders = dict(own112=target, all111=all_swap, context111=context, complement111=complement)
        tm = json.loads((target/'manifest.json').read_text())
        for key, folder in folders.items():
            m = json.loads((folder/'manifest.json').read_text())
            verify(m['input_sha256'])
            if m['observed_roles'] != tm['observed_roles']:
                raise ValueError('same physical observations required')
            paths += [folder/'manifest.json', folder/'control.spice']
            if key != 'own112':
                for basis in (target,donor):
                    if m['input_sha256'].get(str(basis/'manifest.json')) != sha(basis/'manifest.json'):
                        raise ValueError('exact same original reference pair required')
                ic = donor/'initial_conditions.spice' if key == 'all111' else folder/'initial_conditions.spice'
                expected = (target/'control.spice').read_text()
                for old,new in ((target/'initial_conditions.spice',ic),(target/'control.raw',folder/'control.raw')):
                    if expected.count(str(old)) != 1:
                        raise ValueError('unique original IC and observation reference required')
                    expected = expected.replace(str(old),str(new))
                if expected != (folder/'control.spice').read_text():
                    raise ValueError('physical cards, sources, solver or observations changed')
                paths.append(ic)
            if key in ('context111','complement111'):
                observed = initial(folder/'initial_conditions.spice')
                if set(observed) != set(before):
                    raise ValueError('partial intervention lost private initial nodes')
                chosen = group if key == 'context111' else set(before)-group
                if any(observed[n] != (after[n] if n in chosen else before[n]) for n in before):
                    raise ValueError('interventions are not the exact complementary factorial')
                label = 'context' if key == 'context111' else 'complement'
                binding = runtime/label/'binding.json'
                b = json.loads(binding.read_text())
                verify(b['input_sha256'])
                if b['case'] != str(folder) or b['runtime_dependency_files'] != 319:
                    raise ValueError('exact-case actual runtime capture required')
                paths += [binding,runtime/label/'namespace.json',folder/'owner.json']
        pins = {str(p):sha(p) for p in paths}
        save(output/'inputs.json', dict(input_sha256=pins, context_nodes=sorted(group),
            context_size=12, complement_size=5968, exact_complementary_initial_voltages_verified=True,
            only_IC_include_and_raw_destination_deck_changes=True, native_cases_launched=0))
        owners = {folder:json.loads((folder/'owner.json').read_text()) for folder in (context,complement)}
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+11100
        while True:
            pending = []
            for folder,owner in owners.items():
                state = json.loads((folder/'status.json').read_text())['state']
                if state == 'checkpoint_IC_factorial_assessed':
                    continue
                if state != 'checkpoint_IC_factorial_native_running' or identity(owner['pid']) != owner['birth']:
                    raise ValueError('original factorial case stopped without normal completion')
                pending.append(str(folder))
            if not pending:
                break
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('observer deadline; native jobs unchanged')
            save(output/'status.json', dict(state='waiting_for_IC_factorial_controls',pending=pending,release_ready=False))
            time.sleep(10)
        tables = {}
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+300):
            for key,folder in folders.items():
                receipt = folder/'assessment.json'
                a = json.loads(receipt.read_text())
                verify(a['input_sha256'])
                verify(a['artifacts'])
                expected = ('saved_state_DCO_diagnostic_complete' if key == 'own112' else
                            'checkpoint_IC_swap_assessed' if key == 'all111' else 'checkpoint_IC_factorial_assessed')
                if json.loads((folder/'status.json').read_text())['state'] != expected:
                    raise ValueError('all four native cases must complete normally')
                rows,info = read_prefix(folder/'control.raw',tm['observed_roles'])
                if info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-tm['simulation_end_s']) > 1e-18:
                    raise ValueError('complete equal native horizons required')
                tables[key] = rows
                for p in (receipt,folder/'control.raw',folder/'status.json'):
                    pins[str(p)] = sha(p)
        windows = []
        for start,stop in ((35,45),(40,55),(50,59),(70,84)):
            f = {key:frequency(rows,start,stop)['frequency_mhz'] for key,rows in tables.items()}
            a = f['context111']-f['own112']
            b = f['complement111']-f['own112']
            interaction = f['all111']-f['context111']-f['complement111']+f['own112']
            windows.append(dict(window_ns=[start,stop],frequency_MHz=f,context_effect_with_other_state112_MHz=a,
                complement_effect_with_context112_MHz=b,interaction_MHz=interaction,
                full_IC_shift_MHz=f['all111']-f['own112']))
        verify(pins)
        save(output/'assessment.json', dict(input_sha256=pins,windows=windows,
            all_four_native_cases_completed_normally=True, exact_complementary_IC_interventions_verified=True,
            context_nodes=sorted(group),context_size=12,complement_size=5968,
            scope='Two-group initial-voltage sensitivity and interaction in one conditional TT112 partition. '
                  'This localizes model state dependence; physical reachability of hybrid states and '
                  'full-native switched-code equivalence are not established.',
            hybrid_physical_reachability_assumed=False, full_native_switched_reference_available=False,
            uniform_model_uncertainty_qualified=False, model_family_qualified=False, release_ready=False))
        save(output/'status.json',dict(state='checkpoint_IC_factorial_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),native_jobs_unchanged=True,release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('target','donor','all-swap','context','complement','runtime','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    run(a.target.resolve(),a.donor.resolve(),a.all_swap.resolve(),a.context.resolve(),a.complement.resolve(),a.runtime.resolve(),a.output.resolve())
