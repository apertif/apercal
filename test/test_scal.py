import unittest
import matplotlib as mpl
mpl.use('TkAgg')
from apercal.modules.scal import scal
from os import path

here = path.dirname(__file__)


class TestScal(unittest.TestCase):
    def test_scal(self):
        p = scal(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../')
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        #p.show(showall=False)

if __name__ == "__main__":
        unittest.main()
        p.go()
