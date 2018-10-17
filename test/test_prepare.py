import unittest
from apercal.modules.prepare import prepare

from os import path

here = path.dirname(__file__)


class TestPrepare(unittest.TestCase):

    def test_prepare(self):
        p = prepare(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../apercal')
        p.show(showall=True)
        p.go()


