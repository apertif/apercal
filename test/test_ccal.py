import unittest
from apercal.modules.ccal import ccal
from os import path

here = path.dirname(__file__)


class TestCcal(unittest.TestCase):
    def test_prepare(self):
        p = ccal(path.join(here, 'test.cfg'))
        p.show(showall=True)
        p.go()
