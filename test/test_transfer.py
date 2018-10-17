import unittest
from os import path

from apercal.modules.transfer import transfer

here = path.dirname(__file__)


class TestTransfer(unittest.TestCase):

    def test_prepare(self):
        p = transfer(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '..')
        p.basedir = path.join(here, '../data/small')
        p.show(showall=False)
        p.go()
