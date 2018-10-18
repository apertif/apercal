import unittest
from apercal.modules.prepare import prepare
import matplotlib as mpl
mpl.use('TkAgg')

from os import path

here = path.dirname(__file__)


class TestPrepare(unittest.TestCase):

    def test_prepare(self):
        p = prepare(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '..')
        p.basedir = path.join(here, '../data/small')
        p.show(showall=False)
        p.go()


