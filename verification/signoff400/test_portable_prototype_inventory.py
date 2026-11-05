import json
from pathlib import Path
import shutil
import tempfile
import unittest
from check_portable_prototype_inventory import check, digest


class PortableInventory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root/'original'
        self.package.mkdir()
        p = self.package
        (p/'design.v').write_text('module top; endmodule\n')
        (p/'requirements.json').write_text('{"prototype": true}\n')
        entry = dict(role='rtl', path='design.v', source='/absent/source/top.v', sha256=digest(p/'design.v'))
        (p/'inventory.json').write_text(json.dumps([entry]))
        candidate = {'id': 'synthetic-inventory-control'}
        manifest = dict(candidate=candidate, handoff_artifacts={'rtl': [dict(source=entry['source'], destination=entry['path'])]})
        (p/'manifest.input.json').write_text(json.dumps(manifest))
        receipt = dict(package_staged=True, qualification_prerequisites_passed=True,
                       candidate=candidate, profile_sha256=digest(p/'requirements.json'),
                       artifacts={str(f): digest(f) for f in p.iterdir()})
        (p/'assessment.json').write_text(json.dumps(receipt))
        self.trusted = digest(p/'assessment.json')
        self.moved = self.root/'relocated'
        shutil.move(p, self.moved)

    def test_relocation_never_opens_old_sources_or_promotes_release(self):
        result = check(self.moved, self.trusted)
        self.assertTrue(result['relocated_inventory_verified'])
        self.assertFalse(result['source_paths_opened'])
        self.assertFalse(result['release_ready'])
        self.assertFalse(result['clean_environment_replay_complete'])

    def test_changed_missing_and_extra_files_rejected(self):
        p = self.moved/'design.v'
        original = p.read_bytes()
        p.write_text('altered')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):check(self.moved, self.trusted)
        p.unlink()
        with self.assertRaisesRegex(ValueError, 'missing or unlisted'):check(self.moved, self.trusted)
        p.write_bytes(original)
        (self.moved/'extra').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'missing or unlisted'):check(self.moved, self.trusted)

    def test_links_and_changed_trust_root_rejected(self):
        with self.assertRaisesRegex(ValueError, 'trusted digest'):check(self.moved, '0'*64)
        p = self.moved/'design.v'
        p.unlink()
        p.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'symbolic link'):check(self.moved, self.trusted)


if __name__ == '__main__':unittest.main()
