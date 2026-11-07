"""Reject an unwired two-terminal fixture without altering the source database."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from extract_prototype_parent_spef_v2 import OPENROAD


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts']);recipe=source/'min.tcl'
    if r['input_sha256'].get(str(recipe))!=sha(recipe):raise ValueError('native extraction recipe differs')
    output.mkdir(parents=True,exist_ok=False);text=recipe.read_text().replace(str(source),str(output))
    first,rest=text.split('\n',1);script=output/'negative.tcl';script.write_text(first+'\nset block [ord::get_db_block]\n[$block findBTerm VPB] connect [$block findNet VNB]\n'+rest)
    pins={str(p):sha(p)for p in [receipt,recipe,script,Path(__file__).resolve(),OPENROAD]};deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+120;os.sched_setaffinity(0,{24,25})
    try:
        with lease(2,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/'native.log',deadline,8)
    except RuntimeError:
        if 'multi-terminal signal missing detailed wire'not in (output/'native.log').read_text():raise
    else:raise ValueError('unwired multi-terminal fixture accepted')
    verify(pins);verify(r['input_sha256']);verify(r['artifacts']);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'native.log'):sha(output/'native.log')},unwired_multi_terminal_net_rejected=True,fixture_changed_only_in_memory=True,source_artifacts_unchanged=True,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.source.resolve(),a.output.resolve())
