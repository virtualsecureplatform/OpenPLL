"""Compare stock and isolated coupling-import change on native on/off controls."""
import argparse
import json
import os
import time
from pathlib import Path
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute


def run(engine, output):
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {28})
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 7200
        while not (engine / 'assessment.json').exists():
            status = engine / 'status.json'
            if status.exists() and json.loads(status.read_text())['state'] == 'stopped_without_qualification':
                raise RuntimeError('isolated engine build stopped')
            owner = json.loads((engine / 'owner.json').read_text())
            if identity(owner['pid']) != owner['birth']:
                raise RuntimeError('engine build owner missing')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('build observation deadline')
            save(output / 'status.json', dict(state='waiting_for_isolated_engine', release_ready=False))
            time.sleep(10)
        a = json.loads((engine / 'assessment.json').read_text())
        verify(a['artifacts'])
        modified = Path(a['installed_executable'])
        stock = Path('/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic')
        fixture = ROOT / 'tools/magic_rcx/coupling_grounding_probe.tcl'
        tech = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/magic/sky130A.tech')
        pins = {str(p): sha(p) for p in [engine / 'assessment.json', stock, modified, fixture, tech, Path(__file__).resolve()]}
        save(output / 'inputs.json', dict(input_sha256=pins, CPU=28, memory_GiB=4, release_ready=False))
        results = []
        with lease(1, 4, deadline):
            for label, executable in [('stock', stock), ('modified', modified)]:
                for coupling in (0, 1):
                    target = output / (label + '_coupling' + str(coupling))
                    target.mkdir()
                    rc = target / 'minimal.magicrc'
                    rc.write_text('tech load {' + str(tech) + '}\n')
                    os.environ['OPENPLL_TEST_COUPLING'] = str(coupling)
                    os.chdir(target)
                    save(output / 'status.json', dict(state='native_' + target.name, release_ready=False))
                    execute([str(executable), '-dnull', '-noconsole', '-rcfile', str(rc), str(fixture)], target / 'native.log', min(deadline, time.clock_gettime(time.CLOCK_BOOTTIME) + 300), 4)
                    before = (target / 'before.spice').read_bytes()
                    after = (target / 'after.spice').read_bytes()
                    same = before == after
                    expected_same = label == 'modified' or coupling == 0
                    if same != expected_same:
                        raise ValueError('unexpected coupling export result: ' + target.name)
                    results.append(dict(engine=label, coupling=coupling, before_after_byte_identical=same, expected_result=True))
            verify(pins)
        artifacts = {str(p): sha(p) for p in output.glob('*/*') if p.is_file()}
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts, cases=results, stock_duplication_reproduced=True, modified_controls_pass=True, native_resistor_network_geometry_qualified=False, RC_simplification_qualified=False, PLL_model_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='native_explicit_coupling_controls_complete', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ['engine', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.engine.resolve(), a.output.resolve())
