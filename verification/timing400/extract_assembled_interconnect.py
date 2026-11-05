#!/usr/bin/env python3
"""Extract parent intermacro wire RC from the exact DRC/LVS-passing assembly.

Macro internal RC and pin capacitance are excluded. The three PDK RC views
are extraction views, not a demonstrated electrical enclosure or timing pass.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

from check_compact_clock_tree import verify
from check_compact_mapping import LIB, OPENROAD
from run_dco_qualification import sha, save


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('layout-audit', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    audit = args.layout_audit.resolve()
    receipt = json.loads(audit.read_text())
    # This audit has no generated artifacts; explicitly check its direct inputs.
    for path, digest in receipt['input_sha256'].items():
        assert sha(Path(path)) == digest, path
    assert receipt['assembled_magic_drc_passed'] and receipt['assembled_lvs_passed']
    database = Path(receipt['routed_database'])
    assert sha(database) == receipt['routed_database_sha256']
    models = {view: LIB.parents[3]/f'libs.tech/librelane/rules.openrcx.sky130A.{view}.magic'
              for view in ('nom', 'min', 'max')}
    paths = [Path(__file__).resolve(), Path(OPENROAD), database, audit,
             Path(__file__).with_name('check_compact_clock_tree.py'),
             Path(__file__).with_name('check_compact_mapping.py'),
             Path(__file__).with_name('run_dco_qualification.py'), *models.values()]
    pins = {str(p.resolve()): sha(p) for p in paths}
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for view, model in models.items():
        task = out/f'extract_{view}.tcl'
        task.write_text(f'''read_db {database}
set_thread_count 2
set block [ord::get_db_block]
set f [open {out}/connections_{view}.tsv w]
foreach net [$block getNets] {{
 if {{[$net getSigType] in {{POWER GROUND}}}} {{continue}}
 foreach term [$net getITerms] {{
  puts $f [join [list [$net getName] I [[$term getInst] getName] [[$term getMTerm] getName] [$term getIoType]] "\\t"]
 }}
 foreach term [$net getBTerms] {{
  puts $f [join [list [$net getName] P - [$term getName] [$term getIoType]] "\\t"]
 }}
}}
close $f
define_process_corner -ext_model_index 0 RCX_{view.upper()}
extract_parasitics -ext_model_file {model} -corner 0
write_spef {out}/route.{view}.spef
exit
''')
        with (out/f'extract_{view}.log').open('x') as log:
            subprocess.run([OPENROAD, '-no_init', '-exit', str(task)], stdout=log,
                           stderr=subprocess.STDOUT, check=True,
                           timeout=max(1, 43200-(time.monotonic()-started)))
        assert 'Error:' not in (out/f'extract_{view}.log').read_text()
    assert len({(out/f'connections_{view}.tsv').read_bytes() for view in models}) == 1
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path
    elapsed = time.monotonic()-started
    assert elapsed < 43200
    save(out/'assessment.json', dict(input_sha256=pins,
        artifacts={str(p): sha(p) for p in out.iterdir() if p.is_file()},
        routed_database=str(database), rc_views=list(models),
        parent_wire_rc_extracted=True, macro_internal_rc_included=False,
        pin_capacitance_included=False, electrical_enclosure_qualified=False,
        physical_timing_qualified=False, release_qualified=False, adopted=False,
        elapsed_seconds=elapsed, check_budget_seconds=43200, scope=__doc__))
    print(json.dumps(dict(parent_wire_rc_extracted=True, elapsed_seconds=elapsed)))


if __name__ == '__main__':
    main()
