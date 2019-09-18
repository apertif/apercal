import os


def setinitdirs(self):
    """
    Creates the directory names for the subdirectories to make scripting easier
    """
    self.rawdir = os.path.join(self.basedir, self.beam, self.rawsubdir)
    self.crosscaldir = os.path.join(
        self.basedir, self.beam, self.crosscalsubdir)
    self.selfcaldir = os.path.join(self.basedir, self.beam, self.selfcalsubdir)
    self.linedir = os.path.join(self.basedir, self.beam, self.linesubdir)
    self.contdir = os.path.join(self.basedir, self.beam, self.contsubdir)
    self.poldir = os.path.join(self.basedir, self.beam, self.polsubdir)
    self.mosdir = os.path.join(self.basedir, self.mossubdir)
    self.transferdir = os.path.join(
        self.basedir, self.beam, self.transfersubdir)


def setdatasetnamestomiriad(self):
    """
    Renames the dataset names to .mir from .MS for crosscal and following modules
    """
    if self.fluxcal.endswith('.MS'):
        self.fluxcal = self.fluxcal.rstrip('MS') + 'mir'
    if self.polcal.endswith('.MS'):
        self.polcal = self.polcal.rstrip('MS') + 'mir'
    if self.target.endswith('.MS'):
        self.target = self.target.rstrip('MS') + 'mir'
