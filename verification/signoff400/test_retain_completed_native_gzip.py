import gzip
import hashlib
import tempfile
import unittest
from unittest.mock import patch
from runtime_common import sha
from pathlib import Path
from retain_completed_native_gzip import retain


class NativeArchive(unittest.TestCase):
    def test_exact_binary_roundtrip_and_source_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            source, archive = Path(directory) / 'trace', Path(directory) / 'trace.gz'
            data = (b'{"native":1}\n' * 1000) + bytes(range(256))
            source.write_bytes(data)
            result = retain(source, archive, native_completed=True)
            self.assertEqual(gzip.decompress(archive.read_bytes()), data)
            self.assertEqual(source.read_bytes(), data)
            self.assertEqual(result['uncompressed_sha256'], hashlib.sha256(data).hexdigest())
            self.assertLess(result['compressed_bytes'], len(data))
            self.assertFalse(archive.with_name('trace.gz.compressing').exists())

    def test_incomplete_or_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source, archive = Path(directory) / 'trace', Path(directory) / 'trace.gz'
            source.write_bytes(b'closed')
            with self.assertRaises(ValueError):
                retain(source, archive, native_completed=False)
            self.assertFalse(archive.exists())
            archive.write_bytes(b'retained')
            with self.assertRaises(ValueError):
                retain(source, archive, native_completed=True)
            self.assertEqual(archive.read_bytes(), b'retained')

    def test_preexisting_partial_archive_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source, archive = Path(directory) / 'trace', Path(directory) / 'trace.gz'
            source.write_bytes(b'closed')
            partial = archive.with_name('trace.gz.compressing')
            partial.write_bytes(b'prior attempt')
            with self.assertRaises(FileExistsError):
                retain(source, archive, native_completed=True)
            self.assertEqual(partial.read_bytes(), b'prior attempt')
            self.assertFalse(archive.exists())

    def test_source_change_prevents_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            source, archive = Path(directory) / 'trace', Path(directory) / 'trace.gz'
            source.write_bytes(b'closed')
            def changed_hash(path):
                source.write_bytes(b'changed')
                return sha(path)
            with patch('retain_completed_native_gzip.sha', side_effect=changed_hash):
                with self.assertRaises(ValueError):
                    retain(source, archive, native_completed=True)
            self.assertFalse(archive.exists())
            self.assertEqual(source.read_bytes(), b'changed')

    def test_corrupt_archive_prevents_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            source, archive = Path(directory) / 'trace', Path(directory) / 'trace.gz'
            source.write_bytes(b'closed')
            def corrupt_archive(path):
                archive.with_name('trace.gz.compressing').write_bytes(b'invalid gzip')
                return sha(path)
            with patch('retain_completed_native_gzip.sha', side_effect=corrupt_archive):
                with self.assertRaises(gzip.BadGzipFile):
                    retain(source, archive, native_completed=True)
            self.assertFalse(archive.exists())
            self.assertEqual(source.read_bytes(), b'closed')

    def test_concurrent_destination_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            source, archive = Path(directory) / 'trace', Path(directory) / 'trace.gz'
            source.write_bytes(b'closed')
            def raced_hash(path):
                if Path(path).name.endswith('.compressing'):
                    archive.write_bytes(b'other retained result')
                return sha(path)
            with patch('retain_completed_native_gzip.sha', side_effect=raced_hash):
                with self.assertRaises(FileExistsError):
                    retain(source, archive, native_completed=True)
            self.assertEqual(archive.read_bytes(), b'other retained result')


if __name__ == '__main__':
    unittest.main()
