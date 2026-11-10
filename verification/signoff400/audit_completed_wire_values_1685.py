"""Completed-only independent wire-value gate for the full corrected export."""
import json
import time
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import lease
from audit_completed_RC_1681 import completed
from native_wire_values import assess
from extract_keeper_flat_geometry_C import FLAT


def run():
    base = ROOT / 'build/signoff400'
    geometry = base / 'selected_corrected_full_RC_1671'
    converted = base / 'selected_completed_RC_reexport_1680'
    gr, original = completed(geometry)
    cr, conversion = completed(converted)
    if conversion['input_sha256'].get(str(gr)) != sha(gr):
        raise ValueError('conversion does not bind completed geometry')
    source = geometry / (FLAT + '.res.ext')
    spice = converted / 'after.spice'
    paths = [gr, cr, source, spice, Path(__file__).resolve(),
             Path(__file__).with_name('native_wire_values.py'),
             Path(__file__).with_name('audit_keeper_native_R_contraction.py'),
             Path(__file__).with_name('audit_completed_RC_1681.py')]
    pins = {str(p): sha(p) for p in paths}
    out = base / 'selected_completed_wire_values_1685'
    out.mkdir(exist_ok=False)
    try:
        with lease(1, 8, time.clock_gettime(time.CLOCK_BOOTTIME) + 3600):
            result = assess(source.read_text(), spice.read_text())
            for name, digest in pins.items():
                if sha(Path(name)) != digest:
                    raise ValueError('wire audit input changed')
            save(out / 'assessment.json', dict(input_sha256=pins, **result,
                 conductor_coverage_verified=False, RC_export_fixed=False,
                 release_ready=False))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
