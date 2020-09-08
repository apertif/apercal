import logging

import numpy as np
import pandas as pd
import json
import os
from os import path
from time import time

import casacore.tables as pt

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs.msutils import get_nchan
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
    preflag_manualflag_auto = None
    preflag_manualflag_antenna = None
    preflag_manualflag_corr = None
    preflag_manualflag_baseline = None
    preflag_manualflag_channel = None
    preflag_manualflag_time = None
    preflag_manualflag_clipzeros = None
    preflag_manualflag_file = ''
    preflag_manualflag_file_path = ''
    preflag_aoflagger = None
    preflag_aoflagger_bandpass = None
    preflag_aoflagger_fluxcal = None
    preflag_aoflagger_polcal = None
    preflag_aoflagger_target = None
    preflag_aoflagger_fluxcalstrat = None
    preflag_aoflagger_polcalstrat = None
    preflag_aoflagger_targetstrat = None
    preflag_aoflagger_threads = None
    preflag_aoflagger_use_interval = None
    preflag_aoflagger_delta_interval = None
    preflag_aoflagger_max_interval = None
    preflag_aoflagger_version = ''

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
        logger.info('Beam ' + self.beam + ': Starting Pre-flagging step')

        logger.info('Beam ' + self.beam + ': Running manualflag for {0}'.format(self.target))
        start_time = time()
        self.manualflag()
        logger.info('Beam ' + self.beam + ': Running manualflag for {0} ... Done ({1:.0f}s)'.format(self.target, time() - start_time))

        if self.fluxcal != '':
            query = "SELECT GNFALSE(FLAG) == 0 AS all_flagged, " + \
                    "GNTRUE(FLAG) == 0 AS all_unflagged FROM " + self.get_fluxcal_path()
            query_result = pt.taql(query)
            logger.debug('Beam ' + self.beam + ': All visibilities     flagged before aoflag: ' + str(query_result[0]["all_flagged"]))
            logger.debug('Beam ' + self.beam + ': All visibilities not flagged before aoflag: ' + str(query_result[0]["all_unflagged"]))

        logger.info('Beam ' + self.beam + ': Running aoflagger tasks for {0}'.format(self.target))
        start_time = time()
        self.aoflagger()
        logger.info('Beam ' + self.beam + ': Running aoflagger tasks for {0} ... Done ({1:.0f}s)'.format(self.target, time() - start_time))

        if self.fluxcal != '':
            query = "SELECT GNFALSE(FLAG) == 0 AS all_flagged, " + \
                    "GNTRUE(FLAG) == 0 AS all_unflagged FROM " + self.get_fluxcal_path()
            query_result = pt.taql(query)
            logger.debug('Beam ' + self.beam + ': All visibilities     flagged after aoflag: ' + str(query_result[0]["all_flagged"]))
            logger.debug('Beam ' + self.beam + ': All visibilities not flagged after aoflag: ' + str(query_result[0]["all_unflagged"]))

        logger.info('Beam ' + self.beam + ': Running shadow for {0}'.format(self.target))
        start_time = time()
        self.shadow()
        logger.info('Beam ' + self.beam + ': Running shadow for {0} ... Done ({1:.0f}s)'.format(self.target, time() - start_time))

        logger.info('Beam ' + self.beam + ': Running edge for {0}'.format(self.target))
        start_time = time()
        self.edges()
        logger.info('Beam ' + self.beam + ': Running edge for {0} ... Done ({1:.0f}s)'.format(self.target, time() - start_time))

        logger.info('Beam ' + self.beam + ': Running ghosts for {0}'.format(self.target))
        start_time = time()
        self.ghosts()
        logger.info('Beam ' + self.beam + ': Running ghosts for {0} ... Done ({1:.0f}s)'.format(self.target, time() - start_time))

        logger.info('Beam ' + self.beam + ': Pre-flagging step done')


    def get_bandpass_path(self):
        if self.subdirification:
            return path.join(self.basedir, self.beam, self.rawsubdir, 'Bpass.txt')
        else:
            return path.join(os.getcwd(), 'Bpass.txt')


    def shadow(self):
        """
        Flag all data sets for shadowed antennas using drivecasa and the CASA task flagdata
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        logger.debug('Beam ' + self.beam + ': Shadowed antenna flagging step started')

        # Create the parameters for the parameter file for the shadowing status

        # Is the fluxcal shadow flagged?
        preflagfluxcalshadow = get_param_def(self, pbeam + '_fluxcal_shadow', False)

        # Is the polcal shadow flagged?
        preflagpolcalshadow = get_param_def(self, pbeam + '_polcal_shadow', False)

        # Are the target beams shadow flagged?
        preflagtargetbeamsshadow = get_param_def(self, pbeam + '_targetbeams_shadow', False)

        # Flag shadowed antennas

        if self.preflag_shadow:
            logger.info('Beam ' + self.beam + ': Flagging shadowed antennas')
            # Flag the flux calibrator
            if preflagfluxcalshadow:
                logger.info('Beam ' + self.beam + ': Shadowed antenna(s) for flux calibrator were already flagged')
            else:
                if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                    logger.debug('Beam ' + self.beam + ': Flagging shadowed antennas for flux calibrator')
                    fc_shadow = 'flagdata(vis="' + self.get_fluxcal_path() + '", mode="shadow", flagbackup=False)'
                    lib.run_casa([fc_shadow])
                    preflagfluxcalshadow = True
                else:
                    logger.warning('Beam ' + self.beam + ': Flux calibrator dataset not available or dataset not specified. Not flagging '
                                   'shadowed antennas for flux calibrator')
                    preflagfluxcalshadow = False
            # Flag the polarised calibrator
            if preflagpolcalshadow:
                logger.info('Beam ' + self.beam + ': Shadowed antenna(s) for polarised calibrator were already flagged')
            else:
                if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                    logger.debug('Beam ' + self.beam + ': Flagging shadowed antennas for polarised calibrator')
                    pc_shadow = 'flagdata(vis="' + self.get_polcal_path() + '", mode="shadow", flagbackup=False)'
                    lib.run_casa([pc_shadow])
                    preflagpolcalshadow = True
                else:
                    logger.warning('Beam ' + self.beam + ': Polarised calibrator dataset not available or dataset not specified. Not '
                                   'flagging shadowed antennas for polarised calibrator')
                    preflagpolcalshadow = False
            # Flag the target beams
            if preflagtargetbeamsshadow:
                logger.info('Beam ' + self.beam + ': Shadowed antenna(s) for target were already flagged')
            else:
                if self.target !='' and os.path.isdir(self.get_target_path()):
                    logger.debug('Beam ' + self.beam + ': Flagging shadowed antennas for target')
                    tg_shadow = 'flagdata(vis="' + self.get_target_path() + '", mode="shadow", flagbackup=False)'
                    lib.run_casa([tg_shadow])
                    preflagtargetbeamsshadow = True
                else:
                    logger.warning('Beam ' + self.beam + ': Target dataset not available or dataset not specified. Not '
                                   'flagging shadowed antennas for polarised calibrator')
                    preflagtargetbeamsshadow = False
        else:
            logger.warning('Beam ' + self.beam + ': Shadowed antenna(s) are not flagged!')
        logger.debug('Beam ' + self.beam + ': Shadowed antenna flagging step done')

        # Save the derived parameters for the shadow flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_shadow', preflagfluxcalshadow)
        subs_param.add_param(self, pbeam + '_polcal_shadow', preflagpolcalshadow)
        subs_param.add_param(self, pbeam + '_targetbeams_shadow', preflagtargetbeamsshadow)


    def edges(self):
        """
        Flag the edges of the subbands
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        logger.debug('Beam ' + self.beam + ': Starting to flag the edges of the subbands')

        # Create the parameters for the parameter file for the shadowing status

        # Edges of fluxcal flagged?
        preflagfluxcaledges = get_param_def(self, pbeam + '_fluxcal_edges', False)

        # Edges of polcal flagged?
        preflagpolcaledges = get_param_def(self, pbeam + '_polcal_edges', False)

        # Edges of target beams flagged?
        preflagtargetbeamsedges = get_param_def(self, pbeam + '_targetbeams_edges', False)

        if self.preflag_edges:
            logger.info('Beam ' + self.beam + ': Flagging subband edges')
            # Flag the flux calibrator
            if preflagfluxcaledges:
                logger.info('Beam ' + self.beam + ': Subband edges for flux calibrator were already flagged')
            else:
                if self.fluxcal != '' and os.path.isdir(
                        self.get_fluxcal_path()):
                    # Flag the subband edges of the flux calibrator data set
                    logger.debug('Beam ' + self.beam + ': Flagging subband edges for flux calibrator')
                    # Get the number of channels of the flux calibrator data set
                    nchannel = get_nchan(self.get_fluxcal_path())
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
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Subband edges of flux calibrator '
                                   'will not be flagged!')
                    preflagfluxcaledges = False
            # Flag the polarised calibrator
            if preflagpolcaledges:
                logger.info('Beam ' + self.beam + ': Subband edges for polarised calibrator were already flagged')
            else:
                if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                    # Flag the subband edges of the polarised calibrator data set
                    logger.debug('Beam ' + self.beam + ': Flagging subband edges for polarised calibrator #')
                    # Get the number of channels of the polarised calibrator data set
                    nchannel = get_nchan(self.get_polcal_path())
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
                    logger.warning('Beam ' + self.beam + ': No polarised calibrator dataset specified. Subband edges of polarised '
                                   'calibrator will not be flagged!')
                    preflagpolcaledges = False
            if preflagtargetbeamsedges:
                logger.info('Beam ' + self.beam + ': Subband edges for target dataset were already flagged')
            else:
                if self.target != '' and os.path.isdir(self.get_target_path()):
                    # Flag the subband edges of the the target beam dataset
                    logger.debug('Beam ' + self.beam + ': Flagging subband edges for all target beams')
                    nchannel = get_nchan(self.get_target_path())
                    # Calculate the subband edges for each target beam data set
                    a = range(0, nchannel, 64)
                    b = range(1, nchannel, 64)
                    c = range(63, nchannel, 64)
                    l = a + b + c
                    m = ';'.join(str(ch) for ch in l)
                    tg_edges_flagcmd = 'flagdata(vis="' + self.get_target_path() + '", spw="0:' + m + '", flagbackup=False)'
                    lib.run_casa([tg_edges_flagcmd])
                    preflagtargetbeamsedges = True
                else:
                    logger.warning('Beam ' + self.beam + ': No target dataset specified. Subband edges of target dataset will not be flagged!')
                    preflagtargetbeamsedges = False
        else:
            logger.warning('Beam ' + self.beam + ': Subband edges are not flagged!')
        logger.debug('Beam ' + self.beam + ': Finished flagging subband edges')

        # Save the derived parameters for the subband edges flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_edges', preflagfluxcaledges)
        subs_param.add_param(self, pbeam + '_polcal_edges', preflagpolcaledges)
        subs_param.add_param(self, pbeam + '_targetbeams_edges', preflagtargetbeamsedges)

    def ghosts(self):
        """
        Flag the ghosts of each subband at channel 16 and 48
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        logger.debug('Beam ' + self.beam + ': Starting to flag the ghost channels')

        # Create the parameters for the parameter file for the shadowing status

        # Ghosts of fluxcal flagged?
        preflagfluxcalghosts = get_param_def(self, pbeam + '_fluxcal_ghosts', False)

        # Ghosts of polcal flagged?
        preflagpolcalghosts = get_param_def(self,  pbeam + '_polcal_ghosts', False)

        # Ghosts of target beams flagged?
        preflagtargetbeamsghosts = get_param_def(self,  pbeam + '_targetbeams_ghosts', False)

        if self.preflag_ghosts:
            logger.info('Beam ' + self.beam + ': Flagging ghost channels')
            # Flag the ghost channels in the flux calibrator
            if preflagfluxcalghosts:
                logger.info('Beam ' + self.beam + ': Ghost channels for flux calibrator were already flagged')
            else:
                if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                    # Flag the ghosts in the flux calibrator data set
                    logger.debug('Beam ' + self.beam + ': Flagging ghost channels for flux calibrator')
                    # Get the number of channels of the flux calibrator data set
                    nchannel = get_nchan(self.get_fluxcal_path())
                    # Calculate the ghost positions for the flux calibrator data set
                    a = range(16, nchannel, 64)
                    b = range(48, nchannel, 64)
                    l = a + b
                    m = ';'.join(str(ch) for ch in l)
                    fc_ghosts_flagcmd = 'flagdata(vis="' + self.get_fluxcal_path() + '", spw="0:' + m + '", flagbackup=False)'
                    lib.run_casa([fc_ghosts_flagcmd])
                    preflagfluxcalghosts = True
                else:
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Ghosts in flux calibrator dataset '
                                   'will not be flagged!')
                    preflagfluxcalghosts = False
            # Flag the ghost channels in the polarised calibrator
            if preflagpolcalghosts:
                logger.info('Beam ' + self.beam + ': Ghost channels for polarised calibrator were already flagged')
            else:
                if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                    # Flag the ghosts in the polarised calibrator data set
                    logger.debug('Beam ' + self.beam + ': Flagging ghost channels for polarised calibrator')
                    # Get the number of channels of the polarised calibrator data set
                    nchannel = get_nchan(self.get_polcal_path())
                    # Calculate the subband edges of the polarised calibrator data set
                    a = range(16, nchannel, 64)
                    b = range(48, nchannel, 64)
                    l = a + b
                    m = ';'.join(str(ch) for ch in l)
                    pc_ghosts_flagcmd = 'flagdata(vis="' + self.get_polcal_path() + '", spw="0:' + m + '", flagbackup=False)'
                    lib.run_casa([pc_ghosts_flagcmd])
                    preflagpolcalghosts = True
                else:
                    logger.warning('Beam ' + self.beam + ': No polarised calibrator dataset specified. Ghosts in polarised calibrator '
                                   'will not be flagged!')
                    preflagpolcalghosts = False

            if preflagtargetbeamsghosts:
                logger.info('Beam ' + self.beam + ': Ghost channels for target dataset were already flagged')
            else:
                if self.target != '' and os.path.isdir(self.get_target_path()):
                    # Flag the ghosts in the target beam dataset
                    logger.debug('Beam ' + self.beam + ': Flagging ghost channels for target dataset')
                    nchannel = get_nchan(self.get_target_path())
                    # Calculate the ghost channels for each target beam data set
                    a = range(16, nchannel, 64)
                    b = range(48, nchannel, 64)
                    l = a + b
                    m = ';'.join(str(ch) for ch in l)
                    tg_ghosts_flagcmd = 'flagdata(vis="' + self.get_target_path() + '", spw="0:' + m + '", flagbackup=False)'
                    lib.run_casa([tg_ghosts_flagcmd])
                    preflagtargetbeamsghosts = True
                else:
                    logger.warning('Beam ' + self.beam + ': No target dataset specified. Ghosts in target dataset will not be flagged!')
                    preflagtargetbeamsghosts = False
        else:
            logger.warning('Beam ' + self.beam + ': Ghost channels are not flagged!')
        logger.debug('Beam ' + self.beam + ': Finished flagging ghost channels')

        # Save the derived parameters for the subband edges flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_ghosts', preflagfluxcalghosts)
        subs_param.add_param(self, pbeam + '_polcal_ghosts', preflagpolcalghosts)
        subs_param.add_param(self, pbeam + '_targetbeams_ghosts', preflagtargetbeamsghosts)


    def manualflag(self):
        """
        Use drivecasa and the CASA task flagdata to flag entire antennas, baselines, correlations etc. before doing
        any other calibration.
        """
        if self.preflag_manualflag:
            logger.info('Beam ' + self.beam + ': Manual flagging step started')
            self.manualflag_auto()
            self.manualflag_from_file()
            self.manualflag_antenna()
            self.manualflag_corr()
            self.manualflag_baseline()
            self.manualflag_channel()
            self.manualflag_time()
            self.manualflag_clipzeros()
            logger.info('Beam ' + self.beam + ': Manual flagging step done')


    def aoflagger(self):
        """
        Runs aoflagger on the datasets with the strategies given in the config-file. Creates and applies a preliminary
        bandpass before executing the strategy for better performance of the flagging routines. Strategies for
        calibrators and target fields normally differ.
        """
        if self.preflag_aoflagger:
            logger.info('Beam ' + self.beam + ': Pre-flagging with AOFlagger started')

            logger.info('Beam ' + self.beam + ': Running aoflagger bandpass for {0}'.format(
                self.target))
            start_time = time()
            self.aoflagger_bandpass()
            logger.info('Beam ' + self.beam + ': Running aoflagger bandpass for {0} ... Done ({1:.0f}s)'.format(
                self.target, time() - start_time))

            logger.info('Beam ' + self.beam + ': Running aoflagger flagging for {0}'.format(
                self.target))
            start_time = time()
            self.aoflagger_flag()
            logger.info('Beam ' + self.beam + ': Running aoflagger flagging for {0} ... Done ({1:.0f}s)'.format(
                self.target, time() - start_time))

            logger.info('Beam ' + self.beam + ': Pre-flagging with AOFlagger done')
        else:
            logger.warning('Beam ' + self.beam + ': No flagging with AOflagger done! Your data might be contaminated by RFI!')


    def manualflag_auto(self):
        """
        Function to flag the auto-correlations
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the manualflag step to flag the auto-correlations

        # Auto-correlations of fluxcal flagged?
        preflagfluxcalmanualflagauto = get_param_def(self, pbeam + '_fluxcal_manualflag_auto', False)

        # Auto-correlations of polcal flagged?
        preflagpolcalmanualflagauto = get_param_def(self, pbeam + '_polcal_manualflag_auto', False)

        # Auto-correlations of target beams flagged?
        preflagtargetbeamsmanualflagauto = get_param_def(self, pbeam + '_targetbeams_manualflag_auto', False)

        if self.preflag_manualflag_auto:
            logger.info('Beam ' + self.beam + ': Flagging auto-correlations')
            # Flag the auto-correlations for the flux calibrator
            if preflagfluxcalmanualflagauto and self.preflag_manualflag_fluxcal:
                logger.info('Beam ' + self.beam + ': Auto-correlations for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()) and self.fluxcal != '':
                    fc_auto = 'flagdata(vis="' + self.get_fluxcal_path() + '", autocorr=True, flagbackup=False)'
                    lib.run_casa([fc_auto])
                    logger.debug('Beam ' + self.beam + ': Flagged auto-correlations for flux calibrator')
                    preflagfluxcalmanualflagauto = True
                else:
                    preflagfluxcalmanualflagauto = False
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Auto-correlations for flux calibrator '
                                   'dataset will not be flagged!')
            # Flag the auto-correlations for the polarised calibrator
            if preflagpolcalmanualflagauto and self.preflag_manualflag_polcal:
                logger.info('Beam ' + self.beam + ': Auto-correlations for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()) and self.polcal != '':
                    pc_auto = 'flagdata(vis="' + self.get_polcal_path() + '", autocorr=True, flagbackup=False)'
                    lib.run_casa([pc_auto])
                    logger.debug('Beam ' + self.beam + ': Flagged auto-correlations for polarised calibrator')
                    preflagpolcalmanualflagauto = True
                else:
                    preflagpolcalmanualflagauto = False
                    logger.warning('Beam ' + self.beam + ': No polarised calibrator dataset specified. Auto-correlations for polariased '
                                   'calibrator dataset will not be flagged!')
            # Flag the auto-correlations for the target beams
            if preflagtargetbeamsmanualflagauto and self.preflag_manualflag_target:
                logger.info('Beam ' + self.beam + ': Auto-correlations for target beam dataset were already flagged')
            else:
                if self.preflag_manualflag_target and os.path.isdir(self.get_target_path()):
                    tg_auto = 'flagdata(vis="' + self.get_target_path() + '", autocorr=True, flagbackup=False)'
                    lib.run_casa([tg_auto])
                    logger.debug('Beam ' + self.beam + ': Flagging auto-correlations for target beam dataset')
                    preflagtargetbeamsmanualflagauto = True
                else:
                    preflagtargetbeamsmanualflagauto = False
                    logger.warning('Beam ' + self.beam + ': Target dataset not specified. Auto-correlations for target beam dataset will '
                               'not be flagged!')

        # Save the derived parameters for the auto-correlation flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_manualflag_auto', preflagfluxcalmanualflagauto)
        subs_param.add_param(self, pbeam + '_polcal_manualflag_auto', preflagpolcalmanualflagauto)
        subs_param.add_param(self, pbeam + '_targetbeams_manualflag_auto', preflagtargetbeamsmanualflagauto)

    def manualflag_from_file(self):
        """
        Function to flag based on commands from a file

        This provides a way to input more complex flagging commands.
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the manualflag step to flag individual antennas

        # Flagged already fluxcal this way?
        preflag_fluxcal_manualflag_from_file = get_param_def(self, pbeam + '_fluxcal_manualflag_from_file', False)
        # Flagged already polcal this way?
        preflag_polcal_manualflag_from_file = get_param_def(self, pbeam + '_polcal_manualflag_from_file', False)
        # Flagged already target this way?
        preflag_targetbeams_manualflag_from_file = get_param_def(self, pbeam + '_targetbeams_manualflag_from_file', False)

        # check if a file has been specified:
        if self.preflag_manualflag_file != '':
            # check if a path is set, if not assume the basedir
            if self.preflag_manualflag_file_path != '':
                file_location = os.path.join(self.preflag_manualflag_file_path, self.preflag_manualflag_file)
            else:
                file_location = os.path.join(self.basedir, self.preflag_manualflag_file)

            # check that the file exists
            if os.path.exists(file_location):
                logger.info("Beam {0}: Reading flagging commands from file {1}".format(self.beam, file_location))

                # read in the json file
                with open(file_location, "r") as fp:
                    flag_data = fp.read()

                # get the json dict
                # need to catch exception in case the json file is wrong
                try:
                    flag_data_json = json.loads(flag_data)
                except Exception as e:
                    logger.error("Beam {}: Reading in json file failed. Abort flagging".format(self.beam))
                    logger.exception(e)
                else:
                    logger.info("Beam {}: Successfully read in json file".format(self.beam))

                # set the key based on the given beam
                beam_key = "beam_{}".format(str(self.beam).zfill(2))
                #beam_flag_list = [int(beam.split("_")[-1]) for beam in flag_data_json['flaglist'].keys()]


                # check that there are flags for the current beam
                if flag_data_json['flaglist'].has_key(beam_key):
                    logger.info("Beam {}: Found flag commands for this beam".format(self.beam))

                    # get a list of flag commands based on the key
                    flag_list = flag_data_json['flaglist'][beam_key].keys()

                    # create a list of flag commands
                    flag_command_list = []
                    for flag_key  in flag_list:
                        flag_command = flag_data_json['flaglist'][beam_key][flag_key] + "\n"
                        flag_command_list.append(str(flag_command))

                    if len(flag_command_list) != 0:
                        casa_flag_file = os.path.join(self.rawdir, "casa_flag_list.txt")
                        # writing commands to file
                        try:
                            with open(casa_flag_file, "w") as fp:
                                fp.writelines(flag_command_list)
                        except Exception as e:
                            logger.error("Beam {0}: Writing file {1} with casa flagging commands failed".format(self.beam, casa_flag_file))
                            logger.exception(e)
                        else:
                            logger.info("Beam {0}: Successfully created file {1} with casa flag commands".format(self.beam, casa_flag_file))

                        # make sure there is a casa flag file
                        if os.path.exists(casa_flag_file):
                            # now run casa for fluxcal
                            if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()) and self.fluxcal != '':
                                #flagdata(vis, mode='list', inpfile=['onlineflags.txt' ,'otherflags.txt'])
                                flag_fluxcal = 'flagdata(vis="{0}", mode="list", inpfile="{1}", flagbackup=False)'.format(self.get_fluxcal_path(), casa_flag_file)
                                #flag_fluxcal = 'flagdata(vis="' + self.get_fluxcal_path() + '", mode="list"' + '", inpfile="' + casa_flag_file + ")'
                                lib.run_casa([flag_fluxcal])
                                logger.info('Beam {}: Flagged flux calibrator'.format(self.beam))
                                preflag_fluxcal_manualflag_from_file = True
                            else:
                                logger.warning('Beam {}: No flux calibrator dataset specified'.format(self.beam))

                            # now run casa for polcal
                            if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()) and self.polcal != '':
                                #flagdata(vis, mode='list', inpfile=['onlineflags.txt' ,'otherflags.txt'])
                                flag_polcal = 'flagdata(vis="{0}", mode="list", inpfile="{1}", flagbackup=False)'.format(
                                    self.get_polcal_path(), casa_flag_file)
                                lib.run_casa([flag_polcal])
                                logger.info('Beam {}: Flagged pol calibrator'.format(self.beam))
                                preflag_polcal_manualflag_from_file = True
                            else:
                                logger.warning('Beam {}: No pol calibrator dataset specified'.format(self.beam))

                            # now run casa for target
                            if self.preflag_manualflag_target and os.path.isdir(self.get_target_path()):
                                #flagdata(vis, mode='list', inpfile=['onlineflags.txt' ,'otherflags.txt'])
                                flag_target = 'flagdata(vis="{0}", mode="list", inpfile="{1}", flagbackup=False)'.format(
                                    self.get_target_path(), casa_flag_file)
                                lib.run_casa([flag_target])
                                logger.info(
                                            'Beam {}: Flagged target'.format(self.beam))
                                preflag_targetbeams_manualflag_from_file=True
                            else:
                                logger.warning(
                                            'Beam {}: No target dataset specified'.format(self.beam))
                        else:
                            logger.warning(
                                "Beam {0}: Flag file {1} does not exists.".format(self.beam, casa_flag_file))
                    else:
                        logger.warning("Beam {}: List of flag commands is empty.".format(self.beam))
                else:
                    logger.info("Beam {}: Did not find any flag commands for this beam. Moving on.".format(self.beam))
            else:
                # if it fails here, flagging should abort completey because it was set to use the flag file
                error = "Beam {0}: Did not find specified flagging file {1}. Abort flagging".format(self.beam, file_location)
                logger.error(error)
                raise RuntimeError(error)
        else:
            logger.info("Beam  {}: Did not flag using flagging commands from file".format(self.beam))

        # Save the derived parameters for the flagging from file to the parameter file
        subs_param.add_param(
            self, pbeam + '_fluxcal_manualflag_from_file', preflag_fluxcal_manualflag_from_file)
        subs_param.add_param(
            self, pbeam + '_polcal_manualflag_from_file', preflag_polcal_manualflag_from_file)
        subs_param.add_param(
            self, pbeam + '_targetbeams_manualflag_from_file', preflag_targetbeams_manualflag_from_file)

    def manualflag_antenna(self):
        """
        Function to flag complete antennas
        Antennas are named by their antenna names (e.g. 'RT2,RT3')
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the manualflag step to flag individual antennas

        # Flagged antennas of fluxcal?
        preflagfluxcalmanualflagantenna = get_param_def(self, pbeam + '_fluxcal_manualflag_antenna', np.full(1, '', dtype='U50'))

        # Flagged antennas of polcal?
        preflagpolcalmanualflagantenna = get_param_def(self, pbeam + '_polcal_manualflag_antenna', np.full(1, '', dtype='U50'))
        # Flagged antennas of target beams?
        preflagtargetbeamsmanualflagantenna = get_param_def(self, pbeam + '_targetbeams_manualflag_antenna', np.full(1, '', dtype='U50'))

        if self.preflag_manualflag_antenna != '':
            logger.info('Beam ' + self.beam + ': Flagging antenna(s) ' + self.preflag_manualflag_antenna)
            # Flag antenna(s) for flux calibrator
            if preflagfluxcalmanualflagantenna[0] == self.preflag_manualflag_antenna and self.preflag_manualflag_fluxcal:
                logger.info('Beam ' + self.beam + ': Antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()) and self.fluxcal != '':
                    fc_ant = 'flagdata(vis="' + self.get_fluxcal_path() + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                    lib.run_casa([fc_ant])
                    logger.debug('Beam ' + self.beam + ': Flagged antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator')
                    spltant = self.preflag_manualflag_antenna.split(',')
                    for ant in spltant:
                        if preflagfluxcalmanualflagantenna[0].find(ant) == -1:
                            if preflagfluxcalmanualflagantenna[0] == '':
                                preflagfluxcalmanualflagantenna[0] = ant
                            else:
                                preflagfluxcalmanualflagantenna[0] = preflagfluxcalmanualflagantenna[0] + ',' + ant
                else:
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Specified antenna(s) for flux calibrator dataset will not be flagged!')
            # Flag antenna(s) for polarised calibrator
            if preflagpolcalmanualflagantenna[0] == self.preflag_manualflag_antenna and self.preflag_manualflag_polcal:
                logger.info('Beam ' + self.beam + ': Antenna(s) ' + self.preflag_manualflag_antenna + ' for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()) and self.polcal != '':
                    pc_ant = 'flagdata(vis="' + self.get_polcal_path() + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                    lib.run_casa([pc_ant])
                    logger.debug('Beam ' + self.beam + ': Flagged antenna(s) ' + self.preflag_manualflag_antenna + ' for polarised calibrator')
                    spltant = self.preflag_manualflag_antenna.split(',')
                    for ant in spltant:
                        if preflagpolcalmanualflagantenna[0].find(ant) == -1:
                            if preflagpolcalmanualflagantenna[0] == '':
                                preflagpolcalmanualflagantenna[0] = ant
                            else:
                                preflagpolcalmanualflagantenna[0] = preflagpolcalmanualflagantenna[0] + ',' + ant
                else:
                    logger.warning('Beam ' + self.beam + ': No polarised calibrator dataset specified. Specified antenna(s) for polarised calibrator dataset will not be flagged!')
            # Flag antenna(s) for target beams
            if preflagtargetbeamsmanualflagantenna[0] == self.preflag_manualflag_antenna and self.preflag_manualflag_target:
                logger.info('Beam ' + self.beam + ': Antenna(s) ' + self.preflag_manualflag_antenna + ' for target beam dataset were already flagged')
            else:
                if self.preflag_manualflag_target and os.path.isdir(self.get_target_path()):
                    tg_ant = 'flagdata(vis="' + self.get_target_path() + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                    lib.run_casa([tg_ant])
                    logger.debug('Beam ' + self.beam + ': Flagged antenna(s) ' + self.preflag_manualflag_antenna + ' for target')
                    spltant = self.preflag_manualflag_antenna.split(',')
                    for ant in spltant:
                        if preflagtargetbeamsmanualflagantenna[0].find(ant) == -1:
                            if preflagtargetbeamsmanualflagantenna[0] == '':
                                preflagtargetbeamsmanualflagantenna[0] = ant
                            else:
                                preflagtargetbeamsmanualflagantenna[0] = preflagtargetbeamsmanualflagantenna[0] + ',' + ant
                else:
                    logger.warning('Beam ' + self.beam + ': Target dataset not specified. Specified antenna(s) for target beam dataset will not be flagged!')

        # Save the derived parameters for the antenna flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_manualflag_antenna', preflagfluxcalmanualflagantenna)
        subs_param.add_param(self, pbeam + '_polcal_manualflag_antenna', preflagpolcalmanualflagantenna)
        subs_param.add_param(self, pbeam + '_targetbeams_manualflag_antenna', preflagtargetbeamsmanualflagantenna)


    def manualflag_corr(self):
        """
        Function to flag complete correlations
        Possible values are 'XX,XY,YX,YY'
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the manualflag step to flag individual correlations

        preflagfluxcalmanualflagcorr = get_param_def(self, pbeam + '_fluxcal_manualflag_corr', np.full(1, '', dtype='U50'))  # Flagged correlations of fluxcal?
        preflagpolcalmanualflagcorr = get_param_def(self, pbeam + '_polcal_manualflag_corr', np.full(1, '', dtype='U50'))  # Flagged correlations of polcal?
        preflagtargetbeamsmanualflagcorr = get_param_def(self, pbeam + '_targetbeams_manualflag_corr', np.full(1 , '', dtype='U50'))  # Flagged correlations of target beams?

        if self.preflag_manualflag_corr != '':
            logger.info('Beam ' + self.beam + ': Flagging correlation(s) ' + self.preflag_manualflag_corr)
            # Flag correlation(s) for flux calibrator
            if preflagfluxcalmanualflagcorr[0] == self.preflag_manualflag_corr and self.preflag_manualflag_fluxcal:
                logger.info('Beam ' + self.beam + ': Correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()) and self.fluxcal != '':
                    subs_setinit.setinitdirs(self)
                    fc_corr = 'flagdata(vis="' + self.get_fluxcal_path() + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                    lib.run_casa([fc_corr])
                    logger.debug('Beam ' + self.beam + ': Flagged correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator')
                    spltcorr = self.preflag_manualflag_corr.split(',')
                    for corr in spltcorr:
                        if preflagfluxcalmanualflagcorr[0].find(corr) == -1:
                            if preflagfluxcalmanualflagcorr[0] == '':
                                preflagfluxcalmanualflagcorr[0] = corr
                            else:
                                preflagfluxcalmanualflagcorr[0] = preflagfluxcalmanualflagcorr[0] + ',' + corr
                else:
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Specified correlation(s) for flux calibrator dataset will not be flagged!')
            # Flag correlation(s) for flux calibrator
            if preflagpolcalmanualflagcorr[0] == self.preflag_manualflag_corr and self.preflag_manualflag_polcal:
                logger.info('Beam ' + self.beam + ': Correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()) and self.polcal != '':
                    subs_setinit.setinitdirs(self)
                    pc_corr = 'flagdata(vis="' + self.get_polcal_path() + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                    lib.run_casa([pc_corr])
                    logger.debug('Beam ' + self.beam + ': Flagged correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator')
                    spltcorr = self.preflag_manualflag_corr.split(',')
                    for corr in spltcorr:
                        if preflagpolcalmanualflagcorr[0].find(corr) == -1:
                            if preflagpolcalmanualflagcorr[0] == '':
                                preflagpolcalmanualflagcorr[0] = corr
                            else:
                                preflagpolcalmanualflagcorr[0] = preflagpolcalmanualflagcorr[0] + ',' + corr
                else:
                    logger.warning('Beam ' + self.beam + ': No polarised calibrator dataset specified. Specified correlation(s) for polarised calibrator dataset will not be flagged!')
            # Flag correlation(s) for target beams
            if preflagtargetbeamsmanualflagcorr[0] == self.preflag_manualflag_corr and self.preflag_manualflag_target:
                logger.info('Beam ' + self.beam + ': Correlation(s) ' + self.preflag_manualflag_corr + ' for target beam dataset were already flagged')
            else:
                if self.preflag_manualflag_target and os.path.isdir(self.get_target_path()):
                    subs_setinit.setinitdirs(self)
                    tg_corr = 'flagdata(vis="' + self.get_target_path() + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                    lib.run_casa([tg_corr])
                    logger.debug('Beam ' + self.beam + ': Flagged correlation(s) ' + self.preflag_manualflag_corr + ' for target dataset')
                    spltcorr = self.preflag_manualflag_corr.split(',')
                    for corr in spltcorr:
                        if preflagtargetbeamsmanualflagcorr[0].find(corr) == -1:
                            if preflagtargetbeamsmanualflagcorr[0] == '':
                                preflagtargetbeamsmanualflagcorr[0] = corr
                            else:
                                preflagtargetbeamsmanualflagcorr[0] = preflagtargetbeamsmanualflagcorr[0] + ',' + corr
                else:
                    logger.warning('Beam ' + self.beam + ': Target dataset not specified. Specified correlation(s) for target beam dataset will not be flagged!')

        # Save the derived parameters for the correlation flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_manualflag_corr', preflagfluxcalmanualflagcorr)
        subs_param.add_param(self, pbeam + '_polcal_manualflag_corr', preflagpolcalmanualflagcorr)
        subs_param.add_param(self, pbeam + '_targetbeams_manualflag_corr', preflagtargetbeamsmanualflagcorr)


    def manualflag_baseline(self):
        """
        Function to flag complete baselines
        Use antenna names and the notation 'ant1&ant2;ant3&ant4' etc.
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the manualflag step to flag individual baselines

        preflagfluxcalmanualflagbaseline = get_param_def(self, pbeam + '_fluxcal_manualflag_baseline', np.full(1, '', dtype='U50'))  # Flagged baselines of fluxcal?
        preflagpolcalmanualflagbaseline = get_param_def(self, pbeam + '_polcal_manualflag_baseline', np.full(1, '', dtype='U50'))  # Flagged baselines of polcal?
        preflagtargetbeamsmanualflagbaseline = get_param_def(self, pbeam + '_targetbeams_manualflag_baseline', np.full(1 , '', dtype='U50'))  # Flagged baselines of target beams?

        if self.preflag_manualflag_baseline != '':
            logger.info('Beam ' + self.beam + ': Flagging baseline(s) ' + self.preflag_manualflag_baseline)
            # Flag correlation(s) for the flux calibrator
            if preflagfluxcalmanualflagbaseline[0] == self.preflag_manualflag_baseline and self.preflag_manualflag_fluxcal:
                logger.info('Beam ' + self.beam + ': Baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(
                        self.get_fluxcal_path()) and self.fluxcal != '':
                    fc_baseline = 'flagdata(vis="' + self.get_fluxcal_path() + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                    lib.run_casa([fc_baseline])
                    logger.debug('Beam ' + self.beam + ': Flagged baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator')
                    spltbaseline = self.preflag_manualflag_baseline.split(',')
                    for baseline in spltbaseline:
                        if preflagfluxcalmanualflagbaseline[0].find(baseline) == -1:
                            if preflagfluxcalmanualflagbaseline[0] == '':
                                preflagfluxcalmanualflagbaseline[0] = baseline
                            else:
                                preflagfluxcalmanualflagbaseline[0] = preflagfluxcalmanualflagbaseline[0] + ',' + baseline
                else:
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Specified baselines(s) for flux calibrator dataset will not be flagged!')
            # Flag correlation(s) for the polarised calibrator
            if preflagpolcalmanualflagbaseline[0] == self.preflag_manualflag_baseline and \
                    self.preflag_manualflag_polcal:
                logger.info('Beam ' + self.beam + ': Baseline(s) ' + self.preflag_manualflag_baseline + ' for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()) and self.polcal != '':
                    pc_baseline = 'flagdata(vis="' + self.get_polcal_path() + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                    lib.run_casa([pc_baseline])
                    logger.debug('Beam ' + self.beam + ': Flagged baseline(s) ' + self.preflag_manualflag_baseline + ' for polarised calibrator')
                    spltbaseline = self.preflag_manualflag_baseline.split(',')
                    for baseline in spltbaseline:
                        if preflagpolcalmanualflagbaseline[0].find(baseline) == -1:
                            if preflagpolcalmanualflagbaseline[0] == '':
                                preflagpolcalmanualflagbaseline[0] = baseline
                            else:
                                preflagpolcalmanualflagbaseline[0] = preflagpolcalmanualflagbaseline[0] + ',' + baseline
                else:
                    logger.warning('Beam ' + self.beam + ': No polarised calibrator dataset specified. Specified baselines(s) for polarised calibrator dataset will not be flagged!')
            # Flag correlation(s) for the target beams
            if preflagtargetbeamsmanualflagbaseline[0] == self.preflag_manualflag_baseline and self.preflag_manualflag_target:
                logger.info('Beam ' + self.beam + ': Baseline(s) ' + self.preflag_manualflag_baseline + ' for target beam dataset were already flagged!')
            else:
                if self.preflag_manualflag_target and os.path.isdir(self.get_target_path()):
                    tg_baseline = 'flagdata(vis="' + self.get_target_path() + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                    lib.run_casa([tg_baseline])
                    logger.debug('Beam ' + self.beam + ': Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for target beam dataset')
                    spltbaseline = self.preflag_manualflag_baseline.split(',')
                    for baseline in spltbaseline:
                        if preflagtargetbeamsmanualflagbaseline[0].find(baseline) == -1:
                            if preflagtargetbeamsmanualflagbaseline[0] == '':
                                preflagtargetbeamsmanualflagbaseline[0] = baseline
                            else:
                                preflagtargetbeamsmanualflagbaseline[0] = preflagtargetbeamsmanualflagbaseline[0] + ',' + baseline
                else:
                    logger.warning('Beam ' + self.beam + ': Target dataset not specified. Specified baseline(s) for target beam dataset will not be flagged!')

        # Save the derived parameters for the baseline flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_manualflag_baseline', preflagfluxcalmanualflagbaseline)
        subs_param.add_param(self, pbeam + '_polcal_manualflag_baseline', preflagpolcalmanualflagbaseline)
        subs_param.add_param(self, pbeam + '_targetbeams_manualflag_baseline', preflagtargetbeamsmanualflagbaseline)


    def manualflag_channel(self):
        """
        Function to flag individual channels and channel ranges
        Use the CASA notation e.g. '0~5;120~128'. You don't need to give a '0:' for the spw. It's added automatically.
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the manualflag step to flag individual channel ranges

        preflagfluxcalmanualflagchannel = get_param_def(self, pbeam + '_fluxcal_manualflag_channel', np.full(1, '', dtype='U50'))  # Flagged channels of fluxcal?
        preflagpolcalmanualflagchannel = get_param_def(self, pbeam + '_polcal_manualflag_channel', np.full(1, '', dtype='U50'))  # Flagged channels of polcal?
        preflagtargetbeamsmanualflagchannel = get_param_def(self, pbeam + '_targetbeams_manualflag_channel', np.full(1 , '', dtype='U50'))  # Flagged channels of target beams?

        if self.preflag_manualflag_channel != '':
            logger.info('Beam ' + self.beam + ': Flagging channel(s) ' + self.preflag_manualflag_channel)
            # Flag channel(s) for the flux calibrator
            if preflagfluxcalmanualflagchannel[0] == self.preflag_manualflag_channel and self.preflag_manualflag_fluxcal:
                logger.info('Beam ' + self.beam + ': Channel(s) ' + self.preflag_manualflag_channel + ' for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()) and self.fluxcal != '':
                    fc_channel = 'flagdata(vis="' + self.get_fluxcal_path() + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                    lib.run_casa([fc_channel])
                    logger.debug('Beam ' + self.beam + ': Flagged channel(s) ' + self.preflag_manualflag_channel + ' for flux calibrator')
                    spltchannel = self.preflag_manualflag_channel.split(',')
                    for channel in spltchannel:
                        if preflagfluxcalmanualflagchannel[0].find(channel) == -1:
                            if preflagfluxcalmanualflagchannel[0] == '':
                                preflagfluxcalmanualflagchannel[0] = channel
                            else:
                                preflagfluxcalmanualflagchannel[0] = preflagfluxcalmanualflagchannel[0] + ',' + channel
                else:
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Specified channel range(s) for flux calibrator dataset will not be flagged!')
            # Flag channel(s) for the polarised calibrator
            if preflagpolcalmanualflagchannel[0] == self.preflag_manualflag_channel and self.preflag_manualflag_polcal:
                logger.info('Beam ' + self.beam + ': Channel(s) ' + self.preflag_manualflag_channel + ' for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()) and self.polcal != '':
                    pc_channel = 'flagdata(vis="' + self.get_polcal_path() + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                    lib.run_casa([pc_channel])
                    logger.debug('Beam ' + self.beam + ': Flagged channel(s) ' + self.preflag_manualflag_channel + ' for polarised calibrator')
                    spltchannel = self.preflag_manualflag_channel.split(',')
                    for channel in spltchannel:
                        if preflagpolcalmanualflagchannel[0].find(channel) == -1:
                            if preflagpolcalmanualflagchannel[0] == '':
                                preflagpolcalmanualflagchannel[0] = channel
                            else:
                                preflagpolcalmanualflagchannel[0] = preflagpolcalmanualflagchannel[0] + ',' + channel
                else:
                    logger.warning('Beam ' + self.beam + ': No polarised calibrator dataset specified. Specified channel range(s) for polarised calibrator dataset will not be flagged!')
            # Flag channel(s) for the target beams
            if preflagtargetbeamsmanualflagchannel[0] == self.preflag_manualflag_channel and self.preflag_manualflag_target:
                logger.info('Beam ' + self.beam + ': Correlation(s) ' + self.preflag_manualflag_channel + ' for target beam dataset were already flagged')
            else:
                if self.preflag_manualflag_target and os.path.isdir(self.get_target_path()):
                    tg_channel = 'flagdata(vis="' + self.get_target_path() + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                    lib.run_casa([tg_channel])
                    logger.debug('Beam ' + self.beam + ': Flagging channel(s) ' + self.preflag_manualflag_channel + ' for target beam dataset')
                    spltchannel = self.preflag_manualflag_channel.split(',')
                    for channel in spltchannel:
                        if preflagtargetbeamsmanualflagchannel[0].find(channel) == -1:
                            if preflagtargetbeamsmanualflagchannel[0] == '':
                                preflagtargetbeamsmanualflagchannel[0] = channel
                            else:
                                preflagtargetbeamsmanualflagchannel[0] = preflagtargetbeamsmanualflagchannel[0] + ',' + channel
                else:
                    logger.warning('Beam ' + self.beam + ': Target dataset not specified. Specified channel range(s) for target beam dataset will not be flagged!')

        # Save the derived parameters for the channel flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_manualflag_channel', preflagfluxcalmanualflagchannel)
        subs_param.add_param(self, pbeam + '_polcal_manualflag_channel', preflagpolcalmanualflagchannel)
        subs_param.add_param(self, pbeam + '_targetbeams_manualflag_channel', preflagtargetbeamsmanualflagchannel)


    def manualflag_time(self):
        """
        Function to flag time ranges
        Use the CASA notation e.g. '09:14:0~09:54:0'.
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the manualflag step to flag individual channel ranges

        preflagfluxcalmanualflagtime = get_param_def(self, pbeam + '_fluxcal_manualflag_time', np.full(1, '', dtype='U50'))  # Flagged time range(s) of fluxcal?
        preflagpolcalmanualflagtime = get_param_def(self, pbeam + '_polcal_manualflag_time', np.full(1, '', dtype='U50'))  # Flagged time range(s) of polcal?
        preflagtargetbeamsmanualflagtime = get_param_def(self, pbeam + '_targetbeams_manualflag_time', np.full(1 , '', dtype='U50'))  # Flagged time range(s) of target beams?

        if self.preflag_manualflag_time != '':
            logger.info('Beam ' + self.beam + ': Flagging time range ' + self.preflag_manualflag_time)
            # Flag time range for the flux calibrator
            if preflagfluxcalmanualflagtime[0] == self.preflag_manualflag_time and self.preflag_manualflag_fluxcal:
                logger.info('Beam ' + self.beam + ': Time range ' + self.preflag_manualflag_time + ' for flux calibrator was already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()) and self.fluxcal != '':
                    fc_time = 'flagdata(vis="' + self.get_fluxcal_path() + '", timerange="' + self.preflag_manualflag_time + '", flagbackup=False)'
                    lib.run_casa([fc_time])
                    logger.debug('Beam ' + self.beam + ': Flagged time range ' + self.preflag_manualflag_time + ' for flux calibrator')
                    splttime = self.preflag_manualflag_time.split(',')
                    for time in splttime:
                        if preflagfluxcalmanualflagtime[0].find(time) == -1:
                            if preflagfluxcalmanualflagtime[0] == '':
                                preflagfluxcalmanualflagtime[0] = time
                            else:
                                preflagfluxcalmanualflagtime[0] = preflagfluxcalmanualflagtime[0] + ',' + time
                else:
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Specified time range(s) for '
                                   'flux calibrator dataset will not be flagged!')
            # Flag time range for the polarised calibrator
            if preflagpolcalmanualflagtime[0] == self.preflag_manualflag_time and self.preflag_manualflag_polcal:
                logger.info('Time range ' + self.preflag_manualflag_time + ' for polarised calibrator was already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()) and self.polcal != '':
                    pc_time = 'flagdata(vis="' + self.get_polcal_path() + '", timerange="' + self.preflag_manualflag_time + '", flagbackup=False)'
                    lib.run_casa([pc_time])
                    logger.debug('Beam ' + self.beam + ': Flagged time range ' + self.preflag_manualflag_time + ' for polarised calibrator')
                    splttime = self.preflag_manualflag_time.split(',')
                    for time in splttime:
                        if preflagpolcalmanualflagtime[0].find(time) == -1:
                            if preflagpolcalmanualflagtime[0] == '':
                                preflagpolcalmanualflagtime[0] = time
                            else:
                                preflagpolcalmanualflagtime[0] = preflagpolcalmanualflagtime[0] + ',' + time
                else:
                    logger.warning('Beam ' + self.beam + ': No polariased calibrator dataset specified. Specified time range(s) '
                                   'for polarised calibrator dataset will not be flagged!')
            # Flag time range for the target beams
            if preflagtargetbeamsmanualflagtime[0] == self.preflag_manualflag_time and self.preflag_manualflag_target:
                logger.info('Beam ' + self.beam + ': Time range ' + self.preflag_manualflag_time + ' for target beam dataset was already flagged!')
            else:
                if self.preflag_manualflag_target and os.path.isdir(self.get_target_path()):
                    tg_time = 'flagdata(vis="' + self.get_target_path() + '", timerange="' + self.preflag_manualflag_time + '", flagbackup=False)'
                    lib.run_casa([tg_time])
                    logger.debug('Beam ' + self.beam + ': Flagging time range(s) ' + self.preflag_manualflag_time + ' for target beam dataset')
                    splttime = self.preflag_manualflag_time.split(',')
                    for time in splttime:
                        if preflagtargetbeamsmanualflagtime[0].find(time) == -1:
                            if preflagtargetbeamsmanualflagtime[0] == '':
                                preflagtargetbeamsmanualflagtime[0] = time
                            else:
                                preflagtargetbeamsmanualflagtime[0] = preflagtargetbeamsmanualflagtime[0] + ',' + time
                else:
                    logger.warning('Beam ' + self.beam + ': Target dataset not specified. Specified time range(s) for target beam dataset will not be flagged!')

        # Save the derived parameters for the channel flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_manualflag_time', preflagfluxcalmanualflagtime)
        subs_param.add_param(self, pbeam + '_polcal_manualflag_time', preflagpolcalmanualflagtime)
        subs_param.add_param(self, pbeam + '_targetbeams_manualflag_time', preflagtargetbeamsmanualflagtime)


    def manualflag_clipzeros(self):
        """
        Function to flag any zero-valued data
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the manualflag step to flag the zero-valued data.

        # Zero valued data of fluxcal flagged?
        preflagfluxcalmanualflagclipzeros = get_param_def(self, pbeam + '_fluxcal_manualflag_clipzeros', False)

        # Zero valued data of polcal flagged?
        preflagpolcalmanualflagclipzeros = get_param_def(self, pbeam + '_polcal_manualflag_clipzeros', False)
        # Zero valued data of target beams flagged?
        preflagtargetbeamsmanualflagclipzeros = get_param_def(self, pbeam + '_targetbeams_manualflag_clipzeros', False)

        if self.preflag_manualflag_clipzeros:
            logger.info('Beam ' + self.beam + ': Flagging Zero-valued data')
            # Flag the Zero-valued data for the flux calibrator
            if preflagfluxcalmanualflagclipzeros and self.preflag_manualflag_fluxcal:
                logger.info('Beam ' + self.beam + ': Zero-valued data for flux calibrator were already flagged')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.get_fluxcal_path()) and self.fluxcal != '':
                    fc_clipzeros = 'flagdata(vis="' + self.get_fluxcal_path() + '", mode="clip", clipzeros=True, flagbackup=False)'
                    lib.run_casa([fc_clipzeros])
                    logger.debug('Beam ' + self.beam + ': Flagged Zero-valued data for flux calibrator')
                    preflagfluxcalmanualflagclipzeros = True
                else:
                    preflagfluxcalmanualflagclipzeros = False
                    logger.warning('Beam ' + self.beam + ': No flux calibrator dataset specified. Zero-valued data for flux calibrator '
                                   'dataset will not be flagged!')
            # Flag the Zero-valued data for the polarised calibrator
            if preflagpolcalmanualflagclipzeros and self.preflag_manualflag_polcal:
                logger.info('Beam ' + self.beam + ': Zero-values data for polarised calibrator were already flagged')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.get_polcal_path()) and self.polcal != '':
                    pc_clipzeros = 'flagdata(vis="' + self.get_polcal_path() + '", mode="clip", clipzeros=True, flagbackup=False)'
                    lib.run_casa([pc_clipzeros])
                    logger.debug('Beam ' + self.beam + ': Flagged Zero-valued data for polarised calibrator')
                    preflagpolcalmanualflagclipzeros = True
                else:
                    preflagpolcalmanualflagclipzeros = False
                    logger.warning('Beam ' + self.beam + ': No polarised calibrator dataset specified. Zero-valued data for polariased '
                                   'calibrator dataset will not be flagged!')
            # Flag the Zero-valued for the target beams
            if self.preflag_manualflag_clipzeros and self.preflag_manualflag_target:
                logger.info('Beam ' + self.beam + ': Zero-valued data for target beam dataset were already flagged')
            else:
                if self.preflag_manualflag_target and os.path.isdir(self.get_target_path()):
                    tg_clipzeros = 'flagdata(vis="' + self.get_target_path() + '", mode="clip", clipzeros=True, flagbackup=False)'
                    lib.run_casa([tg_clipzeros])
                    logger.debug('Beam ' + self.beam + ': Zero-valued data for target beam flagged!')
                    preflagtargetbeamsmanualflagclipzeros = True
                else:
                    logger.warning('Beam ' + self.beam + ': Target dataset not specified. Zero-values data for target beam dataset will '
                               'not be flagged!')

        # Save the derived parameters for the auto-correlation flagging to the parameter file

        subs_param.add_param(self, pbeam + '_fluxcal_manualflag_clipzeros', preflagfluxcalmanualflagclipzeros)
        subs_param.add_param(self, pbeam + '_polcal_manualflag_clipzeros', preflagpolcalmanualflagclipzeros)
        subs_param.add_param(self, pbeam + '_targetbeams_manualflag_clipzeros', preflagtargetbeamsmanualflagclipzeros)


    def aoflagger_bandpass(self):
        """
        Creates a bandpass from a known frequency behaviour of the telescope. This is usually applied on the fly
        when using aoflagger.
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the bandpass step of the AOFLagger step

        # Bandpass successfully derived
        preflagaoflaggerbandpassstatus = get_param_def(self, pbeam + '_aoflagger_bandpass_status', False)

        if self.preflag_aoflagger_bandpass:
            # Check if bandpass was already derived and bandpass table is available
            if os.path.isfile(self.get_bandpass_path()):
                logger.info('Beam ' + self.beam + ': Preliminary bandpass table was already derived')
                preflagaoflaggerbandpassstatus = True
            # If not, calculate the bandpass for the setup of the observation using the flux calibrator
            elif not preflagaoflaggerbandpassstatus:
                if self.fluxcal != '':
                    create_bandpass(self.get_fluxcal_path(), self.get_bandpass_path())
                elif self.polcal != '':
                    create_bandpass(self.get_polcal_path(), self.get_bandpass_path())
                else:
                    # logger.debug("self.get_target_path(str(self.beam).zfill(2))= {0}".format(str(self.get_target_path(str(self.beam).zfill(2)))))
                    # create_bandpass(self.get_target_path(str(self.beam).zfill(2)), self.get_bandpass_path())
                    create_bandpass(self.get_target_path(self.beam), self.get_bandpass_path())
                if os.path.isfile(self.get_bandpass_path()):
                    preflagaoflaggerbandpassstatus = True
                    logger.info('Beam ' + self.beam + ': Derived preliminary bandpass table for AOFlagging')
                else:
                    error = 'Beam ' + self.beam + ': Preliminary bandpass table for flux calibrator was not derived successfully!'
                    logger.error(error)
                    raise ApercalException(error)
            else:
                error = 'Beam ' + self.beam + ': Bandpass table not available at {}. Preliminary bandpass cannot be applied'.format(self.get_bandpass_path())
                logger.error(error)
                raise ApercalException(error)

        # Save the derived parameters for the AOFlagger bandpass status to the parameter file

        subs_param.add_param(self, pbeam + '_aoflagger_bandpass_status', preflagaoflaggerbandpassstatus)


    def aoflagger_plot(self, mspath, baselines=[(0, 0xb), (2, 7), (4, 5)]):
        """
        Saves a png with the flags that AOFlagger added for some 'typical' baselines
        Will save in the same directory as the measurement set

        Args:
            mspath (str): full path to the measurement set that has been flagged
            baselines (List[Tuple[int]]): baselines for which to produce the plots. These are
                                          antenna number in the MS (typically 0 means RT2).
        """
        logger.info('Beam ' + self.beam + ': Storing flagging images for ' + mspath)
        beamstr = mspath.rstrip('/').split('/')[-3] # beam number as string, "29" or so

        if self.subdirification:
            destination_path = self.basedir + '/qa/preflag/' + beamstr
            if not path.exists(destination_path):
                os.makedirs(destination_path)
        else:
            destination_path = "."
        msname = mspath.rstrip('/').split('/')[-1].rstrip('.MS')
        for (ant1, ant2) in baselines:
            pngname = "{}-flags-{:02d}-{:02d}.png".format(msname, ant1, ant2)
            lib.basher("rfigui -save-baseline {} {} {} 0 0 {}".format(destination_path + "/" + pngname, ant1, ant2, mspath))
        logger.info('Beam ' + self.beam + ': Done storing flagging images for ' + mspath)


    def aoflagger_flag(self):
        """
        Uses the aoflagger to flag the calibrators and the target data set(s). Uses the bandpass corrected
        visibilities if bandpass was derived and applied successfully beforehand.
        """
        subs_setinit.setinitdirs(self)

        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the bandpass step of the AOFlagger step

        # AOFlagged the flux calibrator?
        preflagaoflaggerfluxcalflag = get_param_def(self, pbeam + '_aoflagger_fluxcal_flag_status', False)

        # AOFlagged the polarised calibrator?
        preflagaoflaggerpolcalflag = get_param_def(self, pbeam + '_aoflagger_polcal_flag_status', False)

        # AOFlagged the target beams?
        preflagaoflaggertargetbeamsflag = get_param_def(self, pbeam + '_aoflagger_targetbeams_flag_status', False)

        # base_cmd = 'aoflagger -strategy ' + ao_strategies + '/' + self.preflag_aoflagger_fluxcalstrat
        base_cmd = 'aolua -strategy ' + ao_strategies + '/strategy-apertif-2020-05-19.lua -baselines all'

        # Suppress logging of lines that start with this (to prevent 1000s of lines of logging)
        strip_prefixes = ['Channel ']
        if self.preflag_aoflagger:
            # Flag the flux calibrator with AOFLagger
            if self.preflag_aoflagger_fluxcal and self.fluxcal != '':
                if not preflagaoflaggerfluxcalflag:
                    if os.path.isdir(self.get_fluxcal_path()) and self.preflag_aoflagger_fluxcalstrat != '':
                        logger.info('Beam ' + self.beam + ': Using AOFlagger to flag flux calibrator dataset')
                        # Check if bandpass table was derived successfully
                        preflagaoflaggerbandpassstatus = get_param_def(self, '_aoflagger_bandpass_status', True)
                        if self.preflag_aoflagger_bandpass and preflagaoflaggerbandpassstatus:
                            try:
                                lib.basher(base_cmd + ' -preamble "bandpass_filename=\'{}\'" '.format(self.get_bandpass_path()) + self.get_fluxcal_path(),
                                        prefixes_to_strip=strip_prefixes)
                            except Exception as e:
                                logger.error("Beam {0}: Using AOFlagger to flag flux calibrator ... Failed".format(self.beam))
                                raise ApercalException(e)
                            else:
                                logger.debug('Beam {0}: Used AOFlagger to flag flux calibrator with preliminary bandpass applied'.format(self.beam))
                                preflagaoflaggerfluxcalflag = True
                        elif self.preflag_aoflagger_bandpass and not preflagaoflaggerbandpassstatus:
                            lib.basher(base_cmd + ' ' + self.get_fluxcal_path(),
                                       prefixes_to_strip=strip_prefixes)
                            logger.warning('Beam ' + self.beam + ': Used AOFlagger to flag flux calibrator without preliminary bandpass '
                                           'applied. Better results are usually obtained with a preliminary bandpass applied.')
                            preflagaoflaggerfluxcalflag = True
                        elif not self.preflag_aoflagger_bandpass:
                            lib.basher(base_cmd + ' ' + self.get_fluxcal_path(), prefixes_to_strip=strip_prefixes)
                            logger.warning('Beam ' + self.beam + ': Used AOFlagger to flag flux calibrator without preliminary bandpass '
                                           'applied. Better results are usually obtained with a preliminary bandpass applied.')
                            preflagaoflaggerfluxcalflag = True
                        # it is not critical if plotting fails
                        try:
                            self.aoflagger_plot(self.get_fluxcal_path())
                        except Exception as e:
                            logger.warning('Beam ' + self.beam + ': AOflagger plotting failed')
                            logger.exception(e)
                    else:
                        error = 'Beam ' + self.beam + ': Flux calibrator dataset or strategy not defined properly or dataset' \
                                'not available. Not AOFlagging flux calibrator.'
                        logger.error(error)
                        raise ApercalException(error)
                else:
                    logger.info('Beam ' + self.beam + ': Flux calibrator was already flagged with AOFlagger!')

            # Save the derived parameters for the AOFlagger status to the parameter file
            subs_param.add_param(self, pbeam + '_aoflagger_fluxcal_flag_status', preflagaoflaggerfluxcalflag)

            # Flag the polarised calibrator with AOFlagger
            if self.preflag_aoflagger_polcal and self.polcal != '':
                if not preflagaoflaggerpolcalflag:
                    if not os.path.isdir(self.get_polcal_path()):
                        error = 'Beam ' + self.beam + ': Cannot find polarisation calibrator dataset: {}'.format(self.get_polcal_path())
                        logger.error(error)
                        raise ApercalException(error)

                    if self.preflag_aoflagger_polcalstrat == '':
                        error = 'Beam ' + self.beam + ': Strategy for polarised calibrator not defined'
                        logger.error(error)
                        raise ApercalException(error)

                    logger.info('Beam ' + self.beam + ': Using AOFlagger to flag polarised calibrator dataset.')
                    # Check if bandpass was applied successfully
                    # Check if bandpass table was derived successfully
                    preflagaoflaggerbandpassstatus = get_param_def(self, pbeam + '_aoflagger_bandpass_status', False)
                    ao_base_cmd = 'aolua -strategy ' + '/strategy-apertif-2020-05-19.lua -baselines all'
                    if self.preflag_aoflagger_bandpass and preflagaoflaggerbandpassstatus:
                        try:
                            lib.basher(ao_base_cmd + ' -preamble "bandpass_filename=\'{}\'" '.format(self.get_bandpass_path()) + self.get_polcal_path(),
                                    prefixes_to_strip=strip_prefixes)
                        except Exception as e:
                            logger.error("Beam {0}: Using AOFlagger to flag polarisaed calibrator ... Failed".format(self.beam))
                            logger.exception(e)
                            preflagaoflaggerpolcalflag = False
                        else:
                            logger.debug('Beam ' + self.beam + ': Used AOFlagger to flag polarised calibrator with preliminary bandpass applied.')
                            preflagaoflaggerpolcalflag = True
                    elif self.preflag_aoflagger_bandpass and not preflagaoflaggerbandpassstatus:
                        lib.basher(ao_base_cmd + ' ' + self.get_polcal_path(), prefixes_to_strip=strip_prefixes)
                        logger.warning('Beam ' + self.beam + ': Used AOFlagger to flag polarised calibrator without preliminary bandpass '
                                       'applied. Better results are usually obtained with a preliminary bandpass applied.')
                        preflagaoflaggerpolcalflag = True
                    elif not self.preflag_aoflagger_bandpass:
                        lib.basher(ao_base_cmd + ' ' + self.get_polcal_path(), prefixes_to_strip=strip_prefixes)
                        logger.info('Beam ' + self.beam + ': Used AOFlagger to flag polarised calibrator without preliminary bandpass '
                                    'applied. Better results are usually obtained with a preliminary bandpass applied.')
                        preflagaoflaggerpolcalflag = True
                    # it is not critical if plotting fails
                    try:
                        self.aoflagger_plot(self.get_polcal_path())
                    except Exception as e:
                        logger.warning('Beam ' + self.beam + ': Aoflagger plotting failed')
                        logger.exception(e)
                else:
                    logger.info('Beam ' + self.beam + ': Polarised calibrator was already flagged with AOFlagger!')

            # Save the derived parameters for the AOFlagger status to the parameter file
            subs_param.add_param(
                self, pbeam + '_aoflagger_polcal_flag_status', preflagaoflaggerpolcalflag)

            # Flag the target beams with AOFlagger
            if self.preflag_aoflagger_target and self.target != '':
                if not preflagaoflaggertargetbeamsflag:
                    if not os.path.isdir(self.get_target_path()):
                        error = 'Beam ' + self.beam + ': Cannot find target dataset: {}'.format(self.get_target_path())
                        logger.error(error)
                        raise ApercalException(error)

                    if self.preflag_aoflagger_targetstrat == '':
                        error = 'Beam ' + self.beam + ': Strategy for target dataset not defined'
                        logger.error(error)
                        raise ApercalException(error)

                    logger.info('Beam ' + self.beam + ': Using AOFlagger to flag selected target beam dataset(s)')
                    # Check if parameter exists already and bandpass was applied successfully
                    # Check if bandpass table was derived successfully
                    preflagaoflaggerbandpassstatus = get_param_def(self, pbeam + '_aoflagger_bandpass_status', False)
                    if self.preflag_aoflagger_use_interval:
                        if not preflagaoflaggertargetbeamsflag:
                            base_cmd = 'aolua -strategy ' + ao_strategies + '/strategy-apertif-2020-05-19.lua -baselines all' + " --max-interval-size {0}".format(self.preflag_aoflagger_delta_interval) + " -j {0}".format(
                            self.preflag_aoflagger_threads)
                            if self.preflag_aoflagger_bandpass and preflagaoflaggerbandpassstatus:
                                try:
                                    lib.basher(base_cmd + ' -preamble "bandpass_filename=\'{}\'" '.format(self.get_bandpass_path()) + self.get_target_path(),
                                            prefixes_to_strip=strip_prefixes)
                                except Exception as e:
                                    logger.error("Beam {0}: Using AOFlagger to flag target ... Failed".format(self.beam))
                                    raise ApercalException(e)
                                logger.debug('Beam ' + self.beam + ': Used AOFlagger to flag target beam with preliminary bandpass applied')
                                preflagaoflaggertargetbeamsflag = True
                            elif self.preflag_aoflagger_bandpass and not preflagaoflaggerbandpassstatus:
                                lib.basher(base_cmd + ' ' + self.get_target_path(), prefixes_to_strip=strip_prefixes)
                                logger.warning('Beam ' + self.beam + ': Used AOFlagger to flag target beam without preliminary bandpass '
                                            'applied. Better results are usually obtained with a preliminary bandpass applied.')
                                preflagaoflaggertargetbeamsflag = True
                            elif not self.preflag_aoflagger_bandpass:
                                lib.basher(base_cmd + ' ' + self.get_target_path(), prefixes_to_strip=strip_prefixes)
                                logger.warning('Beam ' + self.beam + ': Used AOFlagger to flag target beam without preliminary bandpass '
                                            'applied. Better results are usually obtained with a preliminary '
                                            'bandpass applied.')
                                preflagaoflaggertargetbeamsflag = True
                            # it is not critical if plotting fails
                            try:
                                self.aoflagger_plot(self.get_target_path())
                            except Exception as e:
                                logger.warning('Beam ' + self.beam + ': Aoflagger plotting failed')
                                logger.exception(e)
                        else:
                            logger.info('Beam ' + self.beam + ': Target beam dataset was already flagged with AOFlagger!')
                    else:
                        base_cmd = 'aolua -strategy ' + ao_strategies + '/strategy-apertif-2020-05-19.lua -baselines all'
                        if not preflagaoflaggertargetbeamsflag:
                            if self.preflag_aoflagger_bandpass and preflagaoflaggerbandpassstatus:
                                lib.basher(base_cmd + ' -preamble "bandpass_filename=\'{}\'" '.format(self.get_bandpass_path()) + self.get_target_path(),
                                        prefixes_to_strip=strip_prefixes)
                                logger.debug('Beam ' + self.beam + ': Used AOFlagger to flag target beam with preliminary bandpass applied')
                                preflagaoflaggertargetbeamsflag = True
                            elif self.preflag_aoflagger_bandpass and not preflagaoflaggerbandpassstatus:
                                lib.basher(base_cmd + ' ' + self.get_target_path(), prefixes_to_strip=strip_prefixes)
                                logger.warning('Beam ' + self.beam + ': Used AOFlagger to flag target beam without preliminary bandpass '
                                            'applied. Better results are usually obtained with a preliminary bandpass applied.')
                                preflagaoflaggertargetbeamsflag = True
                            elif not self.preflag_aoflagger_bandpass:
                                lib.basher(base_cmd + ' ' + self.get_target_path(), prefixes_to_strip=strip_prefixes)
                                logger.warning('Beam ' + self.beam + ': Used AOFlagger to flag target beam without preliminary bandpass '
                                            'applied. Better results are usually obtained with a preliminary bandpass applied.')
                                preflagaoflaggertargetbeamsflag = True
                            # it is not critical if plotting fails
                            try:
                                self.aoflagger_plot(self.get_target_path())
                            except Exception as e:
                                logger.warning('Beam ' + self.beam + ': Aoflagger plotting failed')
                                logger.exception(e)
                        else:
                            logger.info('Beam ' + self.beam + ': Target beam dataset was already flagged with AOFlagger!')
                else:
                    error = 'Beam ' + self.beam + ': Target beam dataset(s) or strategy not defined properly. Not AOFlagging ' \
                            'target beam dataset(s).'
                    logger.error(error)
                    raise ApercalException(error)

            # Save the derived parameters for the AOFlagger status to the parameter file
            subs_param.add_param(
                self, pbeam + '_aoflagger_targetbeams_flag_status', preflagaoflaggertargetbeamsflag)
        #subs_param.add_param(self, pbeam + '_aoflagger_fluxcal_flag_status', preflagaoflaggerfluxcalflag)
        #subs_param.add_param(self, pbeam + '_aoflagger_polcal_flag_status', preflagaoflaggerpolcalflag)



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

        beam_range = range(self.NBEAMS)
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
        subs_managefiles.director(self, 'rm', self.basedir + self.beam + '/' + self.rawsubdir)
        logger.warning('Deleting all parameter file entries for PREPARE and PREFLAG module')

        prebeam = 'prepare_B' + str(self.beam).zfill(2)
        pbeam = 'preflag_B' + str(self.beam).zfill(2)

        subs_param.del_param(self, prebeam + '_fluxcal_requested')
        subs_param.del_param(self, prebeam + '_fluxcal_diskstatus')
        subs_param.del_param(self, prebeam + '_fluxcal_altastatus')
        subs_param.del_param(self, prebeam + '_fluxcal_copystatus')
        subs_param.del_param(self, prebeam + '_fluxcal_rejreason')
        subs_param.del_param(self, prebeam + '_polcal_requested')
        subs_param.del_param(self, prebeam + '_polcal_diskstatus')
        subs_param.del_param(self, prebeam + '_polcal_altastatus')
        subs_param.del_param(self, prebeam + '_polcal_copystatus')
        subs_param.del_param(self, prebeam + '_polcal_rejreason')
        subs_param.del_param(self, prebeam + '_targetbeams_requested')
        subs_param.del_param(self, prebeam + '_targetbeams_diskstatus')
        subs_param.del_param(self, prebeam + '_targetbeams_altastatus')
        subs_param.del_param(self, prebeam + '_targetbeams_copystatus')
        subs_param.del_param(self, prebeam + '_targetbeams_rejreason')

        subs_param.del_param(self, pbeam + '_fluxcal_shadow')
        subs_param.del_param(self, pbeam + '_polcal_shadow')
        subs_param.del_param(self, pbeam + '_targetbeams_shadow')
        subs_param.del_param(self, pbeam + '_fluxcal_edges')
        subs_param.del_param(self, pbeam + '_polcal_edges')
        subs_param.del_param(self, pbeam + '_targetbeams_edges')
        subs_param.del_param(self, pbeam + '_fluxcal_ghosts')
        subs_param.del_param(self, pbeam + '_polcal_ghosts')
        subs_param.del_param(self, pbeam + '_targetbeams_ghosts')
        subs_param.del_param(self, pbeam + '_fluxcal_manualflag_auto')
        subs_param.del_param(self, pbeam + '_polcal_manualflag_auto')
        subs_param.del_param(self, pbeam + '_targetbeams_manualflag_auto')
        subs_param.del_param(self, pbeam + '_fluxcal_manualflag_from_file')
        subs_param.del_param(self, pbeam + '_polcal_manualflag_from_file')
        subs_param.del_param(self, pbeam + '_targetbeams_manualflag_from_file')
        subs_param.del_param(self, pbeam + '_fluxcal_manualflag_antenna')
        subs_param.del_param(self, pbeam + '_polcal_manualflag_antenna')
        subs_param.del_param(self, pbeam + '_targetbeams_manualflag_antenna')
        subs_param.del_param(self, pbeam + '_fluxcal_manualflag_corr')
        subs_param.del_param(self, pbeam + '_polcal_manualflag_corr')
        subs_param.del_param(self, pbeam + '_targetbeams_manualflag_corr')
        subs_param.del_param(self, pbeam + '_fluxcal_manualflag_baseline')
        subs_param.del_param(self, pbeam + '_polcal_manualflag_baseline')
        subs_param.del_param(self, pbeam + '_targetbeams_manualflag_baseline')
        subs_param.del_param(self, pbeam + '_fluxcal_manualflag_channel')
        subs_param.del_param(self, pbeam + '_polcal_manualflag_channel')
        subs_param.del_param(self, pbeam + '_targetbeams_manualflag_channel')
        subs_param.del_param(self, pbeam + '_fluxcal_manualflag_time')
        subs_param.del_param(self, pbeam + '_polcal_manualflag_time')
        subs_param.del_param(self, pbeam + '_targetbeams_manualflag_time')
        subs_param.del_param(self, pbeam + '_fluxcal_manualflag_clipzeros')
        subs_param.del_param(self, pbeam + '_polcal__manualflag_clipzeros')
        subs_param.del_param(self, pbeam + '_targetbeams_manualflag_clipzeros')
        subs_param.del_param(self, pbeam + '_aoflagger_bandpass_status')
        subs_param.del_param(self, pbeam + '_aoflagger_fluxcal_flag_status')
        subs_param.del_param(self, pbeam + '_aoflagger_polcal_flag_status')
        subs_param.del_param(self, pbeam + '_aoflagger_targetbeams_flag_status')

    def reset_all(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        logger.warning('Deleting all raw data products and their directories for all beams. You will need to '
                       'start with the PREPARE step again!')
        subs_managefiles.director(self, 'ch', self.basedir)
        for b in range(self.NBEAMS):
            prebeam = 'prepare_B' + str(b).zfill(2)
            pbeam = 'preflag_B' + str(b).zfill(2)
            if os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.rawsubdir):
                logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all raw data products.')
                subs_managefiles.director(self, 'rm', self.basedir + str(b).zfill(2) + '/' + self.rawsubdir)
                logger.warning('Beam ' + str(b).zfill(2) + ': Deleting all parameter file entries for PREPARE and PREFLAG module.')

                subs_param.del_param(self, prebeam + '_fluxcal_requested')
                subs_param.del_param(self, prebeam + '_fluxcal_diskstatus')
                subs_param.del_param(self, prebeam + '_fluxcal_altastatus')
                subs_param.del_param(self, prebeam + '_fluxcal_copystatus')
                subs_param.del_param(self, prebeam + '_fluxcal_rejreason')
                subs_param.del_param(self, prebeam + '_polcal_requested')
                subs_param.del_param(self, prebeam + '_polcal_diskstatus')
                subs_param.del_param(self, prebeam + '_polcal_altastatus')
                subs_param.del_param(self, prebeam + '_polcal_copystatus')
                subs_param.del_param(self, prebeam + '_polcal_rejreason')
                subs_param.del_param(self, prebeam + '_targetbeams_requested')
                subs_param.del_param(self, prebeam + '_targetbeams_diskstatus')
                subs_param.del_param(self, prebeam + '_targetbeams_altastatus')
                subs_param.del_param(self, prebeam + '_targetbeams_copystatus')
                subs_param.del_param(self, prebeam + '_targetbeams_rejreason')

                subs_param.del_param(self, pbeam + '_fluxcal_shadow')
                subs_param.del_param(self, pbeam + '_polcal_shadow')
                subs_param.del_param(self, pbeam + '_targetbeams_shadow')
                subs_param.del_param(self, pbeam + '_fluxcal_edges')
                subs_param.del_param(self, pbeam + '_polcal_edges')
                subs_param.del_param(self, pbeam + '_targetbeams_edges')
                subs_param.del_param(self, pbeam + '_fluxcal_ghosts')
                subs_param.del_param(self, pbeam + '_polcal_ghosts')
                subs_param.del_param(self, pbeam + '_targetbeams_ghosts')
                subs_param.del_param(self, pbeam + '_fluxcal_manualflag_auto')
                subs_param.del_param(self, pbeam + '_polcal_manualflag_auto')
                subs_param.del_param(self, pbeam + '_targetbeams_manualflag_auto')
                subs_param.del_param(self, pbeam + '_fluxcal_manualflag_from_file')
                subs_param.del_param(self, pbeam + '_polcal_manualflag_from_file')
                subs_param.del_param(self, pbeam + '_targetbeams_manualflag_from_file')
                subs_param.del_param(self, pbeam + '_fluxcal_manualflag_antenna')
                subs_param.del_param(self, pbeam + '_polcal_manualflag_antenna')
                subs_param.del_param(self, pbeam + '_targetbeams_manualflag_antenna')
                subs_param.del_param(self, pbeam + '_fluxcal_manualflag_corr')
                subs_param.del_param(self, pbeam + '_polcal_manualflag_corr')
                subs_param.del_param(self, pbeam + '_targetbeams_manualflag_corr')
                subs_param.del_param(self, pbeam + '_fluxcal_manualflag_baseline')
                subs_param.del_param(self, pbeam + '_polcal_manualflag_baseline')
                subs_param.del_param(self, pbeam + '_targetbeams_manualflag_baseline')
                subs_param.del_param(self, pbeam + '_fluxcal_manualflag_channel')
                subs_param.del_param(self, pbeam + '_polcal_manualflag_channel')
                subs_param.del_param(self, pbeam + '_targetbeams_manualflag_channel')
                subs_param.del_param(self, pbeam + '_fluxcal_manualflag_time')
                subs_param.del_param(self, pbeam + '_polcal_manualflag_time')
                subs_param.del_param(self, pbeam + '_targetbeams_manualflag_time')
                subs_param.del_param(self, pbeam + '_fluxcal_manualflag_clipzeros')
                subs_param.del_param(self, pbeam + '_polcal__manualflag_clipzeros')
                subs_param.del_param(self, pbeam + '_targetbeams_manualflag_clipzeros')
                subs_param.del_param(self, pbeam + '_aoflagger_bandpass_status')
                subs_param.del_param(self, pbeam + '_aoflagger_fluxcal_flag_status')
                subs_param.del_param(self, pbeam + '_aoflagger_polcal_flag_status')
                subs_param.del_param(self, pbeam + '_aoflagger_targetbeams_flag_status')
            else:
                logger.warning('Beam ' + str(b).zfill(2) + ': No raw data present.')
