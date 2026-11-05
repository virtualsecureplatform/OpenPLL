"""Build a tiny DAC replay control using a pinned isolated Xyce build manifest.

Run inside the same tool container as the isolated Xyce build. No source patches.
"""
import argparse,json,subprocess
from pathlib import Path


def commands(manifest, source, output):
    value=json.loads(manifest.read_text())
    compile=value['commands'][0].copy()
    compile[compile.index('-c')+1]=str(source)
    compile[compile.index('-o')+1]=str(output/'probe.o')
    link=value['commands'][-1].copy()
    candidates=[i for i,p in enumerate(link) if p.endswith('/Xyce.C.o')]
    if len(candidates)!=1:raise ValueError('one main object required')
    link[candidates[0]]=str(output/'probe.o')
    link[link.index('-o')+1]=str(output/'probe')
    return [compile,link]


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--source',type=Path,default=Path(__file__).with_name('dac_replay_probe.cpp'))
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=a.source.resolve()
    cmds=commands(a.manifest.resolve(),source,out)
    (out/'commands.json').write_text(json.dumps(cmds,indent=2)+'\n')
    for i,command in enumerate(cmds):
        with (out/f'build_{i}.log').open('x') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
