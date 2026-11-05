import unittest
from capture_selected_native_runtime import dependencies


class RuntimeDependenciesTests(unittest.TestCase):
    def test_include_closure_keeps_inactive_sections_and_resolves_relative_paths(self):
        text='''* ignored
.lib tt
.include "../cells/tt.spice"
.endl tt
.lib ff
.inc '../cells/ff.spice'
.lib "extra.spice" slow
.endl ff
'''
        self.assertEqual(dependencies(text,'/opt/pdk/model/main.lib'),[
            '/opt/pdk/cells/tt.spice','/opt/pdk/cells/ff.spice','/opt/pdk/model/extra.spice'])

    def test_dynamic_include_is_not_silently_omitted(self):
        with self.assertRaises(ValueError):dependencies('.include "$MODEL_FILE"','/opt/pdk/main.lib')


if __name__=='__main__':unittest.main()
