from glob import glob
from os import path
from typing import List, Tuple, Any

class BaseModule:
    subdirification = None
    basedir = None
    rawsubdir = None
    fluxcal = None
    polcal = None
    target = None

    def get_fluxcal_path(self):
        if self.subdirification:
            return path.join(self.basedir, '00', self.rawsubdir, self.fluxcal)
        else:
            return self.fluxcal

    def get_polcal_path(self):
        if self.subdirification:
            return path.join(self.basedir, '00', self.rawsubdir, self.polcal)
        else:
            return self.polcal

    def get_datasets(self, beams=None):
        # type: (List[int]) -> List[Tuple[Any, Any]]
        if self.subdirification:
            if beams:
                datasets = [path.join(self.basedir, str(b).zfill(2), self.rawsubdir, self.target) for b in beams]
            else:
                datasets = glob(path.join(self.basedir, '[0-9][0-9]', self.rawsubdir, self.target))
            beams = [vis.split('/')[-3] for vis in datasets]
            return zip(datasets, beams)
        else:
            # TODO: (gijs) is it okay to just always set this to 0?
            return [(self.target, '00')]

    def get_datasets_beams(self, beams):
        if self.subdirification:

            beams = [vis.split('/')[-3] for vis in datasets]
            return zip(datasets, beams)
        else:
            return [(self.target, '00')]
