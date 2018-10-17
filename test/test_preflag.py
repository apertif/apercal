import unittest
from apercal.modules.preflag import preflag
from os import path

here = path.dirname(__file__)


class TestPreflag(unittest.TestCase):
    def test_prepare(self):
        p = preflag(path.join(here, 'test.cfg'))
        p.apercaldir = path.join(here, '../apercal')
        p.show(showall=True)
        p.manualflag()
        p.aoflagger_bandpass()
        preflag.aoflagger_flag()
