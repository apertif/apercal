import unittest
from os import path

from apercal.modules.mosaic import mosaic

here = path.dirname(__file__)


class TestMosaic(unittest.TestCase):

    def test_prepare(self):
        p = mosaic(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../apercal')
        p.show(showall=True)
        p.go()
