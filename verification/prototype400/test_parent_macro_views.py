"""The selected frame, power database and route must form one pinned chain."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import sha
from parent_macro_views import parent_views, MASTERS


class ParentMacroViews(unittest.TestCase):
    def prepare(self,root):
        frame,power,route=(root/n for n in ('frame','power','route'))
        for d in (frame,power,route):d.mkdir()
        source=root/'source.v';source.write_text('current source')
        (frame/'floorplan.odb').write_text('frame');(power/'power.odb').write_text('power')
        views={};pins={str(source):sha(source)}
        for name,master in MASTERS.items():
            folder=root/name/'signoff';folder.mkdir(parents=True)
            views[name]=dict(master=master)
            for kind in ('gds','lef'):
                path=folder/('view.'+kind);path.write_text(name+kind)
                views[name][kind]=str(path);pins[str(path)]=sha(path)
        def save(folder,value):
            (folder/'assessment.json').write_text(json.dumps(value))
        save(frame,dict(assembly_frame_pass=True,macro_sources=views,input_sha256=pins,artifacts={}))
        save(power,dict(main_rail_database_connectivity_pass=True,
            input_sha256={str(frame/n):sha(frame/n) for n in ('assessment.json','floorplan.odb')},artifacts={}))
        save(route,dict(router_drc_violations=0,exact_macro_bindings_preserved=True,
            input_sha256={str(power/n):sha(power/n) for n in ('assessment.json','power.odb')},artifacts={}))
        return frame,power,route,source

    def test_selected_views_follow_the_exact_parent_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            frame,power,route,source=self.prepare(Path(temp))
            with patch('parent_macro_views.source_pins',return_value={str(source):sha(source)}):
                result=parent_views(route,power,frame)
            self.assertEqual(result['names'],list(MASTERS.values()))
            self.assertEqual(len(result['sources']),3)

    def test_stale_sources_and_unrelated_power_or_frame_are_rejected(self):
        for fault in ('source','frame','power'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);frame,power,route,source=self.prepare(root)
                if fault=='source':source.write_text('changed source')
                else:
                    original=frame if fault=='frame' else power
                    other=root/'unrelated';other.mkdir()
                    for p in original.iterdir():
                        (other/p.name).write_bytes(p.read_bytes())
                    if fault=='frame':frame=other
                    else:power=other
                with patch('parent_macro_views.source_pins',return_value={str(source):sha(source)}):
                    with self.assertRaises(ValueError):
                        parent_views(route,power,frame)


if __name__=='__main__':
    unittest.main()
