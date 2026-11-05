"""Review retained native MOS-style extraction without rerunning the antenna job."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re
import shlex
import time
from common_v3 import save,sha,verify
from resources import lease

def run(source,geometry,output):
    manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    recipe=source/'antenna.tcl'
    if 'extract style ngspice(orig)' not in recipe.read_text():
        raise ValueError('explicit MOS-only native extraction style required')
    control=next(Path(p) for p in m['input_sha256'] if p.endswith('/antenna_diode_style_comparison_001/assessment.json'))
    c=json.loads(control.read_text());verify(c['input_sha256']);verify(c['artifacts'])
    if not c['orig_known_controls_match_required_mos_only_reference']:
        raise ValueError('native diode-style controls required')
    original=geometry/'assessment.json';g=json.loads(original.read_text());verify(g['artifacts'])
    if not g['all_checked_mask_regions_preserved']:
        raise ValueError('independent source mask preservation required')
    log=source/'magic.log';ext=source/'OpenPLL_Prototype_Antenna_Flat.ext';flat=source/'flat.gds'
    text=log.read_text();counts=re.findall(r'^ANTENNA_FEEDBACK_COUNT=(\d+)\s*$',text,re.M)
    if len(counts)!=1 or re.search(r'invalid command name|couldn.t open|Cannot open|syntax error|unknown command',text,re.I):
        raise ValueError('native antenna job incomplete')
    area=Fraction(0);mos=diodes=uses=0
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+43200):
        for line in ext.open():
            f=shlex.split(line)
            if f[:1]==['use']:uses+=1
            if f[:2]==['device','mosfet']:
                if not any(s in f[2] for s in ('nfet','pfet')):
                    raise ValueError('unreviewed MOS model')
                length,width=Fraction(f[7]),Fraction(f[8])
                if min(length,width)<=0:raise ValueError('invalid MOS dimensions')
                area+=length*width/40000;mos+=1
            if f[:2]==['device','ndiode']:diodes+=1
    if uses or mos<10000 or str(area)!=g['source_poly_diff_channel_area_um2']:
        raise ValueError('native MOS gate inventory does not match independent source polygons')
    pins=dict(m['input_sha256']);pins.update({str(p):sha(p) for p in (manifest,original,log,ext,flat,Path(__file__).resolve())})
    # Compare the actual source and flat GDS geometries separately; the prior
    # default-style flatten check does not prove this second flatten's masks.
    output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (flat,ext,log)},
         native_flat_layout_antenna_run_completed=True,extraction_style='ngspice(orig)',diode_style_controls_pass=True,
         residual_hierarchy_uses=uses,extracted_flat_MOS_primitives=mos,explicit_diodes=diodes,
         raw_gate_area_um2_at_1_over_200_grid=str(area),native_antenna_feedback_entries=int(counts[0]),
         original_failed_postprocessor_preserved=True,native_job_rerun=False,
         independent_GDS_gate_area_and_conductor_geometry_checked=False,
         parent_antenna_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','geometry','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.source.resolve(),args.geometry.resolve(),args.output.resolve())
