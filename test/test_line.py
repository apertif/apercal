import unittest
import matplotlib as mpl
mpl.use('TkAgg')
from apercal.modules.line import line
from os import path

here = path.dirname(__file__)


class TestLine(unittest.TestCase):
    def test_line(self):
        p = line(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '..')
        p.basedir = path.join(here, '../data/small')
        p.show(showall=False)
        p.go()
