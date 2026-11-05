"""Serialize shared status updates; stage evidence remains immutable."""
import fcntl
import json
from common import ROOT,save


def update_root(field,value):
    path=ROOT/'build/timing400/prototype_001/status.json'
    with path.with_suffix('.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        record=json.loads(path.read_text());record[field]=value
        record['observed_utc']=value.get('observed_utc',record.get('observed_utc'))
        save(path,record)
