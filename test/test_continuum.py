import unittest
from os import path
import matplotlib as mpl
mpl.use('TkAgg')

from apercal.modules.continuum import continuum

here = path.dirname(__file__)


class TestTransfer(unittest.TestCase):

    def test_continuum(self):
        p = continuum(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../')
        p.basedir = path.join(here, '../data/small/')
        p.fluxcal = '3C295.MS'
        p.polcal = '3C138.MS'
        p.target = 'NGC807.MS'
        #p.show(showall=False)
        p.go()
