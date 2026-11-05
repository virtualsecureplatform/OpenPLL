"""Require byte-pinned C reference equivalence before using a different R domain."""
import json
from pathlib import Path

def domain_bridge_pins(n, domain, expected_domain_hash):
    domain=Path(domain);d=json.loads(domain.read_text())
    bridge_pins={str(domain):expected_domain_hash}
    if n['input_sha256'].get(str(domain))!=bridge_pins[str(domain)]:
        # Reuse C only across a proven pre-R-equivalent diagnostic domain.
        refs=[p for p in n['input_sha256'] if p.endswith('/domain/assessment.json')]
        if len(refs)!=1 or d['input_sha256'].get(refs[0])!=n['input_sha256'][refs[0]]:
            raise ValueError('corrected R does not pin the C reference domain')
        if not d.get('native_rc_export_completed') or not d.get('pre_resistance_capacitance_preserved'):
            raise ValueError('corrected native pre-R equivalence required')
        ref=Path(refs[0]);reference=json.loads(ref.read_text())
        bridge_pins[str(ref)]=n['input_sha256'][str(ref)]
        for suffix in ('pre_resistance.spice','Prototype400_FilledCapacitanceView.ext'):
            p=ref.parent/'trace'/suffix
            digest=n['input_sha256'].get(str(p))
            if not digest or d['input_sha256'].get(str(p))!=digest:
                raise ValueError('C/R reference card lineage differs')
            bridge_pins[str(p)]=digest
            p=domain.parent/'trace'/suffix
            bridge_pins[str(p)]=d['artifacts'][str(p)]
        sets=[{h for p,h in report['input_sha256'].items() if p.endswith('.gds')} for report in (n,d,reference)]
        if len(sets[0])!=1 or any(h!=sets[0] for h in sets[1:]):
            raise ValueError('C and corrected R do not pin one identical GDS digest')
        for report in (n,d):
            for p,h in report['input_sha256'].items():
                if p.endswith('.gds') or p.endswith('/sky130A.tech'):
                    if p in bridge_pins and bridge_pins[p]!=h:raise ValueError('conflicting shared input digest')
                    bridge_pins[p]=h
        techs=[h for p,h in n['input_sha256'].items() if p.endswith('/sky130A.tech')]
        if len(techs)!=1 or {h for p,h in d['input_sha256'].items() if p.endswith('/sky130A.tech')}!=set(techs):
            raise ValueError('C/R technology differs')
    return bridge_pins
