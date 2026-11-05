"""Linear model-edit ledgers and directive-only dependency tokenization."""
import hashlib,shlex,time
from pathlib import Path


def model_closure(first,deadline):
    pending,seen=[first],set()
    while pending:
        path=Path(pending.pop()).resolve()
        if path in seen:continue
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('model closure deadline')
        if not path.is_file():raise ValueError('missing model dependency: '+str(path))
        seen.add(path)
        for line in path.read_text().splitlines():
            text=line.strip()
            if not text or text[0]!='.':continue
            directive=text.split(None,1)[0].lower()
            if directive not in ('.include','.inc','.lib'):continue
            tokens=shlex.split(text)
            if directive=='.lib' and len(tokens)==2:continue
            if len(tokens)<2:raise ValueError('model include path required')
            pending.append(path.parent/tokens[1])
    return sorted(seen)


def line_edits(before,after):
    left,right=before.splitlines(keepends=True),after.splitlines(keepends=True)
    if len(left)!=len(right):raise ValueError('line-preserving model edits required')
    edits=[dict(line=i+1,before=a.decode('utf8'),after=b.decode('utf8')) for i,(a,b) in enumerate(zip(left,right,strict=True)) if a!=b]
    return dict(format='OPENPLL_MODEL_LINE_EDITS_1',source_sha256=hashlib.sha256(before).hexdigest(),result_sha256=hashlib.sha256(after).hexdigest(),line_count=len(left),edits=edits)


def apply_line_edits(before,ledger):
    if ledger['format']!='OPENPLL_MODEL_LINE_EDITS_1' or hashlib.sha256(before).hexdigest()!=ledger['source_sha256']:raise ValueError('model edit source/format mismatch')
    lines=before.splitlines(keepends=True)
    if len(lines)!=ledger['line_count']:raise ValueError('model edit line count')
    previous=0
    for edit in ledger['edits']:
        i=edit['line']
        if type(i) is not int or not previous<i<=len(lines) or lines[i-1]!=edit['before'].encode('utf8'):raise ValueError('ordered exact model edit preimage required')
        lines[i-1]=edit['after'].encode('utf8');previous=i
    result=b''.join(lines)
    if hashlib.sha256(result).hexdigest()!=ledger['result_sha256']:raise ValueError('model edit result mismatch')
    return result
