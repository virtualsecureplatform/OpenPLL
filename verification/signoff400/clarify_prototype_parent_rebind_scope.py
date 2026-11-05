"""Correct inherited template scope flags without repeating native reconstruction."""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify


def run(source,output):
    receipt=source/'assessment.json';a=json.loads(receipt.read_text())
    verify(a['input_sha256']);verify(a['artifacts'])
    if not all(a.get(k) for k in (
        'selected_digital_GDS_rebound_with_identical_external_interface',
        'analog_macro_GDS_unchanged','parent_database_geometry_and_connections_retained',
        'old_abstract_obstructions_retained_and_new_actual_GDS_missing_geometry_added',
        'main_rail_database_connectivity_pass')):
        raise ValueError('completed checked parent rebind required')
    log=(source/'augment.log').read_text()
    if '[ERROR' in log or not all(f'All shapes on net {n} are connected.' in log for n in ('VPWR','VGND')):
        raise ValueError('native PG result incomplete')
    output.mkdir(parents=True,exist_ok=False)
    artifacts={}
    for name,digest in a['artifacts'].items():
        old=Path(name)
        if old.parent!=source:raise ValueError('unexpected external artifact')
        new=output/old.name;new.write_bytes(old.read_bytes())
        if sha(new)!=digest:raise ValueError('native artifact copy changed')
        artifacts[str(new)]=digest
    inputs=dict(a['input_sha256']);inputs.update(a['artifacts'])
    inputs.update({str(receipt):sha(receipt),str(Path(__file__).resolve()):sha(Path(__file__).resolve()),
                   str(Path(__file__).with_name('common_v3.py')):sha(Path(__file__).with_name('common_v3.py'))})
    verify(inputs)
    a.update(input_sha256=inputs,artifacts=artifacts,
        macro_interiors_unchanged=False,macro_GDS_and_abstract_pin_shapes_unchanged=False,
        placement_and_pg_only=False,
        inherited_template_scope_flags_corrected=True,native_artifacts_copied_without_rerun=True,
        scope='Digital child GDS selection changed; external pin interface and parent placement/connections retained. Analog child GDS unchanged. New parent routing and all physical checks required.',
        release_ready=False)
    save(output/'assessment.json',a)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
