import unittest
from apercal.modules.convert import convert
from os import path
import matplotlib as mpl
mpl.use('TkAgg')

here = path.dirname(__file__)


class TestConvert(unittest.TestCase):
    def test_prepare(self):
        p = convert(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '..')
        p.basedir = path.join(here, '../data/small')
        p.show(showall=False)
        p.go()
