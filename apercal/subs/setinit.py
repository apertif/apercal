def setinitdirs(self):
    """
    Creates the directory names for the subdirectories to make scripting easier
    """
    self.rawdir = self.basedir + str(self.beam).zfill(2) + '/' + self.rawsubdir
    self.crosscaldir = self.basedir + \
        str(self.beam).zfill(2) + '/' + self.crosscalsubdir
    self.selfcaldir = self.basedir + \
        str(self.beam).zfill(2) + '/' + self.selfcalsubdir
    self.linedir = self.basedir + \
        str(self.beam).zfill(2) + '/' + self.linesubdir
    self.contdir = self.basedir + \
        str(self.beam).zfill(2) + '/' + self.contsubdir
    self.poldir = self.basedir + str(self.beam).zfill(2) + '/' + self.polsubdir
    self.mosdir = self.basedir + self.mossubdir
    self.transferdir = self.basedir + \
        str(self.beam).zfill(2) + '/' + self.transfersubdir


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
