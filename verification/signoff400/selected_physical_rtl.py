"""Select exact RTL bytes pinned by the selected filled-layout input receipt."""
import json
from pathlib import Path
from common_v3 import ROOT,sha,verify

BINDING=ROOT/'rtl/selected400/sources.json'


def source_pins(binding=BINDING,root=ROOT):
    binding=Path(binding);root=Path(root);b=json.loads(binding.read_text())
    if b['schema_version']!=1 or not b['files'] or not b['original_source_sha256']:raise ValueError('physical RTL binding required')
    receipt=root/b['physical_receipt']['path'];gds=root/b['physical_gds']['path']
    verify({str(receipt):b['physical_receipt']['sha256'],str(gds):b['physical_gds']['sha256']})
    r=json.loads(receipt.read_text())
    if r.get('artifacts',{}).get(str(gds))!=b['physical_gds']['sha256']:raise ValueError('GDS not bound by physical layout receipt')
    # Verify source provenance directly, without compiling the archived originals
    # alongside their identical portable copies (which would duplicate modules).
    originals=b['original_source_sha256']
    if any(r['input_sha256'].get(p)!=digest for p,digest in originals.items()):raise ValueError('RTL not bound by physical layout receipt')
    if len({Path(p).name for p in originals})!=len(originals):raise ValueError('ambiguous original RTL names')
    by_name={Path(p).name:d for p,d in originals.items()}
    files={str(root/name):digest for name,digest in b['files'].items()}
    if len(files)!=len(originals) or any(by_name.get(Path(p).name)!=d for p,d in files.items()):raise ValueError('portable RTL differs from physical candidate')
    verify(originals);verify(files)
    # Preserve layout identity alongside source identity; callers compile only .v.
    return dict(files,**{str(binding):sha(binding),str(receipt):sha(receipt),str(gds):b['physical_gds']['sha256'],str(Path(__file__).resolve()):sha(Path(__file__).resolve())})
