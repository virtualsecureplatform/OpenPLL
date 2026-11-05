#!/usr/bin/env python3
"""Install a pinned HS overlay; never write to the baseline PDK."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import re
import subprocess
import sys

from run import DEFAULT_PDK, REPO

ROOT = REPO / 'build/timing450'
SOURCES = {
    'sky130_fd_sc_hs': ('https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hs.git', '1d051f49bfe4e2fe9108d702a8bc2e9c081005a4'),
    'open_pdks': ('https://github.com/RTimothyEdwards/open_pdks.git', 'aa3fc215a80d32437b8cca1cb3fdee819d18c4c9'),
    'skywater-pdk': ('https://github.com/google/skywater-pdk.git', '7198cf647113f56041e02abf3eb623692820c5e1'),
}
MAGIC_BIN = '/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin'


def adapt_views(destination):
    """Repair pinned upstream view defects without changing geometry."""
    originals = ROOT / 'hs_original_views'
    originals.mkdir(exist_ok=True)
    metadata = ROOT / 'hs_view_adaptations.json'
    fixes = json.loads(metadata.read_text()) if metadata.exists() else {}
    verilog = destination / 'verilog/sky130_fd_sc_hs.v'
    saved = originals / verilog.name
    if not saved.exists():
        shutil.copy2(verilog, saved)
    original = saved.read_text()
    updated, count = re.subn(r'(?m)^([ \t]*wire)[ \t]+([A-Z][A-Z0-9_]*)[ \t]+([a-z]\w*)[ \t]*(;)',
                            r'\1 \3 \4', original)
    fixes['malformed_wire_declarations'] = count
    # Malformed latch helper declarations contain an extra identifier.
    updated, count = re.subn(r'(?m)^([ \t]*wire)[ \t]+(?:buf_Q|gate)[ \t]+(\w+)[ \t]*(;)',
                            r'\1 \2 \3', updated)
    fixes['malformed_latch_declarations'] = count
    # Two cells repeat the same comma-separated temporary declaration.
    updated, count = re.subn(r'(?m)^([ \t]*wire)[ \t]+(csi_opt_\d+),[ \t]*((?:nor|and)1_out)[ \t]*(;)',
                            r'\1 \3 \4', updated)
    fixes['duplicate_temporary_declarations'] = count
    headers = re.findall(r'module (sky130_fd_sc_hs__\w+)\s*\((.*?)\);', updated, flags=re.S)
    powered_bases = {name for name, _ in headers}
    for name, ports in headers:
        if 'VPWR' not in ports or 'VGND' not in ports:
            powered_bases.discard(name)
    fixed_supplies = 0
    def connect_supplies(match):
        nonlocal fixed_supplies
        body = match[0]
        if '.VPWR(' in body or body.split()[0] not in powered_bases:
            return body
        fixed_supplies += 1
        prefix, connections = body.split('(', 1)
        connections = connections[:-2].rstrip()
        return prefix + '(' + connections + (',\n' if connections.strip() else '\n') + '        .VPWR(VPWR),\n        .VGND(VGND)\n    );'
    # Pinned base models expose supply ports in both preprocessor branches,
    # but non-power-pin wrappers omit connections to their declared supplies.
    updated, count = re.subn(r'sky130_fd_sc_hs__\w+ base \(.*?\);', connect_supplies, updated, flags=re.S)
    fixes['base_supply_connections_checked'] = count
    fixes['base_supply_connections_added'] = fixed_supplies
    verilog.write_text(updated)
    spice = destination / 'spice/sky130_fd_sc_hs.spice'
    original = spice.read_text()
    # Upstream conb uses an undefined three-terminal "short" primitive.
    # Its GDS contains two-terminal poly resistors; retain supplied dimensions
    # and use the installed PDK's physical resistor model and terminal count.
    updated, count = re.subn(r'(?m)^(X[01])\s+(\S+)\s+(\S+)\s+VNB\s+short\s+w=(\S+)\s+l=(\S+)\s*$',
                            r'\1 \2 \3 sky130_fd_pr__res_generic_po w=\4 l=\5', original)
    if count:
        if count != 2:
            raise RuntimeError(f'Expected exactly two HS tie resistors, found {count}')
        shutil.copy2(spice, originals / spice.name)
        spice.write_text(updated)
    fixes['tie_resistor_primitives'] = count or fixes.get('tie_resistor_primitives', 0)
    fixes['original_sha256'] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in originals.iterdir() if f.is_file()}
    (ROOT / 'hs_view_adaptations.json').write_text(json.dumps(fixes, indent=2) + '\n')
    print(json.dumps(fixes))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patch-views', action='store_true', help='Adapt and hash an already installed private HS library')
    args = parser.parse_args()
    if args.patch_views:
        destination = ROOT / 'pdk/sky130A/libs.ref/sky130_fd_sc_hs'
        if destination.is_symlink():
            raise RuntimeError('HS views must be private')
        adapt_views(destination)
        record_library(destination)
        return
    staging = ROOT / 'pdk_src'
    staging.mkdir(parents=True, exist_ok=True)
    for name, (url, revision) in SOURCES.items():
        directory = staging / name
        if not directory.exists():
            subprocess.run(['git', 'clone', '--no-checkout', url, str(directory)], check=True)
        if not (directory / '.git').exists():
            marker = directory / '.pinned_revision'
            if marker.exists() and marker.read_text().strip() == revision:
                continue
            raise RuntimeError(f'{directory} exists without its own Git repository or verified archive marker')
        actual = subprocess.check_output(['git', '-C', str(directory), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != revision:
            subprocess.run(['git', '-C', str(directory), 'fetch', 'origin', revision], check=True)
            subprocess.run(['git', '-C', str(directory), 'checkout', '--detach', revision], check=True)
        elif name == 'skywater-pdk':
            subprocess.run(['git', '-C', str(directory), 'checkout', revision, '--', 'scripts/python-skywater-pdk'], check=True)
        else:
            subprocess.run(['git', '-C', str(directory), 'checkout', revision, '--', '.'], check=True)
    dependencies = ROOT / 'python_deps'
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--target', str(dependencies),
                    'dataclasses-json==0.5.14', 'marshmallow==3.26.2', 'typing-inspect==0.9.0',
                    'mypy-extensions==1.1.0', 'packaging==26.3', 'typing-extensions==4.16.0'], check=True)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(dependencies) + ':' + str(staging / 'skywater-pdk/scripts/python-skywater-pdk')
    # Use a relative path: upstream collect() excludes any path containing
    # "timing". The module entry point also runs Python-version-sensitive
    # doctests; call the official generator's main function directly.
    subprocess.run([sys.executable, '-c', 'from skywater_pdk import liberty; raise SystemExit(liberty.main())',
                    'sky130_fd_sc_hs', 'tt_025C_1v80', 'ss_100C_1v60', 'ff_n40C_1v95'],
                   cwd=staging, env=env, check=True)
    overlay = ROOT / 'pdk/sky130A'
    baseline = Path(DEFAULT_PDK) / 'sky130A'
    overlay.mkdir(parents=True, exist_ok=True)
    if not (overlay / 'libs.tech').exists():
        shutil.copytree(baseline / 'libs.tech', overlay / 'libs.tech')
    (overlay / 'libs.ref').mkdir(exist_ok=True)
    for source in (baseline / 'libs.ref').iterdir():
        target = overlay / 'libs.ref' / source.name
        if not target.exists():
            target.symlink_to(source, target_is_directory=source.is_dir())
    destination = overlay / 'libs.ref/sky130_fd_sc_hs'
    if destination.is_symlink():
        raise RuntimeError('HS destination must be private, not a baseline PDK symlink')
    env['PATH'] = MAGIC_BIN + ':' + env['PATH']
    env['PDK_ROOT'] = str(overlay.parent)
    foundry = staging / 'open_pdks'
    options = [
        '-std_format', '-timestamp', '1790526654',
        '-source', str(staging / 'sky130_fd_sc_hs'), '-target', str(overlay),
        '-techlef', 'tech/*.tlef',
        '-spice', 'cells/*/*.spice', 'compile-only', 'sort=../common/sort_pdkfiles.py',
        '-cdl', 'cells/*/*.cdl', 'ignore=topography', 'compile-only', 'sort=../common/sort_pdkfiles.py',
        '-lef', 'cells/*/*.lef', 'annotate', 'compile-only', 'exclude=*.magic.lef', 'lefopts=-toplayer', 'sort=../common/sort_pdkfiles.py',
        '-doc', 'cells/*/*.pdf', '-lib', 'timing/*.lib.part*', 'collate', '-lib', 'timing/*.lib',
        '-gds', 'cells/*/*.gds', 'compile-only', 'options=custom/scripts/gds_import_sc.tcl', 'sort=../common/sort_pdkfiles.py',
        '-verilog', 'models/*/*.v', 'exclude=*.*.v', 'compile-only', 'rename=primitives', 'filter=custom/scripts/inc_verilog.py', 'sort=../common/sort_pdkfiles.py',
        '-verilog', 'cells/*/*.blackbox.v', 'compile-only', 'exclude=primitives.v', 'rename=sky130_fd_sc_hs__blackbox.v', 'sort=../common/sort_pdkfiles.py',
        '-verilog', 'cells/*/*.blackbox.pp.v', 'compile-only', 'exclude=primitives.v,sky130_fd_sc_hs__blackbox.v', 'rename=sky130_fd_sc_hs__blackbox_pp.v', 'sort=../common/sort_pdkfiles.py',
        '-verilog', 'cells/*/*.*.v', 'remove', '-verilog', 'cells/*/*.v', 'compile-only',
        'exclude=*.*.v,primitives.v,sky130_fd_sc_hs__blackbox.v,sky130_fd_sc_hs__blackbox_pp.v',
        'filter=custom/scripts/inc_verilog.py', 'sort=../common/sort_pdkfiles.py',
        '-library', 'digital', 'sky130_fd_sc_hs',
    ]
    subprocess.run([sys.executable, '../common/foundry_install.py', *options], cwd=foundry / 'sky130', env=env, check=True)
    # OpenROAD names its LEF libraries after file stems. A technology LEF
    # named identically to the cell LEF collides; keep a byte-identical alias
    # so that technology sites and physical masters are both loaded.
    shutil.copyfile(destination / 'techlef/sky130_fd_sc_hs.tlef',
                    destination / 'techlef/sky130_fd_sc_hs__nom.tlef')
    adapt_views(destination)
    record_library(destination)


def record_library(destination):
    required = [destination / directory / filename for directory, filename in [
        ('techlef', 'sky130_fd_sc_hs.tlef'), ('techlef', 'sky130_fd_sc_hs__nom.tlef'), ('lef', 'sky130_fd_sc_hs.lef'),
        ('gds', 'sky130_fd_sc_hs.gds'), ('spice', 'sky130_fd_sc_hs.spice'),
        ('cdl', 'sky130_fd_sc_hs.cdl'), ('verilog', 'sky130_fd_sc_hs.v'),
        *[('lib', 'sky130_fd_sc_hs__' + c + '.lib') for c in ['tt_025C_1v80', 'ss_100C_1v60', 'ff_n40C_1v95']],
    ]]
    manifest = {'baseline_pdk': DEFAULT_PDK, 'sources': SOURCES,
                'sha256': {str(f.relative_to(REPO)): hashlib.sha256(f.read_bytes()).hexdigest() for f in required}}
    (ROOT / 'hs_library_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
