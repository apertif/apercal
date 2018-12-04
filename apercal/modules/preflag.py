import glob
import logging

import numpy as np
import pandas as pd
import os

import casacore.tables as pt

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs import param as subs_param
from apercal.subs.param import get_param_def
from apercal.subs.bandpass import create_bandpass
from apercal.ao_strategies import ao_strategies
from apercal.libs import lib
from apercal.exceptions import ApercalException


logger = logging.getLogger(__name__)


class preflag(BaseModule):
    """
    Preflagging class. Used to automatically flag data and apply preknown flags.
    """
    module_name = 'PREFLAG'

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

    preflag_shadow = None
    preflag_edges = None
    preflag_ghosts = None
    preflag_manualflag = None
    preflag_manualflag_fluxcal = None
    preflag_manualflag_polcal = None
    preflag_manualflag_target = None
    preflag_manualflag_targetbeams = None
    preflag_manualflag_auto = None
    preflag_manualflag_antenna = None
    preflag_manualflag_corr = None
    preflag_manualflag_baseline = None
    preflag_manualflag_channel = None
    preflag_manualflag_time = None
    preflag_manualflag_clipzeros = None
    preflag_aoflagger = None
    preflag_aoflagger_bandpass = None
    preflag_aoflagger_fluxcal = None
    preflag_aoflagger_polcal = None
    preflag_aoflagger_target = None
    preflag_aoflagger_targetbeams = None
    preflag_aoflagger_fluxcalstrat = None
    preflag_aoflagger_polcalstrat = None
    preflag_aoflagger_targetstrat = None

    subdirification = None

    def __init__(self, filename=None, **kwargs):
        self.default = lib.load_config(self, filename)
        subs_setinit.setinitdirs(self)

    def go(self):
        """
        Executes the complete preflag step with the parameters indicated in the config-file in the following order:
        shadow
        edges
        ghosts
        manualflag
        aoflagger
        """
        logger.info('Starting Pre-flagging step')
        self.shadow()
        self.aoflagger()
        self.edges()
        self.ghosts()
        self.manualflag()
        logger.info('Pre-flagging step done')

    @staticmethod
    def _getnchan(msname):
        """Return the number of channels in a given ms"""
        spectralwindowtable = pt.table(msname + '::SPECTRAL_WINDOW', ack=False)
        nchan = spectralwindowtable.getcol("CHAN_FREQ").shape[1]
        return nchan

    def shadow(self):
        """
        Flag all data sets for shadowed antennas using drivecasa and the CASA task flagdata
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        logger.debug('Shadowed antenna flagging step started')

        # Create the parameters for the parameter file for the shadowing status

        # Is the fluxcal shadow flagged?
        preflagfluxcalshadow = get_param_def(self, 'preflag_fluxcal_shadow', False)

        # Is the polcal shadow flagged?
        preflagpolcalshadow = get_param_def(self, 'preflag_polcal_shadow', False)

        # Are the target beams shadow flagged?
        preflagtargetbeamsshadow = get_param_def(self, 'preflag_targetbeams_shadow', np.full(beams, False))

        # Flag shadowed antennas

        if self.preflag_shadow:
            logger.info('Flagging shadowed antennas')
            # Flag the flux calibrator
            if preflagfluxcalshadow:
                logger.info('Shadowed antenna(s) for flux calibrator were already flagged')
            else:
                if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                    logger.debug('Flagging shadowed antennas for flux calibrator')
                    fc_shadow = 'flagdata(vis="' + self.get_fluxcal_path() + '", mode="shadow", flagbackup=False)'
                    lib.run_casa([fc_shadow])
                    preflagfluxcalshadow = True
                else:
                    logger.warning('Flux calibrator dataset {} not available. Not flagging '
                                   'shadowed antennas for flux calibrator'.format(self.get_fluxcal_path()))
                    preflagfluxcalshadow = False
            # Flag the polarised calibrator
            if preflagpolcalshadow:
                logger.info('Shadowed antenna(s) for polarised calibrator were already flagged')
            else:
                if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                    logger.debug('Flagging shadowed antennas for polarised calibrator')
                    pc_shadow = 'flagdata(vis="' + self.get_polcal_path() + '", mode="shadow", flagbackup=False)'
                    lib.run_casa([pc_shadow])
                    preflagpolcalshadow = True
                else:
                    logger.warning('Polarised calibrator dataset not specified or dataset not available. Not '
                                   'flagging shadowed antennas for polarised calibrator')
                    preflagpolcalshadow = False
            # Flag the target beams
            if self.target != '':
                for vis, beam in self.get_datasets():
                    if preflagtargetbeamsshadow[int(beam)]:
                        logger.info('Shadowed antenna(s) for beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Flagging shadowed antennas for beam ' + beam)
                        tg_shadow = 'flagdata(vis="' + str(vis) + '", autocorr=True, flagbackup=False)'
                        lib.run_casa([tg_shadow])
                        preflagtargetbeamsshadow[int(beam)] = True
            else:
                logger.warning('No target dataset specified! Not flagging shadowed antennas for target datasets')
        else:
            logger.warning('Shadowed antenna(s) are not flagged!')
        logger.debug('Shadowed antenna flagging step done')

        # Save the derived parameters for the shadow flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_shadow', preflagfluxcalshadow)
        subs_param.add_param(self, 'preflag_polcal_shadow', preflagpolcalshadow)
        subs_param.add_param(self, 'preflag_targetbeams_shadow', preflagtargetbeamsshadow)

    def edges(self):
        """
        Flag the edges of the subbands
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        logger.debug('Starting to flag the edges of the subbands')

        # Create the parameters for the parameter file for the shadowing status

        # Edges of fluxcal flagged?
        preflagfluxcaledges = get_param_def(self, 'preflag_fluxcal_edges', False)

        # Edges of polcal flagged?
        preflagpolcaledges = get_param_def(self, 'preflag_polcal_edges', False)

        # Edges of target beams flagged?
        preflagtargetbeamsedges = get_param_def(self, 'preflag_targetbeams_edges', np.full(beams, False))

        if self.preflag_edges:
            logger.info('Flagging subband edges')
            # Flag the flux calibrator
            if preflagfluxcaledges:
                logger.info('Subband edges for flux calibrator were already flagged')
            else:
                if self.fluxcal != '' and os.path.isdir(
                        self.get_fluxcal_path()):
                    # Flag the subband edges of the flux calibrator data set
                    logger.debug('Flagging subband edges for flux calibrator')
                    # Get the number of channels of the flux calibrator data set
                    nchannel = self._getnchan(self.get_fluxcal_path())
                    # Calculate the subband edges of the flux calibrator data set
                    a = range(0, nchannel, 64)
                    b = range(1, nchannel, 64)
                    c = range(63, nchannel, 64)
                    l = a + b + c
                    m = ';'.join(str(ch) for ch in l)
                    fc_edges_flagcmd = 'flagdata(vis="' + self.get_fluxcal_path() + '", spw="0:' + m + '", flagbackup=False)'
                    lib.run_casa([fc_edges_flagcmd])
                    preflagfluxcaledges = True
                else:
                    logger.warning('No flux calibrator dataset specified. Subband edges of flux calibrator '
                                   'will not be flagged!')
                    preflagfluxcaledges = False
            # Flag the polarised calibrator
            if preflagpolcaledges:
                logger.info('Subband edges for polarised calibrator were already flagged')
            else:
                if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                    # Flag the subband edges of the polarised calibrator data set
                    logger.debug('Flagging subband edges for polarised calibrator #')
                    # Get the number of channels of the polarised calibrator data set
                    nchannel = self._getnchan(self.get_polcal_path())
                    # Calculate the subband edges of the polarised calibrator data set
                    a = range(0, nchannel, 64)
                    b = range(1, nchannel, 64)
                    c = range(63, nchannel, 64)
                    l = a + b + c
                    m = ';'.join(str(ch) for ch in l)
                    pc_edges_flagcmd = 'flagdata(vis="' + self.get_polcal_path() + '", spw="0:' + m + '", flagbackup=False)'
                    lib.run_casa([pc_edges_flagcmd])
                    preflagpolcaledges = True
                else:
                    logger.warning('No polarised calibrator dataset specified. Subband edges of polarised '
                                   'calibrator will not be flagged!')
                    preflagpolcaledges = False
            if self.target != '':
                # Flag the subband edges of the the target beam datasets
                # Collect all the available target beam datasets
                for vis, beam in self.get_datasets():
                    if preflagtargetbeamsedges[int(beam)]:
                        logger.info('Subband edges for target beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Flagging subband edges for target beam ' + beam)
                        nchannel = self._getnchan(vis)
                        # Calculate the subband edges for each target beam data set
                        a = range(0, nchannel, 64)
                        b = range(1, nchannel, 64)
                        c = range(63, nchannel, 64)
                        l = a + b + c
                        m = ';'.join(str(ch) for ch in l)
                        tg_edges_flagcmd = 'flagdata(vis="' + vis + '", spw="0:' + m + '", flagbackup=False)'
                        lib.run_casa([tg_edges_flagcmd])
                        preflagtargetbeamsedges[int(beam)] = True
            else:
                logger.warning('No target dataset specified. Subband edges of target dataset(s) will not be flagged!')
        else:
            logger.warning('Subband edges are not flagged!')
        logger.debug(' Finished flagging subband edges')

        # Save the derived parameters for the subband edges flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_edges', preflagfluxcaledges)
        subs_param.add_param(self, 'preflag_polcal_edges', preflagpolcaledges)
        subs_param.add_param(self, 'preflag_targetbeams_edges', preflagtargetbeamsedges)

    def ghosts(self):
        """
        Flag the ghosts of each subband at channel 16 and 48
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        logger.debug(' Starting to flag the ghost channels')

        # Create the parameters for the parameter file for the shadowing status

        # Ghosts of fluxcal flagged?
        preflagfluxcalghosts = get_param_def(self, 'preflag_fluxcal_ghosts', False)

        # Ghosts of polcal flagged?
        preflagpolcalghosts = get_param_def(self, 'preflag_polcal_ghosts', False)

        # Ghosts of target beams flagged?
        preflagtargetbeamsghosts = get_param_def(self, 'preflag_targetbeams_ghosts', np.full(beams, False))

        if self.preflag_ghosts:
            logger.info('Flagging ghost channels')
            # Flag the ghost channels in the flux calibrator
            if preflagfluxcalghosts:
                logger.info('Ghost channels for flux calibrator were already flagged')
            else:
                if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                    # Flag the ghosts in the flux calibrator data set
                    logger.debug('Flagging ghost channels for flux calibrator')
                    # Get the number of channels of the flux calibrator data set
                    nchannel = self._getnchan(self.get_fluxcal_path())
                    # Calculate the ghost positions for the flux calibrator data set
                    a = range(16, nchannel, 64)
                    b = range(48, nchannel, 64)
                    l = a + b
                    m = ';'.join(str(ch) for ch in l)
                    fc_ghosts_flagcmd = 'flagdata(vis="' + self.get_fluxcal_path() + '", spw="0:' + m + '", flagbackup=False)'
                    lib.run_casa([fc_ghosts_flagcmd])
                    preflagfluxcalghosts = True
                else:
                    logger.warning('No flux calibrator dataset specified. Ghosts in flux calibrator dataset '
                                   'will not be flagged!')
                    preflagfluxcalghosts = False
            # Flag the ghost channels in the polarised calibrator
            if preflagpolcalghosts:
                logger.info('Ghost channels for polarised calibrator were already flagged')
            else:
                if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                    # Flag the ghosts in the polarised calibrator data set
                    logger.debug('Flagging ghost channels for polarised calibrator')
                    # Get the number of channels of the polarised calibrator data set
                    nchannel = self._getnchan(self.get_polcal_path())
                    # Calculate the subband edges of the polarised calibrator data set
                    a = range(0, nchannel, 64)
                    b = range(1, nchannel, 64)
                    l = a + b
                    m = ';'.join(str(ch) for ch in l)
                    pc_ghosts_flagcmd = 'flagdata(vis="' + self.get_polcal_path() + '", spw="0:' + m + '", flagbackup=False)'
                    lib.run_casa([pc_ghosts_flagcmd])
                    preflagpolcalghosts = True
                else:
                    logger.warning('No polarised calibrator dataset specified. Ghosts in polarised calibrator '
                                   'will not be flagged!')
                    preflagpolcalghosts = False
            if self.target != '':
                # Flag the ghosts in the target beam datasets
                # Collect all the available target beam datasets
                for vis, beam in self.get_datasets():
                    if preflagtargetbeamsghosts[int(beam)]:
                        logger.info('Ghost channels for target beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Flagging ghost channels for target beam ' + beam)
                        nchannel = self._getnchan(vis)
                        # Calculate the ghost channels for each target beam data set
                        a = range(0, nchannel, 64)
                        b = range(1, nchannel, 64)
                        l = a + b
                        m = ';'.join(str(ch) for ch in l)
                        tg_ghosts_flagcmd = 'flagdata(vis="' + vis + '", spw="0:' + m + '", flagbackup=False)'
                        lib.run_casa([tg_ghosts_flagcmd])
                        preflagtargetbeamsghosts[int(beam)] = True
            else:
                logger.warning('No target dataset specified. Ghosts in target dataset(s) will not be flagged!')
        else:
            logger.warning('Ghost channels are not flagged!')
        logger.debug('Finished flagging ghost channels')

        # Save the derived parameters for the subband edges flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_ghosts', preflagfluxcalghosts)
        subs_param.add_param(self, 'preflag_polcal_ghosts', preflagpolcalghosts)
        subs_param.add_param(self, 'preflag_targetbeams_ghosts', preflagtargetbeamsghosts)

    def manualflag(self):
        """
        Use drivecasa and the CASA task flagdata to flag entire antennas, baselines, correlations etc. before doing
        any other calibration.
        """
        if self.preflag_manualflag:
            logger.debug('Manual flagging step started')
            self.manualflag_auto()
            self.manualflag_antenna()
            self.manualflag_corr()
            self.manualflag_baseline()
            self.manualflag_channel()
            self.manualflag_time()
            self.manualflag_clipzeros()
            logger.debug('Manual flagging step done')

    def aoflagger(self):
        """
        Runs aoflagger on the datasets with the strategies given in the config-file. Creates and applies a preliminary
        bandpass before executing the strategy for better performance of the flagging routines. Strategies for
        calibrators and target fields normally differ.
        """
        if self.preflag_aoflagger:
            logger.debug('Pre-flagging with AOFlagger started')
            self.aoflagger_bandpass()
            self.aoflagger_flag()
            logger.debug('Pre-flagging with AOFlagger done')
        else:
            logger.warning('No flagging with AOflagger done! Your data might be contaminated by RFI!')

    def manualflag_auto(self):
        """
        Function to flag the auto-correlations
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the manualflag step to flag the auto-correlations

        # Auto-correlations of fluxcal flagged?
        preflagfluxcalmanualflagauto = get_param_def(self, 'preflag_fluxcal_manualflag_auto', False)

        # Auto-correlations of polcal flagged?
        preflagpolcalmanualflagauto = get_param_def(self, 'preflag_polcal_manualflag_auto', False)
        # Auto-correlations of target beams flagged?
        preflagtargetbeamsmanualflagauto = get_param_def(self, 'preflag_targetbeams_manualflag_auto',
                                                         np.full(beams, False))

        if self.preflag_manualflag_auto:
            logger.info('Flagging auto-correlations')
            # Flag the auto-correlations for the flux calibrator
            if preflagfluxcalmanualflagauto and self.preflag_manualflag_fluxcal:
                logger.info('Auto-correlations for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()):
                    fc_auto = 'flagdata(vis="' + self.get_fluxcal_path() + '", autocorr=True, flagbackup=False)'
                    lib.run_casa([fc_auto])
                    logger.debug('Flagged auto-correlations for flux calibrator')
                    preflagfluxcalmanualflagauto = True
                else:
                    preflagfluxcalmanualflagauto = False
                    logger.warning('No flux calibrator dataset specified. Auto-correlations for flux calibrator '
                                   'dataset will not be flagged!')
            # Flag the auto-correlations for the polarised calibrator
            if preflagpolcalmanualflagauto and self.preflag_manualflag_polcal:
                logger.info('Auto-correlations for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()):
                    pc_auto = 'flagdata(vis="' + self.get_polcal_path() + '", autocorr=True, flagbackup=False)'
                    lib.run_casa([pc_auto])
                    logger.debug('Flagged auto-correlations for polarised calibrator')
                    preflagpolcalmanualflagauto = True
                else:
                    preflagpolcalmanualflagauto = False
                    logger.warning('No polarised calibrator dataset specified. Auto-correlations for polariased '
                                   'calibrator dataset will not be flagged!')
            # Flag the auto-correlations for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = self.get_datasets()
                    logger.debug('Flagging auto-correlations for all target beams')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.get_datasets(beams=beams)]
                    logger.debug('Flagging auto-correlations for selected target beams')
                for vis, beam in datasets:
                    if preflagtargetbeamsmanualflagauto[int(beam)]:
                        logger.info('Auto-correlations for target beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Flagging auto-correlations for target beam ' + beam)
                        tg_auto = 'flagdata(vis="' + str(vis) + '", autocorr=True, flagbackup=False)'
                        lib.run_casa([tg_auto])
                        preflagtargetbeamsmanualflagauto[int(beam)] = True
            else:
                logger.warning('Target dataset not specified. Auto-correlations for target beam dataset(s) will '
                               'not be flagged!')

        # Save the derived parameters for the auto-correlation flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_manualflag_auto', preflagfluxcalmanualflagauto)
        subs_param.add_param(self, 'preflag_polcal_manualflag_auto', preflagpolcalmanualflagauto)
        subs_param.add_param(self, 'preflag_targetbeams_manualflag_auto', preflagtargetbeamsmanualflagauto)

    def manualflag_antenna(self):
        """
        Function to flag complete antennas
        Antennas are named by their antenna names (e.g. 'RT2,RT3')
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the manualflag step to flag individual antennas

        # Flagged antennas of fluxcal?
        preflagfluxcalmanualflagantenna = get_param_def(self, 'preflag_fluxcal_manualflag_antenna', np.full(1, '', dtype='U50'))

        # Flagged antennas of polcal?
        preflagpolcalmanualflagantenna = get_param_def(self, 'preflag_polcal_manualflag_antenna', np.full(1, '', dtype='U50'))  # Flagged antennas of target beams?
        preflagtargetbeamsmanualflagantenna = get_param_def(self, 'preflag_targetbeams_manualflag_antenna', np.full(
            beams, '', dtype='U50'))

        if self.preflag_manualflag_antenna != '':
            logger.info('Flagging antenna(s) ' + self.preflag_manualflag_antenna)
            # Flag antenna(s) for flux calibrator
            if preflagfluxcalmanualflagantenna[0] == self.preflag_manualflag_antenna and self.preflag_manualflag_fluxcal:
                logger.info('Antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()):
                    fc_ant = 'flagdata(vis="' + self.get_fluxcal_path() + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                    lib.run_casa([fc_ant])
                    logger.debug('Flagged antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator')
                    spltant = self.preflag_manualflag_antenna.split(',')
                    for ant in spltant:
                        if preflagfluxcalmanualflagantenna[0].find(ant) == -1:
                            if preflagfluxcalmanualflagantenna[0] == '':
                                preflagfluxcalmanualflagantenna[0] = ant
                            else:
                                preflagfluxcalmanualflagantenna[0] = preflagfluxcalmanualflagantenna[0] + ',' + ant
                else:
                    logger.warning('No flux calibrator dataset specified. Specified antenna(s) for flux calibrator dataset will not be flagged!')
            # Flag antenna(s) for polarised calibrator
            if preflagpolcalmanualflagantenna[0] == self.preflag_manualflag_antenna and self.preflag_manualflag_polcal:
                logger.info('Antenna(s) ' + self.preflag_manualflag_antenna + ' for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()):
                    pc_ant = 'flagdata(vis="' + self.get_polcal_path() + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                    lib.run_casa([pc_ant])
                    logger.debug('Flagged antenna(s) ' + self.preflag_manualflag_antenna + ' for polarised calibrator')
                    spltant = self.preflag_manualflag_antenna.split(',')
                    for ant in spltant:
                        if preflagpolcalmanualflagantenna[0].find(ant) == -1:
                            if preflagpolcalmanualflagantenna[0] == '':
                                preflagpolcalmanualflagantenna[0] = ant
                            else:
                                preflagpolcalmanualflagantenna[0] = preflagpolcalmanualflagantenna[0] + ',' + ant
                else:
                    logger.warning('No polarised calibrator dataset specified. Specified antenna(s) for polarised calibrator dataset will not be flagged!')
            # Flag antenna(s) for target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = self.get_datasets()
                    logger.debug('Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for all target beams')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.get_datasets(beams=beams)]
                    logger.debug('Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for selected target beams')
                for vis, beam in datasets:
                    if preflagtargetbeamsmanualflagantenna[int(beam)] == self.preflag_manualflag_antenna:
                        logger.info('Antenna(s) ' + self.preflag_manualflag_antenna + ' for target beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for target beam ' + beam)
                        tg_ant = 'flagdata(vis="' + str(vis) + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                        lib.run_casa([tg_ant])
                        spltant = self.preflag_manualflag_antenna.split(',')
                        for ant in spltant:
                            if preflagtargetbeamsmanualflagantenna[int(beam)].find(ant) == -1:
                                if preflagtargetbeamsmanualflagantenna[int(beam)] == '':
                                    preflagtargetbeamsmanualflagantenna[int(beam)] = ant
                                else:
                                    preflagtargetbeamsmanualflagantenna[int(beam)] = preflagtargetbeamsmanualflagantenna[int(beam)] + ',' + ant
            else:
                logger.warning('Target dataset not specified. Specified antenna(s) for target beam dataset(s) will not be flagged!')

        # Save the derived parameters for the antenna flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_manualflag_antenna', preflagfluxcalmanualflagantenna)
        subs_param.add_param(self, 'preflag_polcal_manualflag_antenna', preflagpolcalmanualflagantenna)
        subs_param.add_param(self, 'preflag_targetbeams_manualflag_antenna', preflagtargetbeamsmanualflagantenna)

    def manualflag_corr(self):
        """
        Function to flag complete correlations
        Possible values are 'XX,XY,YX,YY'
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the manualflag step to flag individual correlations

        preflagfluxcalmanualflagcorr = get_param_def(self, 'preflag_fluxcal_manualflag_corr', np.full(1, '', dtype='U50'))  # Flagged correlations of fluxcal?
        preflagpolcalmanualflagcorr = get_param_def(self, 'preflag_polcal_manualflag_corr', np.full(1, '', dtype='U50'))  # Flagged correlations of polcal?
        preflagtargetbeamsmanualflagcorr = get_param_def(self, 'preflag_targetbeams_manualflag_corr', np.full(beams, '', dtype='U50'))  # Flagged correlations of target beams?

        if self.preflag_manualflag_corr != '':
            logger.info('Flagging correlation(s) ' + self.preflag_manualflag_corr)
            # Flag correlation(s) for flux calibrator
            if preflagfluxcalmanualflagcorr[0] == self.preflag_manualflag_corr and self.preflag_manualflag_fluxcal:
                logger.info('Correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()):
                    subs_setinit.setinitdirs(self)
                    fc_corr = 'flagdata(vis="' + self.get_fluxcal_path() + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                    lib.run_casa([fc_corr])
                    logger.debug('Flagged correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator')
                    spltcorr = self.preflag_manualflag_corr.split(',')
                    for corr in spltcorr:
                        if preflagfluxcalmanualflagcorr[0].find(corr) == -1:
                            if preflagfluxcalmanualflagcorr[0] == '':
                                preflagfluxcalmanualflagcorr[0] = corr
                            else:
                                preflagfluxcalmanualflagcorr[0] = preflagfluxcalmanualflagcorr[0] + ',' + corr
                else:
                    logger.warning('No flux calibrator dataset specified. Specified correlation(s) for flux calibrator dataset will not be flagged!')
            # Flag correlation(s) for flux calibrator
            if preflagpolcalmanualflagcorr[0] == self.preflag_manualflag_corr and self.preflag_manualflag_polcal:
                logger.info('Correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()):
                    subs_setinit.setinitdirs(self)
                    pc_corr = 'flagdata(vis="' + self.get_polcal_path() + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                    lib.run_casa([pc_corr])
                    logger.debug('Flagged correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator')
                    spltcorr = self.preflag_manualflag_corr.split(',')
                    for corr in spltcorr:
                        if preflagpolcalmanualflagcorr[0].find(corr) == -1:
                            if preflagpolcalmanualflagcorr[0] == '':
                                preflagpolcalmanualflagcorr[0] = corr
                            else:
                                preflagpolcalmanualflagcorr[0] = preflagpolcalmanualflagcorr[0] + ',' + corr
                else:
                    logger.warning('No polarised calibrator dataset specified. Specified correlation(s) for polarised calibrator dataset will not be flagged!')
            # Flag correlation(s) for target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = self.get_datasets()
                    logger.debug('Flagging correlation(s) ' + self.preflag_manualflag_corr + ' for all target beams')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.get_datasets(beams=beams)]
                    logger.debug('Flagging correlation(s) ' + self.preflag_manualflag_corr + ' for selected target beams')
                for vis, beam in datasets:
                    if preflagtargetbeamsmanualflagcorr[int(beam)] == self.preflag_manualflag_corr:
                        logger.info('Correlation(s) ' + self.preflag_manualflag_corr + ' for target beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Flagging correlations(s) ' + self.preflag_manualflag_corr + ' for target beam ' + beam)
                        tg_corr = 'flagdata(vis="' + str(vis) + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                        lib.run_casa([tg_corr])
                        spltcorr = self.preflag_manualflag_corr.split(',')
                        for corr in spltcorr:
                            if preflagtargetbeamsmanualflagcorr[int(beam)].find(corr) == -1:
                                if preflagtargetbeamsmanualflagcorr[int(beam)] == '':
                                    preflagtargetbeamsmanualflagcorr[int(beam)] = corr
                                else:
                                    preflagtargetbeamsmanualflagcorr[int(beam)] = preflagtargetbeamsmanualflagcorr[int(beam)] + ',' + corr
            else:
                logger.warning('Target dataset not specified. Specified correlation(s) for target beam dataset(s) will not be flagged!')

        # Save the derived parameters for the correlation flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_manualflag_corr', preflagfluxcalmanualflagcorr)
        subs_param.add_param(self, 'preflag_polcal_manualflag_corr', preflagpolcalmanualflagcorr)
        subs_param.add_param(self, 'preflag_targetbeams_manualflag_corr', preflagtargetbeamsmanualflagcorr)

    def manualflag_baseline(self):
        """
        Function to flag complete baselines
        Use antenna names and the notation 'ant1&ant2;ant3&ant4' etc.
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the manualflag step to flag individual baselines

        preflagfluxcalmanualflagbaseline = get_param_def(self, 'preflag_fluxcal_manualflag_baseline', np.full(1, '', dtype='U50'))  # Flagged baselines of fluxcal?
        preflagpolcalmanualflagbaseline = get_param_def(self, 'preflag_polcal_manualflag_baseline', np.full(1, '', dtype='U50'))  # Flagged baselines of polcal?
        preflagtargetbeamsmanualflagbaseline = get_param_def(self, 'preflag_targetbeams_manualflag_baseline', np.full(
            beams, '', dtype='U50'))  # Flagged baselines of target beams?

        if self.preflag_manualflag_baseline != '':
            logger.info('Flagging baseline(s) ' + self.preflag_manualflag_baseline)
            # Flag correlation(s) for the flux calibrator
            if preflagfluxcalmanualflagbaseline[0] == self.preflag_manualflag_baseline and self.preflag_manualflag_fluxcal:
                logger.info('Baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(
                        self.get_fluxcal_path()):
                    fc_baseline = 'flagdata(vis="' + self.get_fluxcal_path() + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                    lib.run_casa([fc_baseline])
                    logger.debug('Flagged baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator')
                    spltbaseline = self.preflag_manualflag_baseline.split(',')
                    for baseline in spltbaseline:
                        if preflagfluxcalmanualflagbaseline[0].find(baseline) == -1:
                            if preflagfluxcalmanualflagbaseline[0] == '':
                                preflagfluxcalmanualflagbaseline[0] = baseline
                            else:
                                preflagfluxcalmanualflagbaseline[0] = preflagfluxcalmanualflagbaseline[0] + ',' + baseline
                else:
                    logger.warning('No flux calibrator dataset specified. Specified baselines(s) for flux calibrator dataset will not be flagged!')
            # Flag correlation(s) for the polarised calibrator
            if preflagpolcalmanualflagbaseline[0] == self.preflag_manualflag_baseline and \
                    self.preflag_manualflag_polcal:
                logger.info('Baseline(s) ' + self.preflag_manualflag_baseline + ' for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()):
                    pc_baseline = 'flagdata(vis="' + self.get_polcal_path() + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                    lib.run_casa([pc_baseline])
                    logger.debug('Flagged baseline(s) ' + self.preflag_manualflag_baseline + ' for polarised calibrator')
                    spltbaseline = self.preflag_manualflag_baseline.split(',')
                    for baseline in spltbaseline:
                        if preflagpolcalmanualflagbaseline[0].find(baseline) == -1:
                            if preflagpolcalmanualflagbaseline[0] == '':
                                preflagpolcalmanualflagbaseline[0] = baseline
                            else:
                                preflagpolcalmanualflagbaseline[0] = preflagpolcalmanualflagbaseline[0] + ',' + baseline
                else:
                    logger.warning('No polarised calibrator dataset specified. Specified baselines(s) for polarised calibrator dataset will not be flagged!')
            # Flag correlation(s) for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = self.get_datasets()
                    logger.debug('Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for all target beams')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.get_datasets(beams=beams)]
                    logger.debug('Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for selected target beams')
                for vis, beam in datasets:
                    if preflagtargetbeamsmanualflagbaseline[int(beam)] == self.preflag_manualflag_baseline:
                        logger.info('Correlation(s) ' + self.preflag_manualflag_baseline + ' for target beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for target beam ' + beam)
                        tg_baseline = 'flagdata(vis="' + str(vis) + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                        lib.run_casa([tg_baseline])
                        for baseline in spltbaseline:
                            if preflagtargetbeamsmanualflagbaseline[int(beam)].find(baseline) == -1:
                                if preflagtargetbeamsmanualflagbaseline[int(beam)] == '':
                                    preflagtargetbeamsmanualflagbaseline[int(beam)] = baseline
                                else:
                                    preflagtargetbeamsmanualflagbaseline[int(beam)] = preflagtargetbeamsmanualflagbaseline[int(beam)] + ',' + baseline
            else:
                logger.warning('Target dataset not specified. Specified baseline(s) for target beam dataset(s) will not be flagged!')

        # Save the derived parameters for the baseline flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_manualflag_baseline', preflagfluxcalmanualflagbaseline)
        subs_param.add_param(self, 'preflag_polcal_manualflag_baseline', preflagpolcalmanualflagbaseline)
        subs_param.add_param(self, 'preflag_targetbeams_manualflag_baseline', preflagtargetbeamsmanualflagbaseline)

    def manualflag_channel(self):
        """
        Function to flag individual channels and channel ranges
        Use the CASA notation e.g. '0~5;120~128'. You don't need to give a '0:' for the spw. It's added automatically.
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the manualflag step to flag individual channel ranges

        preflagfluxcalmanualflagchannel = get_param_def(self, 'preflag_fluxcal_manualflag_channel', np.full(1, '', dtype='U50'))  # Flagged channels of fluxcal?
        preflagpolcalmanualflagchannel = get_param_def(self, 'preflag_polcal_manualflag_channel', np.full(1, '', dtype='U50'))  # Flagged channels of polcal?
        preflagtargetbeamsmanualflagchannel = get_param_def(self, 'preflag_targetbeams_manualflag_channel', np.full(
            beams, '', dtype='U50'))  # Flagged channels of target beams?

        if self.preflag_manualflag_channel != '':
            logger.info('Flagging channel(s) ' + self.preflag_manualflag_channel)
            # Flag channel(s) for the flux calibrator
            if preflagfluxcalmanualflagchannel[0] == self.preflag_manualflag_channel and self.preflag_manualflag_fluxcal:
                logger.info('Channel(s) ' + self.preflag_manualflag_channel + ' for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()):
                    fc_channel = 'flagdata(vis="' + self.get_fluxcal_path() + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                    lib.run_casa([fc_channel])
                    logger.debug('Flagged channel(s) ' + self.preflag_manualflag_channel + ' for flux calibrator')
                    spltchannel = self.preflag_manualflag_channel.split(',')
                    for channel in spltchannel:
                        if preflagfluxcalmanualflagchannel[0].find(channel) == -1:
                            if preflagfluxcalmanualflagchannel[0] == '':
                                preflagfluxcalmanualflagchannel[0] = channel
                            else:
                                preflagfluxcalmanualflagchannel[0] = preflagfluxcalmanualflagchannel[0] + ',' + channel
                else:
                    logger.warning('No flux calibrator dataset specified. Specified channel range(s) for flux calibrator dataset will not be flagged!')
            # Flag channel(s) for the polarised calibrator
            if preflagpolcalmanualflagchannel[0] == self.preflag_manualflag_channel and self.preflag_manualflag_polcal:
                logger.info('Channel(s) ' + self.preflag_manualflag_channel + ' for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()):
                    pc_channel = 'flagdata(vis="' + self.get_polcal_path() + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                    lib.run_casa([pc_channel])
                    logger.debug('Flagged channel(s) ' + self.preflag_manualflag_channel + ' for polarised calibrator')
                    spltchannel = self.preflag_manualflag_channel.split(',')
                    for channel in spltchannel:
                        if preflagpolcalmanualflagchannel[0].find(channel) == -1:
                            if preflagpolcalmanualflagchannel[0] == '':
                                preflagpolcalmanualflagchannel[0] = channel
                            else:
                                preflagpolcalmanualflagchannel[0] = preflagpolcalmanualflagchannel[0] + ',' + channel
                else:
                    logger.warning('No polarised calibrator dataset specified. Specified channel range(s) for polarised calibrator dataset will not be flagged!')
            # Flag channel(s) for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = self.get_datasets()
                    logger.debug('Flagging channel(s) ' + self.preflag_manualflag_channel + ' for all target beams')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.get_datasets(beams=beams)]
                    logger.debug('Flagging channel(s) ' + self.preflag_manualflag_channel + ' for selected target beams')
                for vis, beam in datasets:
                    if preflagtargetbeamsmanualflagchannel[int(beam)] == self.preflag_manualflag_channel:
                        logger.info('Correlation(s) ' + self.preflag_manualflag_channel + ' for target beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Flagging channel(s) ' + self.preflag_manualflag_channel + ' for target beam ' + beam)
                        tg_channel = 'flagdata(vis="' + str(vis) + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                        lib.run_casa([tg_channel])
                        for channel in spltchannel:
                            if preflagtargetbeamsmanualflagchannel[int(beam)].find(channel) == -1:
                                if preflagtargetbeamsmanualflagchannel[int(beam)] == '':
                                    preflagtargetbeamsmanualflagchannel[int(beam)] = channel
                                else:
                                    preflagtargetbeamsmanualflagchannel[int(beam)] = preflagtargetbeamsmanualflagchannel[int(beam)] + ',' + channel
            else:
                logger.warning('Target dataset not specified. Specified channel range(s) for target beam dataset(s) will not be flagged!')

        # Save the derived parameters for the channel flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_manualflag_channel', preflagfluxcalmanualflagchannel)
        subs_param.add_param(self, 'preflag_polcal_manualflag_channel', preflagpolcalmanualflagchannel)
        subs_param.add_param(self, 'preflag_targetbeams_manualflag_channel', preflagtargetbeamsmanualflagchannel)

    def manualflag_time(self):
        """
        Function to flag time ranges
        Use the CASA notation e.g. '09:14:0~09:54:0'.
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the manualflag step to flag individual channel ranges

        preflagfluxcalmanualflagtime = get_param_def(self, 'preflag_fluxcal_manualflag_time', np.full(1, '', dtype='U50'))  # Flagged time range(s) of fluxcal?
        preflagpolcalmanualflagtime = get_param_def(self, 'preflag_polcal_manualflag_time', np.full(1, '', dtype='U50'))  # Flagged time range(s) of polcal?
        preflagtargetbeamsmanualflagtime = get_param_def(self, 'preflag_targetbeams_manualflag_time', np.full(beams, '', dtype='U50'))  # Flagged time range(s) of target beams?

        if self.preflag_manualflag_time != '':
            logger.info('Flagging time range ' + self.preflag_manualflag_time)
            # Flag time range for the flux calibrator
            if preflagfluxcalmanualflagtime[0] == self.preflag_manualflag_time and self.preflag_manualflag_fluxcal:
                logger.info('Time range ' + self.preflag_manualflag_time + ' for flux calibrator was already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()):
                    fc_time = 'flagdata(vis="' + self.get_fluxcal_path() + '", timerange="' + self.preflag_manualflag_time + '", flagbackup=False)'
                    lib.run_casa([fc_time])
                    logger.debug('Flagged time range ' + self.preflag_manualflag_time + ' for flux calibrator')
                    splttime = self.preflag_manualflag_time.split(',')
                    for time in splttime:
                        if preflagfluxcalmanualflagtime[0].find(time) == -1:
                            if preflagfluxcalmanualflagtime[0] == '':
                                preflagfluxcalmanualflagtime[0] = time
                            else:
                                preflagfluxcalmanualflagtime[0] = preflagfluxcalmanualflagtime[0] + ',' + time
                else:
                    logger.warning('No flux calibrator dataset specified. Specified time range(s) for '
                                   'flux calibrator dataset will not be flagged!')
            # Flag time range for the polarised calibrator
            if preflagpolcalmanualflagtime[0] == self.preflag_manualflag_time and self.preflag_manualflag_polcal:
                logger.info('Time range ' + self.preflag_manualflag_time + ' for polarised calibrator was already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()):
                    pc_time = 'flagdata(vis="' + self.get_polcal_path() + '", timerange="' + self.preflag_manualflag_time + '", flagbackup=False)'
                    lib.run_casa([pc_time])
                    logger.debug('Flagged time range ' + self.preflag_manualflag_time + ' for polarised calibrator')
                    splttime = self.preflag_manualflag_time.split(',')
                    for time in splttime:
                        if preflagpolcalmanualflagtime[0].find(time) == -1:
                            if preflagpolcalmanualflagtime[0] == '':
                                preflagpolcalmanualflagtime[0] = time
                            else:
                                preflagpolcalmanualflagtime[0] = preflagpolcalmanualflagtime[0] + ',' + time
                else:
                    logger.warning('No polariased calibrator dataset specified. Specified time range(s) '
                                   'for polarised calibrator dataset will not be flagged!')
            # Flag time range for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = self.get_datasets()
                    logger.debug('Flagging time range ' + self.preflag_manualflag_time + ' for all target beams')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.get_datasets(beams=beams)]
                    logger.debug('Flagging time range ' + self.preflag_manualflag_time + ' for selected target beams')
                for vis, beam in datasets:
                    if preflagtargetbeamsmanualflagtime[int(beam)] == self.preflag_manualflag_time:
                        logger.info('Time range ' + self.preflag_manualflag_time + ' for target beam ' + beam + ' was already flagged')
                    else:
                        logger.debug('Flagging time range(s) ' + self.preflag_manualflag_time + ' for target beam ' + beam)
                        tg_time = 'flagdata(vis="' + str(vis) + '", timerange="' + self.preflag_manualflag_channel + '", flagbackup=False)'
                        lib.run_casa([tg_time])
                        for time in splttime:
                            if preflagtargetbeamsmanualflagtime[int(beam)].find(time) == -1:
                                if preflagtargetbeamsmanualflagtime[int(beam)] == '':
                                    preflagtargetbeamsmanualflagtime[int(beam)] = time
                                else:
                                    preflagtargetbeamsmanualflagtime[int(beam)] = preflagtargetbeamsmanualflagtime[int(beam)] + ',' + time
            else:
                logger.warning('Target dataset not specified. Specified time range(s) for target beam dataset(s) will not be flagged!')

        # Save the derived parameters for the channel flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_manualflag_time', preflagfluxcalmanualflagtime)
        subs_param.add_param(self, 'preflag_polcal_manualflag_time', preflagpolcalmanualflagtime)
        subs_param.add_param(self, 'preflag_targetbeams_manualflag_time', preflagtargetbeamsmanualflagtime)

    def manualflag_clipzeros(self):
        """
        Function to flag any zero-valued data
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the manualflag step to flag the zero-valued data.

        # Zero valued data of fluxcal flagged?
        preflagfluxcalmanualflagclipzeros = get_param_def(self, 'preflag_fluxcal_manualflag_clipzeros', False)

        # Zero valued data of polcal flagged?
        preflagpolcalmanualflagclipzeros = get_param_def(self, 'preflag_polcal_manualflag_clipzeros', False)
        # Zero valued data of target beams flagged?
        preflagtargetbeamsmanualflagclipzeros = get_param_def(self, 'preflag_targetbeams_manualflag_clipzeros',
                                                              np.full(beams, False))

        if self.preflag_manualflag_clipzeros:
            logger.info('Flagging Zero-valued data')
            # Flag the Zero-valued data for the flux calibrator
            if preflagfluxcalmanualflagclipzeros and self.preflag_manualflag_fluxcal:
                logger.info('Zero-valued data for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()):
                    fc_clipzeros = 'flagdata(vis="' + self.get_fluxcal_path() + '", mode="clip", clipzeros=True, flagbackup=False)'
                    lib.run_casa([fc_clipzeros])
                    logger.debug('Flagged Zero-valued data for flux calibrator')
                    preflagfluxcalmanualflagclipzeros = True
                else:
                    preflagfluxcalmanualflagclipzeros = False
                    logger.warning('No flux calibrator dataset specified. Zero-valued data for flux calibrator '
                                   'dataset will not be flagged!')
            # Flag the Zero-valued data for the polarised calibrator
            if preflagpolcalmanualflagclipzeros and self.preflag_manualflag_polcal:
                logger.info('Zero-values data for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()):
                    pc_clipzeros = 'flagdata(vis="' + self.get_polcal_path() + '", mode="clip", clipzeros=True, flagbackup=False)'
                    lib.run_casa([pc_clipzeros])
                    logger.debug('Flagged Zero-valued data for polarised calibrator')
                    preflagpolcalmanualflagclipzeros = True
                else:
                    preflagpolcalmanualflagclipzeros = False
                    logger.warning('No polarised calibrator dataset specified. Zero-valued data for polariased '
                                   'calibrator dataset will not be flagged!')
            # Flag the Zero-valued for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = self.get_datasets()
                    logger.debug('Flagging Zero-valued data for all target beams')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.get_datasets(beams=beams)]
                    logger.debug('Flagging Zero-valued data for selected target beams')
                for vis, beam in datasets:
                    if preflagtargetbeamsmanualflagclipzeros[int(beam)]:
                        logger.info('Zero-valued data for target beam ' + beam + ' were already flagged')
                    else:
                        logger.debug('Zero-valued data for target beam ' + beam)
                        tg_clipzeros = 'flagdata(vis="' + str(vis) + '", mode="clip", clipzeros=True, flagbackup=False)'
                        lib.run_casa([tg_clipzeros])
                        preflagtargetbeamsmanualflagclipzeros[int(beam)] = True
            else:
                logger.warning('Target dataset not specified. Zero-values data for target beam dataset(s) will '
                               'not be flagged!')

        # Save the derived parameters for the auto-correlation flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_manualflag_clipzeros', preflagfluxcalmanualflagclipzeros)
        subs_param.add_param(self, 'preflag_polcal_manualflag_clipzeros', preflagpolcalmanualflagclipzeros)
        subs_param.add_param(self, 'preflag_targetbeams_manualflag_clipzeros', preflagtargetbeamsmanualflagclipzeros)

    def aoflagger_bandpass(self):
        """
        Creates a bandpass from a known frequency behaviour of the telescope. This is usually applied on the fly
        when using aoflagger.
        """
        subs_setinit.setinitdirs(self)

        # Create the parameters for the parameter file for the bandpass step of the AOFLagger step

        # Bandpass successfully derived
        preflagaoflaggerbandpassstatus = get_param_def(self, 'preflag_aoflagger_bandpass_status', False)

        if self.preflag_aoflagger_bandpass:
            # Check if bandpass was already derived and bandpass table is available
            if os.path.isfile(self.get_fluxcal_path()[:-3] + '_Bpass.txt'):
                logger.info('Preliminary bandpass table was already derived')
                preflagaoflaggerbandpassstatus = True
            # If not, calculate the bandpass for the setup of the observation using the flux calibrator
            elif not preflagaoflaggerbandpassstatus:
                if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                    create_bandpass(self.get_fluxcal_path(), self.get_fluxcal_path()[:-3] + '_Bpass.txt')
                    if os.path.isfile(self.get_fluxcal_path()[:-3] + '_Bpass.txt'):
                        preflagaoflaggerbandpassstatus = True
                        logger.info('Derived preliminary bandpass table for AOFlagging')
                    else:
                        error = 'Preliminary bandpass table for flux calibrator was not derived successfully!'
                        logger.error(error)
                        raise ApercalException(error)
                else:
                    error = 'Bandpass calibrator not specified or dataset not available!'
                    logger.error(error)
                    raise ApercalException(error)
            else:
                error = 'Bandpass table not available. Preliminary bandpass cannot be applied'
                logger.error(error)
                raise ApercalException(error)

        # Save the derived parameters for the AOFlagger bandpass status to the parameter file

        subs_param.add_param(self, 'preflag_aoflagger_bandpass_status', preflagaoflaggerbandpassstatus)

    def aoflagger_flag(self):
        """
        Uses the aoflagger to flag the calibrators and the target data set(s). Uses the bandpass corrected
        visibilities if bandpass was derived and applied successfully beforehand.
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the bandpass step of the AOFlagger step

        # AOFlagged the flux calibrator?
        preflagaoflaggerfluxcalflag = get_param_def(self, 'preflag_aoflagger_fluxcal_flag_status', False)

        # AOFlagged the polarised calibrator?
        preflagaoflaggerpolcalflag = get_param_def(self, 'preflag_aoflagger_polcal_flag_status', False)

        # AOFlagged the target beams?
        preflagaoflaggertargetbeamsflag = get_param_def(self, 'preflag_aoflagger_targetbeams_flag_status',
                                                        np.full(beams, False))

        base_cmd = 'aoflagger -strategy ' + ao_strategies + '/' + self.preflag_aoflagger_fluxcalstrat
        # Suppress logging of lines that start with this (to prevent 1000s of lines of logging)
        strip_prefixes = ['Channel ']
        if self.preflag_aoflagger:
            # Flag the flux calibrator with AOFLagger
            if self.preflag_aoflagger_fluxcal and self.fluxcal != '':
                if not preflagaoflaggerfluxcalflag:
                    if os.path.isdir(self.get_fluxcal_path()) and self.preflag_aoflagger_fluxcalstrat != '':
                        logger.info('Using AOFlagger to flag flux calibrator dataset')
                        # Check if bandpass table was derived successfully
                        preflagaoflaggerbandpassstatus = get_param_def(self, 'preflag_aoflagger_bandpass_status', True)
                        if self.preflag_aoflagger_bandpass and preflagaoflaggerbandpassstatus:
                            lib.basher(base_cmd + ' -bandpass ' + self.get_fluxcal_path()[:-3] + '_Bpass.txt ' + self.get_fluxcal_path(),
                                       prefixes_to_strip=strip_prefixes)
                            logger.debug('Used AOFlagger to flag flux calibrator with preliminary bandpass applied')
                            preflagaoflaggerfluxcalflag = True
                        elif self.preflag_aoflagger_bandpass and not preflagaoflaggerbandpassstatus:
                            lib.basher(base_cmd + ' ' + self.get_fluxcal_path(),
                                       prefixes_to_strip=strip_prefixes)
                            logger.warning('Used AOFlagger to flag flux calibrator without preliminary bandpass '
                                           'applied. Better results are usually obtained with a preliminary bandpass applied.')
                            preflagaoflaggerfluxcalflag = True
                        elif not self.preflag_aoflagger_bandpass:
                            lib.basher(base_cmd + ' ' + self.get_fluxcal_path(), prefixes_to_strip=strip_prefixes)
                            logger.warning('Used AOFlagger to flag flux calibrator without preliminary bandpass '
                                           'applied. Better results are usually obtained with a preliminary bandpass applied.')
                            preflagaoflaggerfluxcalflag = True
                    else:
                        error = 'Flux calibrator dataset or strategy not defined properly or dataset' \
                                'not available. Not AOFlagging flux calibrator.'
                        logger.error(error)
                        raise ApercalException(error)
                else:
                    logger.info('Flux calibrator was already flagged with AOFlagger!')
            # Flag the polarised calibrator with AOFlagger
            if self.preflag_aoflagger_polcal and self.polcal != '':
                if not preflagaoflaggerpolcalflag:
                    if not os.path.isdir(self.get_polcal_path()):
                        error = "can't find polarisation calibrator dataset: %s".format(self.get_polcal_path())
                        logger.error(error)
                        raise ApercalException(error)

                    if self.preflag_aoflagger_polcalstrat == '':
                        error = 'Polarised strategy not defined'
                        logger.error(error)
                        raise ApercalException(error)

                    logger.info('Using AOFlagger to flag polarised calibrator dataset.')
                    # Check if bandpass was applied successfully
                    # Check if bandpass table was derived successfully
                    preflagaoflaggerbandpassstatus = get_param_def(self, 'preflag_aoflagger_bandpass_status', False)
                    ao_base_cmd = 'aoflagger -strategy ' + ao_strategies + '/' + self.preflag_aoflagger_polcalstrat
                    if self.preflag_aoflagger_bandpass and preflagaoflaggerbandpassstatus:
                        lib.basher(ao_base_cmd + ' -bandpass ' + self.get_fluxcal_path()[:-3] + '_Bpass.txt ' + self.get_polcal_path(),
                                   prefixes_to_strip=strip_prefixes)
                        logger.debug('Used AOFlagger to flag polarised calibrator with preliminary bandpass applied.')
                        preflagaoflaggerpolcalflag = True
                    elif self.preflag_aoflagger_bandpass and not preflagaoflaggerbandpassstatus:
                        lib.basher(ao_base_cmd + ' ' + self.get_polcal_path(), prefixes_to_strip=strip_prefixes)
                        logger.warning('Used AOFlagger to flag polarised calibrator without preliminary bandpass '
                                       'applied. Better results are usually obtained with a preliminary bandpass applied.')
                        preflagaoflaggerpolcalflag = True
                    elif not self.preflag_aoflagger_bandpass:
                        lib.basher(ao_base_cmd + ' ' + self.get_polcal_path(), prefixes_to_strip=strip_prefixes)
                        logger.info('Used AOFlagger to flag polarised calibrator without preliminary bandpass '
                                    'applied. Better results are usually obtained with a preliminary bandpass applied.')
                        preflagaoflaggerpolcalflag = True

                else:
                    logger.info('Polarised calibrator was already flagged with AOFlagger!')

            # Flag the target beams with AOFlagger
            if self.preflag_aoflagger_target and self.target != '':
                if self.preflag_aoflagger_targetstrat != '':
                    logger.info('Using AOFlagger to flag selected target beam dataset(s)')
                    # Check if parameter exists already and bandpass was applied successfully
                    # Check if bandpass table was derived successfully
                    preflagaoflaggerbandpassstatus = get_param_def(self, 'preflag_aoflagger_bandpass_status', False)
                    if self.preflag_aoflagger_targetbeams == 'all':  # Create a list of target beams
                        datasets = self.get_datasets()
                        logger.info('AOFlagging all target beams')
                    else:
                        beams = self.preflag_aoflagger_targetbeams.split(",")
                        datasets = [self.get_datasets(beams=beams)]
                        logger.info('AOFlagging all selected target beam(s)')
                    for vis, beam in datasets:
                        base_cmd = 'aoflagger -strategy ' + ao_strategies + '/' + self.preflag_aoflagger_targetstrat
                        if not preflagaoflaggertargetbeamsflag[int(beam)]:
                            if self.preflag_aoflagger_bandpass and preflagaoflaggerbandpassstatus:
                                lib.basher(base_cmd + ' -bandpass ' + self.get_fluxcal_path()[:-3] + '_Bpass.txt ' + vis,
                                           prefixes_to_strip=strip_prefixes)
                                logger.debug('Used AOFlagger to flag target beam %s with preliminary '
                                             'bandpass applied'.format(beam))
                                preflagaoflaggertargetbeamsflag[int(beam)] = True
                            elif self.preflag_aoflagger_bandpass and not preflagaoflaggerbandpassstatus:
                                lib.basher(base_cmd + ' ' + vis, prefixes_to_strip=strip_prefixes)
                                logger.warning('Used AOFlagger to flag target beam %s without preliminary bandpass '
                                               'applied. Better results are usually obtained with a preliminary '
                                               'bandpass applied.'.format(beam))
                                preflagaoflaggertargetbeamsflag[int(beam)] = True
                            elif not self.preflag_aoflagger_bandpass:
                                lib.basher(base_cmd + ' ' + vis, prefixes_to_strip=strip_prefixes)
                                logger.warning('Used AOFlagger to flag target beam %s without preliminary bandpass '
                                               'applied. Better results are usually obtained with a preliminary '
                                               'bandpass applied.'.format(beam))
                                preflagaoflaggertargetbeamsflag[int(beam)] = True
                        else:
                            logger.info('Target beam ' + beam + ' was already flagged with AOFlagger!')
                else:
                    error = 'Target beam dataset(s) or strategy not defined properly. Not AOFlagging ' \
                            'target beam dataset(s).'
                    logger.error(error)
                    raise ApercalException(error)

        # Save the derived parameters for the AOFlagger status to the parameter file
        subs_param.add_param(self, 'preflag_aoflagger_fluxcal_flag_status', preflagaoflaggerfluxcalflag)
        subs_param.add_param(self, 'preflag_aoflagger_polcal_flag_status', preflagaoflaggerpolcalflag)
        subs_param.add_param(self, 'preflag_aoflagger_targetbeams_flag_status', preflagaoflaggertargetbeamsflag)

    def temp_del(self):
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_antenna')
        subs_param.del_param(self, 'preflag_polcal_manualflag_antenna')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_corr')
        subs_param.del_param(self, 'preflag_polcal_manualflag_corr')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_baseline')
        subs_param.del_param(self, 'preflag_polcal_manualflag_baseline')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_channel')
        subs_param.del_param(self, 'preflag_polcal_manualflag_channel')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_time')
        subs_param.del_param(self, 'preflag_polcal_manualflag_time')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_clipzeros')
        subs_param.del_param(self, 'preflag_polcal_manualflag_clipzeros')

    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during PREFLAG. No detailed summary
        is available for PREFLAG

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        """

        beams = 37

        # Load the parameters from the parameter file

        FS = subs_param.get_param(self, 'preflag_fluxcal_shadow')
        FG = subs_param.get_param(self, 'preflag_fluxcal_ghosts')
        FE = subs_param.get_param(self, 'preflag_fluxcal_edges')
        FMAu = subs_param.get_param(self, 'preflag_fluxcal_manualflag_auto')
        FMAnt = subs_param.get_param(self, 'preflag_fluxcal_manualflag_antenna')
        FMC = subs_param.get_param(self, 'preflag_fluxcal_manualflag_corr')
        FMB = subs_param.get_param(self, 'preflag_fluxcal_manualflag_baseline')
        FMCh = subs_param.get_param(self, 'preflag_fluxcal_manualflag_channel')
        FMt = subs_param.get_param(self, 'preflag_fluxcal_manualflag_time')
        FCz = subs_param.get_param(self, 'preflag_fluxcal_manualflag_clipzeros')
        FAO = subs_param.get_param(self, 'preflag_aoflagger_fluxcal_flag_status')

        PS = subs_param.get_param(self, 'preflag_polcal_shadow')
        PG = subs_param.get_param(self, 'preflag_polcal_ghosts')
        PE = subs_param.get_param(self, 'preflag_polcal_edges')
        PMAu = subs_param.get_param(self, 'preflag_polcal_manualflag_auto')
        PMAnt = subs_param.get_param(self, 'preflag_polcal_manualflag_antenna')
        PMC = subs_param.get_param(self, 'preflag_polcal_manualflag_corr')
        PMB = subs_param.get_param(self, 'preflag_polcal_manualflag_baseline')
        PMCh = subs_param.get_param(self, 'preflag_polcal_manualflag_channel')
        PMt = subs_param.get_param(self, 'preflag_polcal_manualflag_time')
        PCz = subs_param.get_param(self, 'preflag_polcal_manualflag_clipzeros')
        PAO = subs_param.get_param(self, 'preflag_aoflagger_polcal_flag_status')

        TS = subs_param.get_param(self, 'preflag_targetbeams_shadow')
        TG = subs_param.get_param(self, 'preflag_targetbeams_ghosts')
        TE = subs_param.get_param(self, 'preflag_targetbeams_edges')
        TMAu = subs_param.get_param(self, 'preflag_targetbeams_manualflag_auto')
        TMAnt = subs_param.get_param(self, 'preflag_targetbeams_manualflag_antenna')
        TMC = subs_param.get_param(self, 'preflag_targetbeams_manualflag_corr')
        TMB = subs_param.get_param(self, 'preflag_targetbeams_manualflag_baseline')
        TMCh = subs_param.get_param(self, 'preflag_targetbeams_manualflag_channel')
        TMt = subs_param.get_param(self, 'preflag_targetbeams_manualflag_time')
        TCz = subs_param.get_param(self, 'preflag_targetbeams_manualflag_clipzeros')
        TAO = subs_param.get_param(self, 'preflag_aoflagger_targetbeams_flag_status')

        # Create the data frame

        beam_range = range(beams)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = ['Flux calibrator (' + self.fluxcal[:-3] + ')', 'Polarised calibrator (' + self.polcal[:-3] + ')'] + dataset_beams

        all_s = np.full(39, False)
        all_s[0] = FS
        all_s[1] = PS
        all_s[2:] = TS

        all_g = np.full(39, False)
        all_g[0] = FG
        all_g[1] = PG
        all_g[2:] = TG

        all_e = np.full(39, False)
        all_e[0] = FE
        all_e[1] = PE
        all_e[2:] = TE

        all_MAu = np.full(39, False)
        all_MAu[0] = FMAu
        all_MAu[1] = PMAu
        all_MAu[2:] = TMAu

        all_MAnt = np.concatenate((FMAnt, PMAnt, TMAnt), axis=0)
        all_MC = np.concatenate((FMC, PMC, TMC), axis=0)
        all_MB = np.concatenate((FMB, PMB, TMB), axis=0)
        all_MCh = np.concatenate((FMCh, PMCh, TMCh), axis=0)
        all_Mt = np.concatenate((FMt, PMt, TMt), axis=0)

        all_Cz = np.full(39, False)
        all_Cz[0] = FCz
        all_Cz[1] = PCz
        all_Cz[3] = TCz

        all_AO = np.full(39, False)
        all_AO[0] = FAO
        all_AO[1] = PAO
        all_AO[2:] = TAO

        df_shadow = pd.DataFrame(np.ndarray.flatten(all_s), index=dataset_indices, columns=['Shadow'])
        df_ghosts = pd.DataFrame(np.ndarray.flatten(all_g), index=dataset_indices, columns=['Ghosts'])
        df_edges = pd.DataFrame(np.ndarray.flatten(all_e), index=dataset_indices, columns=['Edges'])
        df_auto = pd.DataFrame(np.ndarray.flatten(all_MAu), index=dataset_indices, columns=['Auto'])
        df_ant = pd.DataFrame(all_MAnt, index=dataset_indices, columns=['Antenna'])
        df_corr = pd.DataFrame(all_MC, index=dataset_indices, columns=['Correlation'])
        df_baseline = pd.DataFrame(all_MB, index=dataset_indices, columns=['Baseline'])
        df_channel = pd.DataFrame(all_MCh, index=dataset_indices, columns=['Channel'])
        df_time = pd.DataFrame(all_Mt, index=dataset_indices, columns=['Time'])
        df_clipzeros = pd.DataFrame(np.ndarray.flatten(all_Cz), index=dataset_indices, columns=['clipzeros'])
        df_AO = pd.DataFrame(np.ndarray.flatten(all_AO), index=dataset_indices, columns=['AOFlagger'])

        df = pd.concat(
            [df_shadow, df_ghosts, df_edges, df_auto, df_ant, df_corr, df_baseline, df_channel, df_time, df_AO], axis=1)

        return df

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        logger.warning('Deleting all raw data products and their directories. You will need to '
                       'start with the PREPARE step again!')
        subs_managefiles.director(self, 'ch', self.basedir)
        deldirs = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir)
        for dir_ in deldirs:
            subs_managefiles.director(self, 'rm', dir_)
        logger.warning(' Deleting all parameter file entries for PREPARE and PREFLAG module')
        subs_param.del_param(self, 'prepare_fluxcal_requested')
        subs_param.del_param(self, 'prepare_fluxcal_diskstatus')
        subs_param.del_param(self, 'prepare_fluxcal_altastatus')
        subs_param.del_param(self, 'prepare_fluxcal_copystatus')
        subs_param.del_param(self, 'prepare_fluxcal_rejreason')
        subs_param.del_param(self, 'prepare_polcal_requested')
        subs_param.del_param(self, 'prepare_polcal_diskstatus')
        subs_param.del_param(self, 'prepare_polcal_altastatus')
        subs_param.del_param(self, 'prepare_polcal_copystatus')
        subs_param.del_param(self, 'prepare_polcal_rejreason')
        subs_param.del_param(self, 'prepare_targetbeams_requested')
        subs_param.del_param(self, 'prepare_targetbeams_diskstatus')
        subs_param.del_param(self, 'prepare_targetbeams_altastatus')
        subs_param.del_param(self, 'prepare_targetbeams_copystatus')
        subs_param.del_param(self, 'prepare_targetbeams_rejreason')

        subs_param.del_param(self, 'preflag_fluxcal_shadow')
        subs_param.del_param(self, 'preflag_polcal_shadow')
        subs_param.del_param(self, 'preflag_targetbeams_shadow')
        subs_param.del_param(self, 'preflag_fluxcal_edges')
        subs_param.del_param(self, 'preflag_polcal_edges')
        subs_param.del_param(self, 'preflag_targetbeams_edges')
        subs_param.del_param(self, 'preflag_fluxcal_ghosts')
        subs_param.del_param(self, 'preflag_polcal_ghosts')
        subs_param.del_param(self, 'preflag_targetbeams_ghosts')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_auto')
        subs_param.del_param(self, 'preflag_polcal_manualflag_auto')
        subs_param.del_param(self, 'preflag_targetbeams_manualflag_auto')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_antenna')
        subs_param.del_param(self, 'preflag_polcal_manualflag_antenna')
        subs_param.del_param(self, 'preflag_targetbeams_manualflag_antenna')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_corr')
        subs_param.del_param(self, 'preflag_polcal_manualflag_corr')
        subs_param.del_param(self, 'preflag_targetbeams_manualflag_corr')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_baseline')
        subs_param.del_param(self, 'preflag_polcal_manualflag_baseline')
        subs_param.del_param(self, 'preflag_targetbeams_manualflag_baseline')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_channel')
        subs_param.del_param(self, 'preflag_polcal_manualflag_channel')
        subs_param.del_param(self, 'preflag_targetbeams_manualflag_channel')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_time')
        subs_param.del_param(self, 'preflag_polcal_manualflag_time')
        subs_param.del_param(self, 'preflag_targetbeams_manualflag_time')
        subs_param.del_param(self, 'preflag_fluxcal_manualflag_clipzeros')
        subs_param.del_param(self, 'preflag_polcal__manualflag_clipzeros')
        subs_param.del_param(self, 'preflag_targetbeams_manualflag_clipzeros')
        subs_param.del_param(self, 'preflag_aoflagger_bandpass_status')
        subs_param.del_param(self, 'preflag_aoflagger_fluxcal_flag_status')
        subs_param.del_param(self, 'preflag_aoflagger_polcal_flag_status')
        subs_param.del_param(self, 'preflag_aoflagger_targetbeams_flag_status')
