import unittest
from os import path
import matplotlib as mpl
mpl.use('TkAgg')

from apercal.modules.mosaic import mosaic

here = path.dirname(__file__)


class TestMosaic(unittest.TestCase):

    def test_prepare(self):
        p = mosaic(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '..')
        p.basedir = path.join(here, '../data/small')
        p.show(showall=False)
        p.go()
