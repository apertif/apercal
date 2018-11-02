import unittest
import matplotlib as mpl
mpl.use('TkAgg')
from apercal.modules.preflag import preflag
from os import path
from apercal.libs import lib


lib.setup_logger('debug')

here = path.dirname(__file__)


class TestPreflag(unittest.TestCase):
    def test_preflag(self):
        p = preflag(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../')
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        p.show(showall=False)
        p.go()

if __name__ == "__main__":
        unittest.main()
        p.go()
