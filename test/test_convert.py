import unittest
from apercal.modules.convert import convert
from os import path

here = path.dirname(__file__)


class TestConvert(unittest.TestCase):
    def test_prepare(self):
        p = convert(path.join(here, 'test.cfg'))
        p.show(showall=True)
        p.go()
