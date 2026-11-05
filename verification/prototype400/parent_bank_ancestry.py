"""Recover every stage-local bank plan through pinned route ancestry."""
import json
from pathlib import Path
from common import sha, verify


def existing_extra_banks(receipt):
    plans, receipts, rows, visited = [], [], [], set()
    path=Path(receipt).resolve()
    while True:
        if path in visited or len(visited)>=64:
            raise ValueError('cyclic or excessive parent route ancestry')
        visited.add(path);receipts.append(path)
        proof=json.loads(path.read_text())
        verify(proof['input_sha256']);verify(proof['artifacts'])
        if proof.get('extra_placement_plan'):
            plan=Path(proof['extra_placement_plan']).resolve()
            if proof['artifacts'].get(str(plan))!=sha(plan):
                raise ValueError('extra bank plan is not a pinned artifact')
            if plan in plans:raise ValueError('repeated stage-local bank plan')
            plans.append(plan);rows.extend(json.loads(plan.read_text()))
        sources=[Path(p).resolve() for p in proof['input_sha256'] if Path(p).name=='route.odb']
        if not sources:break
        if len(sources)!=1:raise ValueError('ambiguous parent route ancestry')
        parent=sources[0].parent/'assessment.json'
        if proof['input_sha256'].get(str(parent))!=sha(parent):
            raise ValueError('source route assessment is not pinned')
        path=parent
    sites=[(r['x_nm'],r['y_nm']) for r in rows]
    if len(sites)!=len(set(sites)):raise ValueError('duplicate ancestor bank sites')
    return plans,receipts,rows
