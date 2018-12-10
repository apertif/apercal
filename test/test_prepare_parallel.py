import unittest
import matplotlib as mpl
from apercal.modules.prepare_parallel import prepare_parallel
from os import path
import logging

mpl.use('TkAgg')
logging.basicConfig(level=logging.DEBUG)
here = path.dirname(__file__)


class TestPrepare(unittest.TestCase):
    def test_prepare_parallel(self):
        p = prepare_parallel()
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.prepare_bypass_alta = True
        p.prepare_target_beams = '00, 04, 17'
        p.go(first_level_threads=2)


if __name__ == "__main__":
    unittest.main()
