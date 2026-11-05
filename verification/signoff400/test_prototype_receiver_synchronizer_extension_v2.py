import unittest
from test_prototype_receiver_synchronizer_extension import fixture
from extend_prototype_receiver_synchronizers_v2 import extend


def current_fixture():
    text,metadata,bound,module,physical=fixture()
    # Renumber the event nets as on the current route; aliases remain stable.
    def update(value):
        if isinstance(value,dict):return {k:update(v) for k,v in value.items()}
        if isinstance(value,list):return [update(v) for v in value]
        if isinstance(value,str):return value.replace('3071','3065').replace('3074','3068')
        return {3071:3065,3074:3068}.get(value,value)
    values=[update(v) for v in (text,metadata,bound,module)]
    values.append({'mapping':physical['chains'][0]['cells']})
    values.append([dict(bit=3065,aliases=[dict(name='core.bbpd_dn_event_toggle')]),dict(bit=3068,aliases=[dict(name='core.bbpd_up_event_toggle')])])
    return values


class CurrentSynchronizerExtension(unittest.TestCase):
    def test_current_aliases_determine_bits_and_actual_load_nodes(self):
        text,mapping=extend(*current_fixture())
        self.assertIn('Xfirstsync_DN SYNC_CLK_DN wire_dn',text)
        self.assertEqual({r['data_bit'] for r in mapping['first_synchronizers']},{3065,3068})
        self.assertNotIn('n_3071',text)

    def test_ambiguous_event_aliases_rejected(self):
        values=current_fixture();values[-1][0]['aliases'].append(dict(name='core.bbpd_up_event_toggle'))
        with self.assertRaisesRegex(ValueError,'unambiguous event'):extend(*values)

if __name__=='__main__':unittest.main()
