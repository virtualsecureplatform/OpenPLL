"""Endpoint/output coverage audit of completed full native extraction."""
import json
import time
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import lease
from audit_completed_RC_1681 import completed
from native_RC_coverage import assess
from extract_keeper_flat_geometry_C import FLAT


def run():
    source = ROOT / 'build/signoff400/selected_corrected_full_RC_1671'
    receipt, record = completed(source)
    before = source / 'before.spice'
    geometry = source / (FLAT + '.res.ext')
    paths = [receipt, before, geometry, Path(__file__).resolve(),
             Path(__file__).with_name('native_RC_coverage.py'),
             Path(__file__).with_name('audit_keeper_native_R_contraction.py'),
             Path(__file__).with_name('audit_completed_RC_1681.py')]
    pins = {str(p): sha(p) for p in paths}
    out = ROOT / 'build/signoff400/selected_completed_RC_coverage_1687'
    out.mkdir(exist_ok=False)
    try:
        with lease(1, 8, time.clock_gettime(time.CLOCK_BOOTTIME) + 3600):
            result = assess(before.read_text(), geometry.read_text())
            for name, digest in pins.items():
                if sha(Path(name)) != digest:
                    raise ValueError('coverage audit input changed')
            save(out / 'assessment.json', dict(input_sha256=pins, **result,
                 RC_export_fixed=False, release_ready=False))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
