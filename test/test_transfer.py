import unittest
from os import path
import matplotlib as mpl

mpl.use('TkAgg')

from apercal.modules.transfer import transfer
import logging

logging.basicConfig(level=logging.INFO)

here = path.dirname(__file__)


class TestTransfer(unittest.TestCase):

    def test_transfer(self):
        p = transfer(path.join(here, 'test.cfg'))
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.go()


if __name__ == "__main__":
    unittest.main()
