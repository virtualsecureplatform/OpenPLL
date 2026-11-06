"""Measure selected REFCLK-domain enable setup/hold at explicit input slews.

Existing native conditional cell views and routed min/max RC are retained.
These sampled budgets do not qualify a continuous slew range, asynchronous
enable, reset, or the fine-domain enable withdrawal paths.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from common_v3 import ROOT, save, sha, verify
from selected_physical_rtl import source_pins
from compare_mapped_routed_CDC import clock_roots
from screen_prototype_decision_hold_phase_v3 import OPENROAD
from resources import lease
from compiled_charge_v2 import execute


def paths_from_report(text, targets):
    records = []
    number = r'[-+0-9.eE]+'
    for block in text.split('Startpoint: ')[1:]:
        start = block.splitlines()[0].split()[0]
        endpoint = re.search(r'^Endpoint: (\S+)',block,re.M)
        kind = re.search(r'Path Type: (min|max)',block)
        slack = re.search('('+number+r')\s+slack \((MET|VIOLATED)\)',block)
        edges = re.findall('('+number+r')\s+clock REFCLK \((rise|fall) edge\)',block)
        if start != 'PLL_ENABLE' or not all((endpoint,kind,slack)) or len(edges) != 2:
            raise ValueError('complete explicit REFCLK input path required')
        if endpoint[1] not in targets or any(direction != 'rise' for _,direction in edges):
            raise ValueError('unexpected enable capture endpoint or edge')
        expected = [0.,40.] if kind[1] == 'max' else [0.,0.]
        if [float(t) for t,_ in edges] != expected:
            raise ValueError('single-cycle40ns reference relation required')
        value = float(slack[1])
        if not math.isfinite(value):
            raise ValueError('finite input path slack required')
        records.append(dict(endpoint=endpoint[1],kind=kind[1],zero_input_delay_slack_ns=value,
            required_external_setup_ns=40-value if kind[1] == 'max' else None,
            required_external_hold_ns=-value if kind[1] == 'min' else None))
    if len(records) != 2*len(targets):
        raise ValueError('every structural REFCLK enable destination requires min/max paths')
    for kind in ('min','max'):
        seen = [r['endpoint'] for r in records if r['kind'] == kind]
        if len(set(seen)) != len(targets) or set(seen) != set(targets):
            raise ValueError('duplicate or missing enable capture path')
    return records


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{28})
    base = ROOT/'build/signoff400'
    inventory = base/'prototype_v3_selected_routed_CDC_019'
    ir = json.loads((inventory/'assessment.json').read_text())
    verify(ir['input_sha256']); verify(ir['artifacts'])
    data = json.loads((inventory/'inventory.json').read_text())
    module = json.loads((inventory/'routed.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
    clock = clock_roots(module)
    targets = sorted(r['cell'].lstrip('\\') for r in data['sequential_state']
        if clock(r['clock_bit']) == ('primary','REFCLK',0,0)
        and any(s['kind'] == 'primary_input' and s['name'] == 'PLL_ENABLE' for s in r['data_sources']))
    if len(targets) != 76 or len(set(targets)) != 76:
        raise ValueError('all76 selected raw-enable REFCLK destinations required')
    image = ROOT/'build/apptainer/openpll-release-modern.sif'
    prefix = ['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',str(image)]
    tool_hash = subprocess.check_output([*prefix,'sha256sum',OPENROAD],text=True).split()[0]
    pins = source_pins()
    paths = [image,Path(__file__).resolve(),inventory/'assessment.json',inventory/'inventory.json',
        inventory/'routed.json',*(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py',
        'compiled_charge_v2.py','selected_physical_rtl.py','compare_mapped_routed_CDC.py'))]
    pins.update({str(p):sha(p) for p in paths})
    save(output/'inputs.json',dict(input_sha256=pins,container_tool_sha256={OPENROAD:tool_hash},
        REFCLK_destination_registers=targets,input_slews_ns=[.1,1.],reference_period_ns=40))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    results = []
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    for corner in ('tt','ff','ss','sf','fs'):
        baseline = base/f'prototype_v3_selected_402p1_timing_{corner}_019'
        receipt = baseline/'assessment.json'
        b = json.loads(receipt.read_text()); verify(b['artifacts'])
        if b['input_sha256'].get(OPENROAD) != tool_hash or b['native_model_corner'] != corner:
            raise ValueError('same pinned native corner/tool baseline required')
        original = baseline/'fixed_divide16/screen.tcl'
        sdc = baseline/'fixed_divide16/screen.sdc'
        for p in (original,sdc):
            if b['artifacts'].get(str(p)) != sha(p):
                raise ValueError('baseline measurement script/constraints changed')
        text = original.read_text().split('report_parasitic_annotation',1)[0]
        if str(base/'prototype_v3_selected_route_019/route.odb') not in text:
            raise ValueError('selected routed database required')
        for line in text.splitlines():
            if line.startswith(('read_liberty ','read_spef ','read_db ')):
                p = Path(line.split()[-1])
                expected_hash = b['input_sha256'].get(str(p),b['artifacts'].get(str(p)))
                if expected_hash != sha(p):
                    raise ValueError('native RC/library/database dependency changed: '+str(p))
                pins[str(p)] = expected_hash
        pins[str(receipt)] = sha(receipt)
        for p in (original,sdc):pins[str(p)] = sha(p)
        for slew in (.1,1.):
            folder = output/f'{corner}_slew{slew:g}'
            folder.mkdir()
            constraints = folder/'input.sdc'
            constraints.write_text(sdc.read_text()+f'''\n# Isolate external-port setup/hold requirements at zero input delay.
set_input_delay 0 -clock REFCLK -max [get_ports PLL_ENABLE]
set_input_delay 0 -clock REFCLK -min [get_ports PLL_ENABLE]
set_input_transition {slew} [get_ports PLL_ENABLE]
''')
            if text.count('source '+str(sdc)) != 1:
                raise ValueError('unique original constraints source required')
            script = folder/'paths.tcl'
            script.write_text(text.replace('source '+str(sdc),'source '+str(constraints))+
                'set endpoints [get_pins {'+' '.join(n+'/D' for n in targets)+'}]\n'+
                'if {[llength $endpoints]!=76} {error "capture pin inventory differs"}\n'+
                'report_checks -from [get_ports PLL_ENABLE] -to $endpoints -path_delay min_max -group_path_count 100 -endpoint_path_count 1 -digits 9\nexit\n')
            with lease(1,4,deadline):
                execute([*prefix,OPENROAD,'-no_init','-exit',script],folder/'paths.log',deadline,4)
            log = (folder/'paths.log').read_text()
            if re.search(r'\[ERROR|Error:|STA-(1648|1650)',log):
                raise ValueError('input path native timing query failed')
            rows = paths_from_report(log,targets)
            results.append(dict(corner=corner,input_slew_ns=slew,paths=rows,
                maximum_required_setup_ns=max(r['required_external_setup_ns'] for r in rows if r['kind']=='max'),
                maximum_required_hold_ns=max(r['required_external_hold_ns'] for r in rows if r['kind']=='min')))
            for p in (constraints,script,folder/'paths.log'):pins[str(p)] = sha(p)
    verify(pins)
    detail = output/'paths.json'; save(detail,results)
    save(output/'assessment.json',dict(input_sha256=pins,container_tool_sha256={OPENROAD:tool_hash},
        artifacts={str(detail):sha(detail)},REFCLK_destination_registers=len(targets),
        explicit_min_max_paths=sum(len(r['paths']) for r in results),corners=5,input_slews_ns=[.1,1.],
        maximum_sampled_external_setup_ns=max(r['maximum_required_setup_ns'] for r in results),
        maximum_sampled_external_hold_ns=max(r['maximum_required_hold_ns'] for r in results),
        reference_period_ns=40,reference_input_transition_ns=.1,clock_uncertainty_ns=.15,
        scope='REFCLK data-capture paths only, with existing conditional native load views and routed '
              'min/max RC. Two sampled external input slews; remaining original exceptions retained.',
        continuous_input_slew_range_qualified=False,asynchronous_enable_qualified=False,
        fine_domain_withdrawal_and_reset_timing_qualified=False,interface_contract_qualified=False,release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args(); run(a.output.resolve())
