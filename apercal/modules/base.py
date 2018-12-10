from glob import glob
from os import path, curdir
from apercal.libs.lib import show
# from typing import List, Tuple, Any # Leave disabled until we install typing on happili
from abc import abstractproperty, ABCMeta


class BaseModule:

    __metaclass__ = ABCMeta

    @abstractproperty
    def module_name(self):
        pass

    fluxcal = None
    polcal = None
    target = None
    basedir = None
    beam = None
    rawsubdir = None
    crosscalsubdir = None
    selfcalsubdir = None
    linesubdir = None
    contsubdir = None
    polsubdir = None
    mossubdir = None
    transfersubdir = None
    subdirification = True
    NBEAMS = 40

    def get_rawsubdir_path(self, beam='00'):
        if self.subdirification:
            return path.join(self.basedir, beam, self.rawsubdir)
        else:
            return curdir

    def get_fluxcal_path(self, beam='00'):
        if self.subdirification:
            return path.join(self.basedir, beam, self.rawsubdir, self.fluxcal)
        else:
            return self.fluxcal

    def get_polcal_path(self, beam='00'):
        if self.subdirification:
            return path.join(self.basedir, beam, self.rawsubdir, self.polcal)
        else:
            return self.polcal

    def get_target_path(self, beam='00'):
        if self.subdirification:
            return path.join(self.basedir, beam, self.rawsubdir, self.target)
        else:
            return self.target

    def get_datasets(self, beams=None):
        # type: (List[int]) -> List[Tuple[Any, Any]]
        if self.subdirification:
            if beams:
                datasets = [self.get_target_path(str(b).zfill(2)) for b in beams]
            else:
                datasets = sorted(glob(self.get_target_path('[0-9][0-9]')))
            beams = [vis.split('/')[-3] for vis in datasets]
            return zip(datasets, beams)
        else:
            # TODO: (gijs) is it okay to just always set this to 0?
            return [(self.target, '00')]

    def show(self, showall=False):
        show(self, self.module_name, showall)
