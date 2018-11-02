import unittest
import matplotlib as mpl
mpl.use('TkAgg')
from apercal.modules.convert import convert
from os import path

here = path.dirname(__file__)


class TestConvert(unittest.TestCase):
    def test_convert(self):
        p = convert(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../')
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        #p.show(showall=False)
        p.go()

if __name__ == "__main__":
        unittest.main()
