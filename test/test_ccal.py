import unittest
import matplotlib as mpl

mpl.use('TkAgg')
from apercal.modules.ccal import ccal
from os import path
import logging

logging.basicConfig(level=logging.INFO)

here = path.abspath(path.dirname(__file__))


class TestCcal(unittest.TestCase):
    def test_ccal(self):
        p = ccal()
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.go()


if __name__ == "__main__":
    unittest.main()
