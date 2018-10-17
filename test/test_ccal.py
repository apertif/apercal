import unittest
from apercal.modules.ccal import ccal
from os import path

here = path.dirname(__file__)


class TestCcal(unittest.TestCase):
    def test_ccal(self):
        p = ccal(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../apercal')
        p.basedir = path.join(here, 'tmp')
        p.show(showall=True)
        p.go()
