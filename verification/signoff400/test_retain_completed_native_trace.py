import tempfile,unittest
from pathlib import Path
from retain_completed_native_trace import retain
class ClosedTraceRetention(unittest.TestCase):
    def test_exact_binary_content_is_published_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'local';target=root/'shared';data=bytes(range(256))*10000;source.write_bytes(data)
            result=retain(source,target,native_completed=True)
            self.assertEqual(target.read_bytes(),data);self.assertEqual(result['bytes'],len(data));self.assertTrue(result['closed_native_trace_copy_verified']);self.assertFalse((root/'shared.copying').exists())
    def test_partial_source_and_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'local';target=root/'shared';source.write_bytes(b'trace')
            with self.assertRaises(ValueError):retain(source,target,native_completed=False)
            target.write_bytes(b'preserved')
            with self.assertRaises(ValueError):retain(source,target,native_completed=True)
            self.assertEqual(target.read_bytes(),b'preserved')
if __name__=='__main__':unittest.main()
