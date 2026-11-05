"""Build isolated baseline and one-derivative diagnostic ngspice binaries."""
import argparse,json,os,shutil,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute


def build(out,deadline):
    original=ROOT/'build/tools/ngspice47/tmpsndfibtf';proof=ROOT/'build/signoff400/startup_timing_CV_body_derivative_controls_001/assessment.json';a=json.loads(proof.read_text());inputs=ROOT/'build/tools/ngspice47/build_inputs.json';old=json.loads(inputs.read_text());source=out/'source';tools=out/'tools';tools.mkdir();packages=out/'packages';packages.mkdir();pins={str(p):sha(p) for p in (proof,inputs,Path(__file__).resolve(),Path('/usr/bin/gcc').resolve(),Path('/usr/bin/make').resolve())};relative=Path('src/spicelib/devices/bsim4v5/b4v5ld.c')
    if sha(original/relative)!=a['input_sha256'][str(original/relative)] or not a['native_T4_expression_matches_independent_derivative']:raise ValueError('audited derivative/source required')
    save(out/'status.json',dict(state='copying_isolated_reference_source',release_qualified=False));shutil.copytree(original,source);source_pins={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()};save(out/'source_manifest_before_generation.json',source_pins)
    # Exact package versions and hashes are the retained reference build inputs.
    for package,version in (('bison','2:3.8.2+dfsg-1ubuntu0.24.04.1'),('flex','2.6.4-8.2build1')):
        # apt-get download uses cwd; a small subprocess wrapper changes only cwd.
        command=['python3','-c','import os,sys; os.chdir(sys.argv[1]); os.execvp(sys.argv[2],sys.argv[2:])',str(packages),'apt-get','download',package+'='+version];execute(command,packages/(package+'.log'),deadline,4)
        matches=list(packages.glob(package+'_*.deb'))
        if len(matches)!=1:raise ValueError('unique exact dependency package')
        p=matches[0];expected=[h for n,h in old['input_sha256'].items() if Path(n).name.startswith(package+'_')]
        if len(expected)!=1 or sha(p)!=expected[0]:raise ValueError('historical build dependency bytes differ')
        pins[str(p)]=sha(p);execute(['dpkg-deb','-x',p,tools],packages/(package+'_unpack.log'),deadline,4)
    os.environ.update(PATH=str(tools/'usr/bin')+os.pathsep+os.environ['PATH'],BISON_PKGDATADIR=str(tools/'usr/share/bison'),OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    for p in (tools/'usr/bin/bison',tools/'usr/bin/flex'):pins[str(p)]=sha(p)
    def command(args,log):
        execute(['python3','-c','import os,sys; os.chdir(sys.argv[1]); os.execvp(sys.argv[2],sys.argv[2:])',str(source),*map(str,args)],out/log,deadline,4)
    save(out/'input_manifest.json',dict(input_sha256=pins,source_manifest_sha256=sha(out/'source_manifest_before_generation.json'),diagnostic_reference_only=True,release_qualified=False));save(out/'status.json',dict(state='configuring_isolated_reference_build',release_qualified=False));command(['sh','autogen.sh'],'autogen.log');command(['./configure','--prefix='+str(out/'install'),'--with-x=no','--with-readline=no','--enable-xspice','--disable-cider','--disable-klu','--disable-osdi'],'configure.log')
    save(out/'status.json',dict(state='building_isolated_unmodified_reference',release_qualified=False));command(['make','-j2'],'baseline_make.log');command(['make','install'],'baseline_install.log');baseline=out/'ngspice_baseline';shutil.copy2(out/'install/bin/ngspice',baseline);save(out/'baseline_receipt.json',dict(binary=str(baseline),sha256=sha(baseline),source_manifest_sha256=sha(out/'source_manifest_before_generation.json'),diagnostic_only=True))
    target=source/relative;text=target.read_text();start=text.index('/* Charge-Thickness capMod (CTM) begins */');prefix,section=text[:start],text[start:];before='dVdseffCV_dVb = dT0_dVb * (1.0 - T5) + T5 * dT1_dVb;';after='dVdseffCV_dVb = dT0_dVb * (T4 - T5) + T5 * dT1_dVb;'
    if section.count(before)!=1:raise ValueError('unique CTM derivative intervention')
    changed=prefix+section.replace(before,after)
    if changed.replace(after,before,1)!=text:raise ValueError('only exact derivative substitution permitted')
    save(out/'derivative_edit.json',dict(path=str(relative),before=before,after=after,original_sha256=sha(target)));(out/'b4v5ld.baseline.c').write_text(text);target.write_text(changed)
    # Verify every original source file; configure-generated files are additional.
    for relative_name,h in source_pins.items():
        if relative_name==str(relative):continue
        if sha(source/relative_name)!=h:raise ValueError('unexpected retained source mutation: '+relative_name)
    save(out/'status.json',dict(state='building_CTM_derivative_diagnostic_reference',release_qualified=False));command(['make','-j2'],'diagnostic_make.log');command(['make','install'],'diagnostic_install.log');diagnostic=out/'ngspice_CTM_derivative';shutil.copy2(out/'install/bin/ngspice',diagnostic)
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('build inputs changed')
    artifacts=[baseline,diagnostic,out/'baseline_receipt.json',out/'derivative_edit.json',out/'b4v5ld.baseline.c',target,out/'source_manifest_before_generation.json',*[out/n for n in ('autogen.log','configure.log','baseline_make.log','baseline_install.log','diagnostic_make.log','diagnostic_install.log')]]
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},baseline_binary=str(baseline),diagnostic_binary=str(diagnostic),native_build_workers=2,only_retained_source_edit='CTM VdseffCV body derivative 1.0 -> T4',stock_reference_unchanged=True,diagnostic_reference_only=True,simulator_response_comparison_complete=False,MOS_backend_compatibility_qualified=False,release_qualified=False));save(out/'status.json',dict(state='isolated_CV_reference_binaries_built',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=2,memory_GiB=4,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(2,4,deadline):build(out,deadline)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':main()
