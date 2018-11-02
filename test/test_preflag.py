import unittest
import matplotlib as mpl

mpl.use('TkAgg')
from apercal.modules.preflag import preflag
from os import path
import logging

logging.basicConfig(level=logging.INFO)
here = path.dirname(__file__)

data_prefix = path.join(here, '../data/small/00/raw/')


class TestPreflag(unittest.TestCase):
    def test_preflag(self):
        p = preflag()
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.go()

    def test_preflag_nosubdirs(self):
        p = preflag()
        p.subdirification = False
        p.fluxcal = path.join(data_prefix, '3C295.MS')
        p.polcal = path.join(data_prefix, '3C138.MS')
        p.target = path.join(data_prefix, 'NGC807.MS')
        p.go()


if __name__ == "__main__":
    unittest.main()
