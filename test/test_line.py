import unittest
from apercal.modules.line import line
from os import path

here = path.dirname(__file__)


class TestLine(unittest.TestCase):
    def test_prepare(self):
        p = line(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../apercal')
        p.show(showall=True)
        p.go()
