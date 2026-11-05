#!/usr/bin/env python3
"""Cache exact installed OpenROAD RCX source to audit fill/geometry coverage.

Git blob SHA1 is checked against the previously pinned complete source tree.
This is source evidence only; extraction support requires a physical control.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from run_dco_qualification import ROOT,sha,save


def main():
    tree=ROOT/'build/timing400/release_001/fixed_signal_wire_source_audit_001/tree.json'
    data=json.loads(tree.read_text());assert not data['truncated']
    commit='dcf36133a369abc8f3c5e5738cd4d82e4903c0e0'
    entries=[e for e in data['tree'] if e['path'].startswith('src/rcx/') and e['type']=='blob' and e['path'].endswith(('.cpp','.h'))]
    assert len(entries)==71
    out=ROOT/'build/timing400/release_001/openrcx_fill_source_audit_001';out.mkdir(exist_ok=False)
    def fetch(entry):
        url=f'https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD/{commit}/{entry["path"]}'
        with urllib.request.urlopen(url,timeout=30) as response:content=response.read()
        blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest();assert blob==entry['sha']
        target=out/entry['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
        lines=content.decode().splitlines()
        hits=[dict(line=i,text=line) for i,line in enumerate(lines,1) if re.search(r'getFills|dbFill|[Ff]ill|[Oo]bstruction',line)]
        return dict(path=entry['path'],url=url,git_blob_sha1=blob,sha256=sha(target),size=len(content),fill_or_obstruction_mentions=hits)
    with ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(fetch,entries))
    save(out/'sources.json',dict(commit=commit,observed_utc=datetime.now(timezone.utc).isoformat(),files=records))
    save(out/'assessment.json',dict(input_sha256={str(tree):sha(tree),str(Path(__file__).resolve()):sha(Path(__file__).resolve())},
        artifacts={str(out/r['path']):r['sha256'] for r in records}|{str(out/'sources.json'):sha(out/'sources.json')},
        source_files=len(records),all_git_blobs_verified=True,fill_support_not_inferred=True,
        electrical_extraction_qualified=False,release_qualified=False,scope=__doc__))
    for r in records:
        for hit in r['fill_or_obstruction_mentions']:print(r['path'],hit['line'],hit['text'])

if __name__=='__main__':main()
