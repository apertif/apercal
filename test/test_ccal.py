import unittest
import matplotlib as mpl
from apercal.modules.ccal import ccal
from os import path
import logging

mpl.use('TkAgg')
logging.basicConfig(level=logging.DEBUG)
here = path.dirname(__file__)


class TestCcal(unittest.TestCase):
    def test_ccal(self):
        p = ccal()
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.prepare_target_beams = '00,04'
        p.go()


if __name__ == "__main__":
    unittest.main()
