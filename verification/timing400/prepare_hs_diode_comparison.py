#!/usr/bin/env python3
"""Prepare the missing observed HS diode geometry comparison from pinned decks.

Change only the device's effective area/perimeter in checked HD diagnostic
templates. Preserve the model, PVT, bias, numerical settings and reference
geometry convention. Fresh execution and independent assessment are required.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
from run_dco_qualification import ROOT,sha,save

sys.path.insert(0,str(ROOT/'scripts'))
from sky130_diode_translation_probe import MODEL_SHA256


def main():
    began=time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline=began+43200
    base=ROOT/'build/timing400/release_001'
    out=base/'hs_diode_geometry_comparison_001'
    inventory=base/'current_diode_geometry_inventory_001'
    report=json.loads((inventory/'assessment.json').read_text())
    assert report['existing_translator_scope_guard_correctly_rejects_hs']
    geometries=json.loads((inventory/'geometries.json').read_text())
    hs=next(r for r in geometries if '_hs__' in r['master'])
    assert hs['instances']==724 and not hs['accepted_by_existing_fixed_geometry_translator']
    area=Decimal(hs['effective_area_um2'])
    perimeter=Decimal(hs['effective_perimeter_um'])
    assert (area,perimeter)==(Decimal('.6417'),Decimal('3.24'))
    cached=ROOT/'build/modern_25mhz/diode_pdk_cache/sky130A/libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice'
    current=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.ref/sky130_fd_pr/spice/sky130_fd_pr__diode_pw2nd_05v5.model.spice')
    assert sha(cached)==sha(current)==MODEL_SHA256
    xyce=Path('/opt/xyce/bin/Xyce')
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    ngspice=ROOT/'build/tools/ngspice47/install/bin/ngspice'
    ng_receipt=ROOT/'build/tools/ngspice47/binary_provenance.json'
    assert sha(ngspice)==json.loads(ng_receipt.read_text())['binary_sha256']
    legacy=ROOT/'build/modern_25mhz/diode_qualification_ng47.json'
    checked=json.loads(legacy.read_text())
    assert checked['model_equivalence_screen_passed']
    templates={
        'electrical':ROOT/'build/modern_25mhz/diode_translation_grid_ng47_v2',
        'noise':ROOT/'build/modern_25mhz/diode_noise_grid_ng47_v1'}
    source_paths=[Path(__file__).resolve(),inventory/'assessment.json',inventory/'geometries.json',cached,
        ngspice,ng_receipt,image,legacy,*[p/'summary.json' for p in templates.values()]]
    source_pins={str(p):sha(p) for p in source_paths}
    out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),budget_started_boottime=began,
        absolute_deadline_uptime=deadline,total_budget_s=43200,includes_preparation_admission_and_assessment=True,
        automatic_identical_retry=False))
    jobs=[]
    source_decks={}
    output_decks={}
    for kind in ['electrical','noise']:
        for corner in ['tt','ff','ss','sf','fs']:
            for temperature in [-40,27,125]:
                biases=[None] if kind=='electrical' else [0,.81,1.62,1.8,1.98]
                for bias in biases:
                    folder=f'{corner}_{temperature}C'+('' if kind=='electrical' else f'_{bias:g}V')
                    labels=['dc',*[f'ac_{v:g}V' for v in [0,.81,1.62,1.8,1.98]],'tran'] if kind=='electrical' else ['noise']
                    for label in labels:
                        for simulator in ['ngspice','xyce']:
                            filename=f'{simulator}_{label}.cir' if kind=='electrical' else simulator+'.cir'
                            source=templates[kind]/folder/filename
                            assert str(source) in checked['evidence_sha256']
                            assert sha(source)==checked['evidence_sha256'][str(source)],source
                            original=source.read_text()
                            before='area=.4347 '+('perim=2.64' if simulator=='ngspice' else 'pj=2.64')
                            after=f'area={area} '+(f'perim={perimeter}' if simulator=='ngspice' else f'pj={perimeter}')
                            assert original.count(before)==1,(source,before)
                            changed=original.replace(before,after)
                            assert changed.replace(after,before)==original
                            target=out/kind/folder/filename
                            target.parent.mkdir(parents=True,exist_ok=True)
                            target.write_text(changed)
                            source_decks[str(source)]=sha(source)
                            output_decks[str(target)]=sha(target)
                            jobs.append(dict(kind=kind,corner=corner,temperature_c=temperature,bias_v=bias,
                                label=label,simulator=simulator,deck=str(target),output_stem=str(target.with_suffix('')),
                                log=str(target.with_suffix('.log')),only_effective_geometry_changed=True))
    assert len(jobs)==360 and len(source_decks)==len(output_decks)==360
    for path,digest in source_pins.items():
        assert sha(Path(path))==digest,path
    save(out/'plan.json',dict(input_sha256=source_pins,source_template_sha256=source_decks,
        prepared_deck_sha256=output_decks,container_inputs_sha256={str(xyce):sha(xyce),str(current):sha(current)},
        image=str(image),ngspice=str(ngspice),jobs=jobs,native_analyses=360,
        effective_geometry=dict(area_um2=str(area),perimeter_um=str(perimeter)),
        extracted_magic_arguments=dict(area=hs['extracted_area_argument'],perimeter=hs['extracted_perimeter_argument']),
        observed_instances_requiring_comparison=724,corners=['tt','ff','ss','sf','fs'],temperatures_c=[-40,27,125],
        biases_v=[0,.81,1.62,1.8,1.98],reference_geometry='explicit',reference_simulator='ngspice47',
        golden_simulator='upstream Xyce',model_adopted=False,geometry_qualified=False,release_qualified=False,scope=__doc__))
    print('Prepared360 sequential native analyses for observed HS geometry, under one12h queue/preparation/execution/assessment budget; none launched.')


if __name__=='__main__':
    main()
