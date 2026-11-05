#!/usr/bin/env python3
"""TT27 capture diagnostic with actual parent max-RC and current receiver RC.

Uses fixed rails, ideal REF/divider/reset boundary drivers, static omitted
aggressors and no external pad loads. Reset generation, dynamic outside pin
loads, near-coincidence, full PVT, noise and metastability remain unqualified.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from check_current_receiver_capture import verify as verify_pins
from check_compact_clock_tree import verify
from characterize_compact_propagation import ROOT, XYCE
from characterize_coupled_bbpd import read_coupled_rows, capture_metrics
from guarded_native_admission import AdmissionDeferred, launch, scan
from run_dco_qualification import sha, save


def prepare(out):
    base = ROOT/'build/timing400/release_001'
    old = base/'current_receiver_capture_tt27_002'
    parent = base/'candidate_interconnect_audit_002'
    previous = json.loads((old/'run_001/assessment.json').read_text())
    verify_pins(previous['input_sha256'])
    assert previous['signed_capture_passes'] == 4
    rc = verify(parent/'assessment.json')
    assert rc['all_357_net_endpoint_sets_match_database']
    pins = dict(previous['input_sha256'])
    for i,row in enumerate(previous['results']):
        for filename,key in (('capture.prn','waveform_sha256'),('run.log','native_log_sha256')):
            path = old/f'run_001/point_{i}'/filename
            assert sha(path) == row[key], path
            pins[str(path)] = row[key]
    pins.update({str(parent/'assessment.json'):sha(parent/'assessment.json'),
                 str(old/'run_001/assessment.json'):sha(old/'run_001/assessment.json')})
    pins.update(rc['artifacts'])
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and path.endswith('.py') and Path(path).resolve().is_relative_to(ROOT):
            pins[str(Path(path).resolve())] = sha(path)
    verify_pins(pins)
    binding = json.loads((parent/'bindings.max.json').read_text())
    nets = json.loads((parent/'nets.max.json').read_text())
    symbols = binding['boundary_node_to_spice']
    # Keep detector node names for the independently retained waveform reader.
    aliases = {'detector:BBPD[0]':'BBPD[0]', 'detector:BBPD[1]':'BBPD[1]',
               'detector:REF':'REF', 'detector:CLKDIVR':'CLKDIVR', 'detector:RESET_N':'RESET_N'}
    actual = {node:aliases.get(node, 'parent_'+symbol) for node,symbol in symbols.items()}
    assert len(set(actual.values())) == len(actual)
    by_symbol = {symbol:actual[node] for node,symbol in symbols.items()}
    ports = ['VGND']+[by_symbol[s] for s in binding['port_order'][1:]]
    lines = ['Xparent']
    for i in range(0,len(ports),8):
        lines.append('+ '+' '.join(ports[i:i+8]))
    lines.append('+ PLL_PARENT_RC')
    excluded = {'BBPD[0]','BBPD[1]','BBPD_RESET_N','REFCLK','CLKDIV_RETIMED'}
    biases = []
    for name,row in nets.items():
        if name in excluded:
            continue
        endpoints = row['endpoints']
        drivers = [n for n,(k,d) in endpoints.items() if k=='I' and d=='O' or k=='P' and d in ('I','B')]
        assert len(drivers) == 1, (name, drivers)
        node = drivers[0]
        value = '{VDD}' if name == 'VPB' else '0'
        lines.append(f'Vstatic{len(biases)} {actual[node]} 0 {value}')
        biases.append(dict(net=name, boundary=node, voltage=value))
    out.mkdir(parents=True, exist_ok=False)
    cases = []
    for phase in (-200,200):
        for edge in (20,200):
            source = old/f'phase{phase}_edge{edge}/capture.cir'
            pins[str(source)] = sha(source)
            text = source.read_text()
            kept = [line for line in text.splitlines() if not line.startswith(
                ('VRESET ', 'VREF ', 'VDIV ', 'XBBPD ', 'Xreceiver '))]
            additions = [f'.include "{parent}/parent.max.spice"', *lines,
                f'VRESET {actual["digital:BBPD_RESET_N"]} 0 PWL(0 0 1n 0 1.02n {{VDD}})',
                f'VREF {actual["REFCLK"]} 0 PULSE(0 {{VDD}} 10n {edge}p {edge}p 20n 40n)',
                f'VDIV {actual["digital:CLKDIV_RETIMED"]} 0 PULSE(0 {{VDD}} {10+phase/1000:g}n {edge}p {edge}p 20n 40n)',
                'XBBPD BBPD[0] BBPD[1] CLKDIVR REF RESET_N VGND VNB VPB VPWR IntegerPLL_BBPD',
                f'Xreceiver {actual["digital:BBPD[0]"]} {actual["digital:BBPD[1]"]} {actual["digital:BBPD_RESET_N"]} VGND VNB VPB VPWR UPQ DNQ bbpd_receiver']
            position = kept.index('.options timeint reltol=1e-5 abstol=1e-9 method=gear')
            kept[position:position] = additions
            text = '\n'.join(kept)+'\n'
            assert text.count('Xparent\n') == text.count('XBBPD ') == text.count('Xreceiver ') == 1
            directory = out/f'phase{phase}_edge{edge}'
            directory.mkdir()
            circuit = directory/'capture.cir'
            circuit.write_text(text)
            pins[str(circuit)] = sha(circuit)
            cases.append(dict(phase_ps=phase, edge_ps=edge, circuit=str(circuit)))
    verify_pins(pins)
    save(out/'plan.json', dict(input_sha256=pins, cases=cases,
        pvt=dict(corner='tt',temperature_c=27,supply_v=1.8),
        parent_rc='max', receiver_rc='max', all_357_parent_nets_included=True,
        static_omitted_net_drivers=biases, total_budget_s=43200,
        includes_admission_wait=True, automatic_identical_retry=False,
        external_pad_loads_included=False, generated_reset_included=False,
        physical_timing_qualified=False, release_qualified=False, scope=__doc__))
    print('Prepared four capture diagnostics with the assembled coupled parent network.')


def run(plan_path, controller):
    started = time.monotonic()
    deadline = started+43200
    plan = json.loads(plan_path.read_text())
    assert plan['total_budget_s'] == 43200 and len(plan['cases']) == 4
    pins = {**plan['input_sha256'], str(plan_path):sha(plan_path)}
    verify_pins(pins)
    out = plan_path.parent/'run_001'
    out.mkdir()
    save(out/'owner.json', dict(runner_pid=os.getpid(),
        started_utc=datetime.now(timezone.utc).isoformat(),
        deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+(deadline-time.monotonic()),
        total_budget_s=43200, includes_admission_wait=True, automatic_identical_retry=False))

    def remaining():
        value = deadline-time.monotonic()
        if value <= 0:
            raise TimeoutError('total 12h budget exhausted')
        return value

    def status(state, **fields):
        save(out/'status.json', dict(state=state, remaining_budget_s=max(0,deadline-time.monotonic()),
            observed_utc=datetime.now(timezone.utc).isoformat(), release_qualified=False, **fields))

    child = None
    results = []
    try:
        for index,case in enumerate(plan['cases']):
            verify_pins(pins)
            point = out/f'point_{index}'
            point.mkdir()
            command = [str(XYCE),'-linsolv','KLU','-quiet','-o',str(point/'capture'),case['circuit']]
            env = dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
            with (point/'run.log').open('x') as log:
                while True:
                    remaining()
                    try:
                        if len(scan()) >= 4:
                            raise AdmissionDeferred('four native slots occupied')
                        child = launch(command,env,log,controller,point/'guarded_admission.json')
                        break
                    except AdmissionDeferred as error:
                        status('waiting_for_guarded_native_capacity',case_index=index,reason=str(error))
                        time.sleep(min(30,remaining()))
                save(point/'launch.json',dict(pid=child.pid,command=command))
                status('native_running',case_index=index,native_pid=child.pid)
                code = child.wait(timeout=remaining())
            child = None
            if code:
                status('native_nonpass',case_index=index,exit_code=code)
                return
            rows = read_coupled_rows(point/'capture.prn')
            assert all(row[0] == i for i,row in enumerate(rows))
            metrics = capture_metrics(rows,1.8,case['phase_ps'])
            result = dict(**case,**metrics,waveform_sha256=sha(point/'capture.prn'),
                native_log_sha256=sha(point/'run.log'),release_qualified=False)
            save(point/'assessment.json',result)
            results.append(result)
        verify_pins(pins)
        remaining()
        save(out/'assessment.json',dict(input_sha256=pins,results=results,
            signed_capture_passes=sum(r['direction_and_two_event_capture_pass'] for r in results),
            parent_and_receiver_rc_included=True, physical_timing_qualified=False,
            whole_pll_qualification_cases_passed=0, release_qualified=False, scope=__doc__))
        status('diagnostics_complete',cases_completed=len(results))
    except (TimeoutError,subprocess.TimeoutExpired):
        status('timeout_inconclusive',cases_completed=len(results))
    except Exception as error:
        status('diagnostic_error',cases_completed=len(results),reason=str(error))
        raise
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--controller-pid',type=int)
    args = parser.parse_args()
    assert Path.cwd().resolve() == ROOT
    if args.action == 'prepare':
        prepare(args.output.resolve())
    else:
        assert args.controller_pid
        run(args.output.resolve()/'plan.json',args.controller_pid)
