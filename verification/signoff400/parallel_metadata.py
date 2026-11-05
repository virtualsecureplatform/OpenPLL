"""Build the byte-equivalent bounded parallel native metadata parser."""
from pathlib import Path
import shutil
import subprocess
from common import ROOT,save,sha
from compiled_charge import execute

SOURCE=ROOT/'tools/charge_compiler/metadata_parallel.cpp'


def compile_metadata(trace,output,build_directory,deadline,threads=8):
    if not 1<=threads<=32:raise ValueError('bounded metadata worker count required')
    directory=Path(build_directory);directory.mkdir(parents=True,exist_ok=False)
    binary=directory/'metadata_parallel';compiler=Path(shutil.which('g++')).resolve()
    command=[compiler,'-std=c++20','-O3','-pthread','-Wall','-Wextra','-Wpedantic',
             '-fno-fast-math','-ffp-contract=off',SOURCE,'-o',binary]
    execute(command,directory/'build.log',deadline,4)
    dependencies=(SOURCE,SOURCE.with_name('main_stream_ledger.cpp'),SOURCE.with_name('json.hpp'),
                  compiler,Path(__file__).resolve())
    save(directory/'build.json',dict(command=list(map(str,command)),
        compiler_version=subprocess.check_output([compiler,'--version'],text=True),
        input_sha256={str(p):sha(p) for p in dependencies},artifacts={str(binary.resolve()):sha(binary)},
        threads=threads,metadata_only=True))
    execute([binary,Path(trace),Path(output),deadline,threads,'parallel'],
            Path(output).with_name('metadata.log'),deadline,4)
    return binary
