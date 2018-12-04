import unittest
import matplotlib as mpl
from apercal.modules.preflag import preflag
import casacore.tables as pt
from os import path
import logging

mpl.use('TkAgg')
logging.basicConfig(level=logging.DEBUG)
here = path.dirname(__file__)

data_prefix = path.join(here, '../data/small/00/raw/')


class TestPreflag(unittest.TestCase):
    def test_preflag(self):
        p = preflag()
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.prepare_bypass_alta = True
        p.prepare_target_beams = '00,04'
        p.go()

    def test_preflag_nosubdirs(self):
        p = preflag()
        p.subdirification = False
        p.fluxcal = path.join(data_prefix, '3C295.MS')
        p.polcal = path.join(data_prefix, '3C138.MS')
        p.target = path.join(data_prefix, 'NGC807.MS')
        p.prepare_bypass_alta = True
        p.prepare_target_beams = '00,04'
        p.go()
        for ms in [p.fluxcal, p.polcal, p.target]:
            query = "SELECT GNFALSE(FLAG) == 0 AS all_flagged, " + \
                    "GNTRUE(FLAG) == 0 AS all_unflagged FROM " + path.join(p.basedir, ms)
            query_result = pt.taql(query)
            assert(not(query_result[0]['all_flagged']))
            assert(not(query_result[0]['all_unflagged']))


if __name__ == "__main__":
    unittest.main()
