import unittest
import matplotlib as mpl
from apercal.modules.convert import convert
from os import path
import logging

mpl.use('TkAgg')
logging.basicConfig(level=logging.DEBUG)
here = path.dirname(__file__)


class TestConvert(unittest.TestCase):
    def test_convert(self):
        p = convert()
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.go()


if __name__ == "__main__":
    unittest.main()
