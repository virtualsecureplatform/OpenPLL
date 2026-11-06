"""Resolve full-model identities through hash-pinned parent native manifests."""
import json
from pathlib import Path
from common_v3 import verify


def resolve(inputs):
    all_inputs={};manifests={};models={};pending=[dict(inputs)]
    while pending:
        current=pending.pop()
        for path,digest in current.items():
            if path in all_inputs and all_inputs[path]!=digest:raise ValueError('conflicting native lineage input digests')
            all_inputs[path]=digest
            if path.endswith('/model.spice'):models[path]=digest
            if not path.endswith('/manifest.json') or path in manifests:continue
            if len(manifests)>=64:raise ValueError('native lineage manifest limit exceeded')
            verify({path:digest});manifests[path]=digest
            parent=json.loads(Path(path).read_text())
            if not isinstance(parent.get('input_sha256'),dict):raise ValueError('native parent manifest lacks input hashes')
            pending.append(parent['input_sha256'])
    verify(all_inputs)
    if len(models)!=1:raise ValueError('unique full physical model required across native lineage')
    return models,manifests
