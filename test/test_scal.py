import unittest
from apercal.modules.scal import scal
from os import path

here = path.dirname(__file__)


class TestScal(unittest.TestCase):
    def test_prepare(self):
        p = scal(path.join(here, 'test.cfg'))
        p.show(showall=True)
        p.go()
