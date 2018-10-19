import ConfigParser
import glob
import logging

import os
import sys

from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.libs import lib


class ccal:
    """
    Crosscal class to handle applying the calibrator gains and prepare the dataset for self-calibration.
    """

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

    crosscaldir = None
    crosscal_bandpass = None
    crosscal_delay = None
    crosscal_polarisation = None
    crosscal_transfer_to_target = None

    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('CROSSCAL')
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        self.default = config # Save the loaded config file as defaults for later usage
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

    #############################################################
    ##### Function to execute the cross-calibration process #####
    #############################################################

    def go(self):
        """
        Executes the full cross calibration process in the following order.
        bandpass
        polarisation
        tranfer_to_target
        """
        self.logger.info("########## Starting CROSS CALIBRATION ##########")
        self.bandpass()
        self.polarisation()
        self.transfer_to_target()
        self.logger.info("########## CROSS CALIBRATION done ##########")

    ###########################################################################################
    ##### Functions to compensate for the fringe stopping. Hopefully not needed for long. #####
    ###########################################################################################

    def bandpass(self):
        """
        Calibrates the bandpass for the flux calibrator using mfcal in MIRIAD.
        """
        if self.crosscal_bandpass:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.crosscaldir)
            self.logger.info('### Bandpass calibration on the flux calibrator data started ###')
            mfcal = lib.miriad('mfcal')
            mfcal.vis = self.fluxcal
            mfcal.stokes = 'ii'
            if self.crosscal_delay:
                mfcal.options = 'delay'
            else:
                pass
            mfcal.interval = 1000
            mfcal.go()
            self.logger.info('### Bandpass calibration on the flux calibrator data done ###')

    def polarisation(self):
        """
        Derives the polarisation corrections (leakage, angle) from the polarised calibrator. Uses the bandpass from the bandpass calibrator. Does not account for freqeuncy dependent solutions at the moment.
        """
        if self.crosscal_polarisation:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.crosscaldir)
            self.logger.info('### Polarisation calibration on the polarised calibrator data started ###')
            if os.path.isfile(self.crosscaldir + '/' + self.fluxcal + '/' + 'bandpass'):
                self.logger.info('# Bandpass solutions in flux calibrator data found. Using them! #')
                gpcopy = lib.miriad('gpcopy')
                gpcopy.vis = self.fluxcal
                gpcopy.out = self.polcal
                gpcopy.mode = 'copy'
                gpcopy.options = 'nopol,relax'
                gpcopy.go()
                self.logger.info('# Bandpass from flux calibrator data copied to polarised calibrator data #')
                gpcal = lib.miriad('gpcal')
                gpcal.vis = self.polcal
                # uv = aipy.miriad.UV(self.polcal)
                # nchan = uv['nchan']
                # gpcal.nfbin = round(nchan / self.crosscal_polarisation_nchan)
                gpcal.options = 'xyvary,linear'
                gpcal.go()
                self.logger.info('# Solved for polarisation leakage and angle on polarised calibrator #')
            else:
                self.logger.info('# Bandpass solutions from flux calibrator not found #')
                self.logger.info('# Deriving bandpass from polarised calibrator using mfcal #')
                mfcal = lib.miriad('mfcal')
                mfcal.vis = self.polcal
                mfcal.go()
                self.logger.info('# Bandpass solutions from polarised calibrator derived #')
                self.logger.info('# Continuing with polarisation calibration (leakage, angle) from polarised calibrator data #')
                gpcal = lib.miriad('gpcal')
                gpcal.vis = self.polcal
                # uv = aipy.miriad.UV(self.polcal)
                # nchan = uv['nchan']
                # gpcal.nfbin = round(nchan / self.crosscal_polarisation_nchan)
                gpcal.options = 'xyvary,linear'
                gpcal.go()
                self.logger.info('# Solved for polarisation leakage and angle on polarised calibrator #')
            self.logger.info('### Polarisation calibration on the polarised calibrator data done ###')
        else:
            self.logger.info('### No polarisation calibration done! ###')

    def transfer_to_target(self):
        """
        Transfers the gains of the calibrators to the target field. Automatically checks if polarisation calibration has been done.
        """
        if self.crosscal_transfer_to_target:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.crosscaldir)
            self.logger.info('### Copying calibrator solutions to target dataset ###')
            gpcopy = lib.miriad('gpcopy')
            if os.path.isfile(self.crosscaldir + '/' + self.polcal + '/' + 'bandpass') and os.path.isfile(self.crosscaldir + '/' + self.polcal + '/' + 'gains') and os.path.isfile(self.crosscaldir + '/' + self.polcal + '/' + 'leakage'):
                gpcopy.vis = self.polcal
                self.logger.info('# Copying calibrator solutions (bandpass, gains, leakage, angle) from polarised calibrator #')
            elif os.path.isfile(self.crosscaldir + '/' + self.fluxcal + '/' + 'bandpass') and os.path.isfile(self.crosscaldir + '/' + self.fluxcal + '/' + 'gains'):
                gpcopy.vis = self.fluxcal
                self.logger.info('# Copying calibrator solutions (bandpass, gains) from flux calibrator #')
                self.logger.info('# Polarisation calibration solutions (leakage, angle) not found #')
            else:
                self.logger.error('# No calibrator solutions found! Exiting! #')
                sys.exit(1)
            datasets = glob.glob('../../*')
            self.logger.info('# Copying calibrator solutions to ' + str(len(datasets)) + ' beams! #')
            for n, ds in enumerate(datasets):
                if os.path.isfile(ds + '/' + self.crosscalsubdir + '/' + self.target + '/visdata'):
                    gpcopy.out = ds + '/' + self.crosscalsubdir + '/' + self.target
                    gpcopy.options = 'relax'
                    gpcopy.go()
                    self.logger.info('# Calibrator solutions copied to beam ' + str(n).zfill(2) + '! #')
                else:
                    self.logger.warning('# Beam ' + str(n).zfill(2) + ' does not seem to contain data! #')
            self.logger.info('### All solutions copied to target data set(s) ###')
        else:
            self.logger.info('### No copying of calibrator solutions to target data done! ###')

    def show(self, showall=False):
        lib.show(self, 'CROSSCALL', showall)

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in this step!
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        self.logger.warning('### Deleting all cross calibrated data. ###')
        subs_managefiles.director(self, 'ch', self.crosscaldir)
        subs_managefiles.director(self, 'rm', self.crosscaldir + '/*')