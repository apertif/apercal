import unittest
from apercal.modules.preflag import preflag
from os import path

here = path.dirname(__file__)


class TestPreflag(unittest.TestCase):
    def test_prepare(self):
        p = preflag(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '..')
        p.basedir = path.join(here, '../data/small')
        p.show(showall=False)
        p.go()
