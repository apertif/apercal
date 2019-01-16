import unittest
import matplotlib as mpl
mpl.use('TkAgg')
from os import path
from apercal.modules.mosaic import mosaic
import logging


logging.basicConfig(level=logging.DEBUG)
here = path.dirname(__file__)


class TestMosaic(unittest.TestCase):
    def test_mosaic(self):
        p = mosaic()
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.go()


if __name__ == "__main__":
    unittest.main()
