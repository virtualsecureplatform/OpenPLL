"""Require byte-identical actual-control reduction with the hardened reader."""
import argparse
import json
from pathlib import Path
import time
from common import save, sha
from compiled_charge import execute
from resources import lease


def run(controls, format_controls, output):
    controls, format_controls, out = (p.resolve() for p in (controls, format_controls, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    receipt, proof = controls/'assessment.json', format_controls/'assessment.json'
    old, checked = [json.loads(p.read_text()) for p in (receipt, proof)]
    if not old['streamed_sparse_accumulation_controls_pass'] or not checked['all_sparse_format_controls_pass']:
        raise ValueError('passing streamed and adversarial format controls required')
    binary = Path(checked['merger_binary'])
    cfg = controls/'merge.config.json'
    previous = json.loads(cfg.read_text())
    paths = [receipt, proof, binary, cfg, controls/'merged.bin', Path(__file__).resolve(),
             *[Path(path) for path in previous['inputs']]]
    pins = {str(p): sha(p) for p in paths}
    if pins[str(binary)] != checked['input_sha256'][str(binary)]:
        raise ValueError('hardened merger changed')
    for path in (cfg, controls/'merged.bin', *map(Path, previous['inputs'])):
        if pins[str(path)] != old['artifacts'][str(path)]:
            raise ValueError('actual sparse control input changed')
    with lease(2, 2, deadline):
        config = out/'config.json'
        save(config, dict(inputs=previous['inputs'], output=str(out/'merged.bin'), deadline_uptime=deadline))
        execute([binary, config], out/'native.log', deadline, 1)
        if sha(out/'merged.bin') != pins[str(controls/'merged.bin')]:
            raise ValueError('hardened merger changes controlled actual-operator reduction bytes')
        if any(sha(Path(p)) != digest for p, digest in pins.items()):
            raise ValueError('sparse merger upgrade input changed')
        save(out/'assessment.json', dict(input_sha256=pins,
             artifacts={str(p): sha(p) for p in (config, out/'merged.bin', out/'native.log')},
             merger_binary=str(binary), source_stream_controls=str(controls),
             source_format_controls=str(format_controls), actual_operator_merge_bytes_identical=True,
             actual_operators=old['operators'], physical_RC_qualified=False, release_qualified=False))
        print(json.dumps(dict(actual_operators=old['operators'], reduced_bytes_identical=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('controls', 'format-controls', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.controls, args.format_controls, args.output)
