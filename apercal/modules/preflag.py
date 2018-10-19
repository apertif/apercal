import ConfigParser
import glob
import logging

import numpy as np
import pandas as pd
import drivecasa
import os

import casacore.tables as pt

from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs import param as subs_param
from apercal.subs.param import get_param_def
from apercal.modules import default_cfg
from apercal.ao_strategies import ao_strategies
from apercal.libs import lib


class preflag:
    """
    Preflagging class. Used to automatically flag data and apply preknown flags.
    """
    apercaldir = None
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
    preflag_aoflagger = None
    preflag_aoflagger_bandpass = None
    preflag_aoflagger_fluxcal = None
    preflag_aoflagger_polcal = None
    preflag_aoflagger_target = None
    preflag_aoflagger_targetbeams = None
    preflag_aoflagger_fluxcalstrat = None
    preflag_aoflagger_polcalstrat = None
    preflag_aoflagger_targetstrat = None

    def __init__(self, filename=None, **kwargs):
        self.logger = logging.getLogger('PREFLAG')
        config = ConfigParser.ConfigParser()  # Initialise the config parser
        if filename:
            config.readfp(open(filename))
            self.logger.info('### Configuration file ' + filename + ' successfully read! ###')
        else:
            config.readfp(open(default_cfg))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        subs_setinit.setinitdirs(self)


    ###############################################
    ##### Function to execute the preflagging #####
    ###############################################

    def go(self):
        """
        Executes the complete preflag step with the parameters indicated in the config-file in the following order:
        shadow
        edges
        ghosts
        manualflag
        aoflagger
        """
        self.logger.info('########## Starting Pre-flagging step ##########')
        self.shadow()
        self.edges()
        self.ghosts()
        self.manualflag()
        self.aoflagger()
        self.logger.info('########## Pre-flagging step done ##########')

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

        self.logger.debug('### Shadowed antenna flagging step started ###')

        # Create the parameters for the parameter file for the shadowing status

        preflagfluxcalshadow = get_param_def(self, 'preflag_fluxcal_shadow', False ) # Is the fluxcal shadow flagged?
        preflagpolcalshadow = get_param_def(self, 'preflag_polcal_shadow', False ) # Is the polcal shadow flagged?
        preflagtargetbeamsshadow = get_param_def(self, 'preflag_targetbeams_shadow', np.full((beams), False) ) # Are the target beams shadow flagged?

        # Flag shadowed antennas

        if self.preflag_shadow:
            self.logger.info('# Flagging shadowed antennas #')
            # Flag the flux calibrator
            if preflagfluxcalshadow:
                self.logger.info('# Shadowed antenna(s) for flux calibrator were already flagged #')
            else:
                if self.fluxcal != '' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    self.logger.debug('# Flagging shadowed antennas for flux calibrator #')
                    fc_shadow = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", mode="shadow", flagbackup=False)'
                    casacmd = [fc_shadow]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    preflagfluxcalshadow = True
                else:
                    self.logger.warning('# Flux calibrator dataset not specified or dataset not available. Not flagging shadowed antennas for flux calibrator #')
                    preflagfluxcalshadow = False
            # Flag the polarised calibrator
            if preflagpolcalshadow:
                self.logger.info('# Shadowed antenna(s) for polarised calibrator were already flagged #')
            else:
                if self.polcal != '' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    self.logger.debug('# Flagging shadowed antennas for polarised calibrator #')
                    pc_shadow = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", mode="shadow", flagbackup=False)'
                    casacmd = [pc_shadow]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    preflagpolcalshadow = True
                else:
                    self.logger.warning('# Polarised calibrator dataset not specified or dataset not available. Not flagging shadowed antennas for polarised calibrator #')
                    preflagpolcalshadow = False
            # Flag the target beams
            if self.target != '':
                datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                for vis in datasets:
                    if preflagtargetbeamsshadow[int(vis.split('/')[-3])]:
                        self.logger.info('# Shadowed antenna(s) for beam ' + vis.split('/')[-3] + ' were already flagged #')
                    else:
                        self.logger.debug('# Flagging shadowed antennas for beam ' + vis.split('/')[-3] + ' #')
                        tg_shadow = 'flagdata(vis="' + str(vis) + '", autocorr=True, flagbackup=False)'
                        casacmd = [tg_shadow]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                        preflagtargetbeamsshadow[int(vis.split('/')[-3])] = True
            else:
                self.logger.warning('# No target dataset specified! Not flagging shadowed antennas for target datasets #')
        else:
            self.logger.warning('# Shadowed antenna(s) are not flagged! #')
        self.logger.debug('### Shadowed antenna flagging step done ###')

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

        self.logger.debug('### Starting to flag the edges of the subbands ###')

        # Create the parameters for the parameter file for the shadowing status

        preflagfluxcaledges = get_param_def(self, 'preflag_fluxcal_edges', False ) # Edges of fluxcal flagged?
        preflagpolcaledges = get_param_def(self, 'preflag_polcal_edges', False ) # Edges of polcal flagged?
        preflagtargetbeamsedges = get_param_def(self, 'preflag_targetbeams_edges', np.full((beams), False) ) # Edges of target beams flagged?

        if self.preflag_edges:
            self.logger.info('# Flagging subband edges #')
            # Flag the flux calibrator
            if preflagfluxcaledges:
                self.logger.info('# Subband edges for flux calibrator were already flagged #')
            else:
                if self.fluxcal != '' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    # Flag the subband edges of the flux calibrator data set
                    self.logger.debug('# Flagging subband edges for flux calibrator #')
                    # Get the number of channels of the flux calibrator data set
                    nchannel = self._getnchan(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
                    # Calculate the subband edges of the flux calibrator data set
                    a = range(0, nchannel, 64)
                    b = range(1, nchannel, 64)
                    c = range(63, nchannel, 64)
                    l = a + b + c
                    m = ';'.join(str(ch) for ch in l)
                    fc_edges_flagcmd = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", spw="0:' + m + '", flagbackup=False)'
                    casacmd_fcflag = [fc_edges_flagcmd]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd_fcflag, raise_on_severe=True, timeout=1800)
                    preflagfluxcaledges = True
                else:
                    self.logger.warning('# No flux calibrator dataset specified. Subband edges of flux calibrator will not be flagged! #')
                    preflagfluxcaledges = False
            # Flag the polarised calibrator
            if preflagpolcaledges:
                self.logger.info('# Subband edges for polarised calibrator were already flagged #')
            else:
                if self.polcal != '' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    # Flag the subband edges of the polarised calibrator data set
                    self.logger.debug('# Flagging subband edges for polarised calibrator #')
                    # Get the number of channels of the polarised calibrator data set
                    nchannel = self._getnchan(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
                    # Calculate the subband edges of the polarised calibrator data set
                    a = range(0, nchannel, 64)
                    b = range(1, nchannel, 64)
                    c = range(63, nchannel, 64)
                    l = a + b + c
                    m = ';'.join(str(ch) for ch in l)
                    pc_edges_flagcmd = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", spw="0:' + m + '", flagbackup=False)'
                    casacmd_pcflag = [pc_edges_flagcmd]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd_pcflag, raise_on_severe=True, timeout=1800)
                    preflagpolcaledges = True
                else:
                    self.logger.warning('# No polarised calibrator dataset specified. Subband edges of polarised calibrator will not be flagged! #')
                    preflagpolcaledges = False
            if self.target != '':
                # Flag the subband edges of the the target beam datasets
                datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target) # Collect all the available target beam datasets
                for vis in datasets:
                    if preflagtargetbeamsedges[int(vis.split('/')[-3])]:
                        self.logger.info('# Subband edges for target beam ' + vis.split('/')[-3] + ' were already flagged #')
                    else:
                        self.logger.debug('# Flagging subband edges for target beam ' + vis.split('/')[-3] + ' #')
                        nchannel = self._getnchan(vis)
                        # Calculate the subband edges for each target beam data set
                        a = range(0, nchannel, 64)
                        b = range(1, nchannel, 64)
                        c = range(63, nchannel, 64)
                        l = a + b + c
                        m = ';'.join(str(ch) for ch in l)
                        tg_edges_flagcmd = 'flagdata(vis="' + vis + '", spw="0:' + m + '", flagbackup=False)'
                        casacmd_tgflag = [tg_edges_flagcmd]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd_tgflag, raise_on_severe=True, timeout=1800)
                        preflagtargetbeamsedges[int(vis.split('/')[-3])] = True
            else:
                self.logger.warning('# No target dataset specified. Subband edges of target dataset(s) will not be flagged! #')
        else:
            self.logger.warning('# Subband edges are not flagged! #')
        self.logger.debug('### Finished flagging subband edges ###')

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

        self.logger.debug('### Starting to flag the ghost channels ###')

        # Create the parameters for the parameter file for the shadowing status

        preflagfluxcalghosts = get_param_def(self, 'preflag_fluxcal_ghosts', False ) # Ghosts of fluxcal flagged?
        preflagpolcalghosts = get_param_def(self, 'preflag_polcal_ghosts', False ) # Ghosts of polcal flagged?
        preflagtargetbeamsghosts = get_param_def(self, 'preflag_targetbeams_ghosts', np.full((beams), False) ) # Ghosts of target beams flagged?

        if self.preflag_ghosts:
            self.logger.info('# Flagging ghost channels #')
            # Flag the ghost channels in the flux calibrator
            if preflagfluxcalghosts:
                self.logger.info('# Ghost channels for flux calibrator were already flagged #')
            else:
                if self.fluxcal != '' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    # Flag the ghosts in the flux calibrator data set
                    self.logger.debug('# Flagging ghost channels for flux calibrator #')
                    # Get the number of channels of the flux calibrator data set
                    nchannel = self._getnchan(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
                    # Calculate the ghost positions for the flux calibrator data set
                    a = range(16, nchannel, 64)
                    b = range(48, nchannel, 64)
                    l = a + b
                    m = ';'.join(str(ch) for ch in l)
                    fc_ghosts_flagcmd = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", spw="0:' + m + '", flagbackup=False)'
                    casacmd_fcflag = [fc_ghosts_flagcmd]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd_fcflag, raise_on_severe=True, timeout=1800)
                    preflagfluxcalghosts = True
                else:
                    self.logger.warning('# No flux calibrator dataset specified. Ghosts in flux calibrator dataset will not be flagged! #')
                    preflagfluxcalghosts = False
            # Flag the ghost channels in the polarised calibrator
            if preflagpolcalghosts:
                self.logger.info('# Ghost channels for polarised calibrator were already flagged #')
            else:
                if self.polcal != '' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    # Flag the ghosts in the polarised calibrator data set
                    self.logger.debug('# Flagging ghost channels for polarised calibrator #')
                    # Get the number of channels of the polarised calibrator data set
                    nchannel = self._getnchan(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
                    # Calculate the subband edges of the polarised calibrator data set
                    a = range(0, nchannel, 64)
                    b = range(1, nchannel, 64)
                    l = a + b
                    m = ';'.join(str(ch) for ch in l)
                    pc_ghosts_flagcmd = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", spw="0:' + m + '", flagbackup=False)'
                    casacmd_pcflag = [pc_ghosts_flagcmd]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd_pcflag, raise_on_severe=True, timeout=1800)
                    preflagpolcalghosts = True
                else:
                    self.logger.warning('# No polarised calibrator dataset specified. Ghosts in polarised calibrator will not be flagged! #')
                    preflagpolcalghosts = False
            if self.target != '':
                # Flag the ghosts in the target beam datasets
                datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target) # Collect all the available target beam datasets
                for vis in datasets:
                    if preflagtargetbeamsghosts[int(vis.split('/')[-3])]:
                        self.logger.info('# Ghost channels for target beam ' + vis.split('/')[-3] + ' were already flagged #')
                    else:
                        self.logger.debug('# Flagging ghost channels for target beam ' + vis.split('/')[-3] + ' #')
                        nchannel = self._getnchan(vis)
                        # Calculate the ghost channels for each target beam data set
                        a = range(0, nchannel, 64)
                        b = range(1, nchannel, 64)
                        l = a + b
                        m = ';'.join(str(ch) for ch in l)
                        tg_ghosts_flagcmd = 'flagdata(vis="' + vis + '", spw="0:' + m + '", flagbackup=False)'
                        casacmd_tgflag = [tg_ghosts_flagcmd]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd_tgflag, raise_on_severe=True, timeout=1800)
                        preflagtargetbeamsghosts[int(vis.split('/')[-3])] = True
            else:
                self.logger.warning('# No target dataset specified. Ghosts in target dataset(s) will not be flagged! #')
        else:
            self.logger.warning('# Ghost channels are not flagged! #')
        self.logger.debug('### Finished flagging ghost channels ###')

        # Save the derived parameters for the subband edges flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_ghosts', preflagfluxcalghosts)
        subs_param.add_param(self, 'preflag_polcal_ghosts', preflagpolcalghosts)
        subs_param.add_param(self, 'preflag_targetbeams_ghosts', preflagtargetbeamsghosts)

    def manualflag(self):
        """
        Use drivecasa and the CASA task flagdata to flag entire antennas, baselines, correlations etc. before doing any other calibration.
        """
        if self.preflag_manualflag:
            self.logger.debug('### Manual flagging step started ###')
            self.manualflag_auto()
            self.manualflag_antenna()
            self.manualflag_corr()
            self.manualflag_baseline()
            self.manualflag_channel()
            self.manualflag_time()
            self.logger.debug('###  Manual flagging step done ###')

    def aoflagger(self):
        """
        Runs aoflagger on the datasets with the strategies given in the config-file. Creates and applies a preliminary bandpass before executing the strategy for better performance of the flagging routines. Strategies for calibrators and target fields normally differ.
        """
        if self.preflag_aoflagger:
            self.logger.debug('### Pre-flagging with AOFlagger started ###')
            self.aoflagger_bandpass()
            self.aoflagger_flag()
            self.logger.debug('### Pre-flagging with AOFlagger done ###')
        else:
            self.logger.warning('### No flagging with AOflagger done! Your data might be contaminated by RFI! ###')



    ############################################################
    ##### Subfunctions for the different manual_flag steps #####
    ############################################################

    def manualflag_auto(self):
        """
        Function to flag the auto-correlations
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the manualflag step to flag the auto-correlations

        preflagfluxcalmanualflagauto = get_param_def(self, 'preflag_fluxcal_manualflag_auto', False ) # Auto-correlations of fluxcal flagged?
        preflagpolcalmanualflagauto = get_param_def(self, 'preflag_polcal_manualflag_auto', False ) # Auto-correlations of polcal flagged?
        preflagtargetbeamsmanualflagauto = get_param_def(self, 'preflag_targetbeams_manualflag_auto', np.full((beams), False) ) # Auto-correlations of target beams flagged?

        if self.preflag_manualflag_auto:
            self.logger.info('# Flagging auto-correlations #')
            # Flag the auto-correlations for the flux calibrator
            if preflagfluxcalmanualflagauto and self.preflag_manualflag_fluxcal:
                self.logger.info('# Auto-correlations for flux calibrator were already flagged #')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    fc_auto = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", autocorr=True, flagbackup=False)'
                    casacmd = [fc_auto]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged auto-correlations for flux calibrator #')
                    preflagfluxcalmanualflagauto = True
                else:
                    preflagfluxcalmanualflagauto = False
                    self.logger.warning('# No flux calibrator dataset specified. Auto-correlations for flux calibrator dataset will not be flagged! #')
            # Flag the auto-correlations for the polarised calibrator
            if preflagpolcalmanualflagauto and self.preflag_manualflag_polcal:
                self.logger.info('# Auto-correlations for polarised calibrator were already flagged #')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    pc_auto = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", autocorr=True, flagbackup=False)'
                    casacmd = [pc_auto]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged auto-correlations for polarised calibrator #')
                    preflagpolcalmanualflagauto = True
                else:
                    preflagpolcalmanualflagauto = False
                    self.logger.warning('# No polarised calibrator dataset specified. Auto-correlations for polariased calibrator dataset will not be flagged! #')
            # Flag the auto-correlations for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                    self.logger.debug('# Flagging auto-correlations for all target beams #')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                    self.logger.debug('# Flagging auto-correlations for selected target beams #')
                for vis in datasets:
                    if preflagtargetbeamsmanualflagauto[int(vis.split('/')[-3])]:
                        self.logger.info('# Auto-correlations for target beam ' + vis.split('/')[-3] + ' were already flagged #')
                    else:
                        self.logger.debug('# Flagging auto-correlations for target beam ' + vis.split('/')[-3] + ' #')
                        tg_auto = 'flagdata(vis="' + str(vis) + '", autocorr=True, flagbackup=False)'
                        casacmd = [tg_auto]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                        preflagtargetbeamsmanualflagauto[int(vis.split('/')[-3])] = True
            else:
                self.logger.warning('# Target dataset not specified. Auto-correlations for target beam dataset(s) will not be flagged! #')

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

        preflagfluxcalmanualflagantenna = get_param_def(self, 'preflag_fluxcal_manualflag_antenna', np.full((1), '', dtype='U50') ) # Flagged antennas of fluxcal?
        preflagpolcalmanualflagantenna = get_param_def(self, 'preflag_polcal_manualflag_antenna', np.full((1), '', dtype='U50') ) # Flagged antennas of polcal?
        preflagtargetbeamsmanualflagantenna = get_param_def(self, 'preflag_targetbeams_manualflag_antenna', np.full((beams), '', dtype='U50') ) # Flagged antennas of target beams?

        if self.preflag_manualflag_antenna != '':
            self.logger.info('# Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' #')
            # Flag antenna(s) for flux calibrator
            if preflagfluxcalmanualflagantenna[0] == self.preflag_manualflag_antenna and self.preflag_manualflag_fluxcal == True:
                self.logger.info('# Antenna(s) ' + self.preflag_manualflag_antenna + ' for flux calibrator were already flagged #')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    fc_ant = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                    casacmd = [fc_ant]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged antenna(s) ' +  self.preflag_manualflag_antenna + ' for flux calibrator #')
                    spltant = self.preflag_manualflag_antenna.split(',')
                    for ant in spltant:
                        if preflagfluxcalmanualflagantenna[0].find(ant) == -1:
                            if preflagfluxcalmanualflagantenna[0] == '':
                                preflagfluxcalmanualflagantenna[0] = ant
                            else:
                                preflagfluxcalmanualflagantenna[0] = preflagfluxcalmanualflagantenna[0] + ',' + ant
                else:
                    self.logger.warning('# No flux calibrator dataset specified. Specified antenna(s) for flux calibrator dataset will not be flagged! #')
            # Flag antenna(s) for polarised calibrator
            if preflagpolcalmanualflagantenna[0] == self.preflag_manualflag_antenna and self.preflag_manualflag_polcal == True:
                self.logger.info('# Antenna(s) ' + self.preflag_manualflag_antenna + ' for polarised calibrator were already flagged #')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    pc_ant = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                    casacmd = [pc_ant]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged antenna(s) ' +  self.preflag_manualflag_antenna + ' for polarised calibrator #')
                    spltant = self.preflag_manualflag_antenna.split(',')
                    for ant in spltant:
                        if preflagpolcalmanualflagantenna[0].find(ant) == -1:
                            if preflagpolcalmanualflagantenna[0] == '':
                                preflagpolcalmanualflagantenna[0] = ant
                            else:
                                preflagpolcalmanualflagantenna[0] = preflagpolcalmanualflagantenna[0] + ',' + ant
                else:
                    self.logger.warning('# No polarised calibrator dataset specified. Specified antenna(s) for polarised calibrator dataset will not be flagged! #')
            # Flag antenna(s) for target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                    self.logger.debug('# Flagging antenna(s) ' +  self.preflag_manualflag_antenna + ' for all target beams #')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                    self.logger.debug('# Flagging antenna(s) ' +  self.preflag_manualflag_antenna + ' for selected target beams #')
                for vis in datasets:
                    if preflagtargetbeamsmanualflagantenna[int(vis.split('/')[-3])] == self.preflag_manualflag_antenna:
                        self.logger.info('# Antenna(s) ' + self.preflag_manualflag_antenna + ' for target beam ' + vis.split('/')[-3] + ' were already flagged #')
                    else:
                        self.logger.debug('# Flagging antenna(s) ' + self.preflag_manualflag_antenna + ' for target beam ' + vis.split('/')[-3] + ' #')
                        tg_ant = 'flagdata(vis="' + str(vis) + '", antenna="' + self.preflag_manualflag_antenna + '", flagbackup=False)'
                        casacmd = [tg_ant]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                        spltant = self.preflag_manualflag_antenna.split(',')
                        for ant in spltant:
                            if preflagtargetbeamsmanualflagantenna[int(vis.split('/')[-3])].find(ant) == -1:
                                if preflagtargetbeamsmanualflagantenna[int(vis.split('/')[-3])] == '':
                                    preflagtargetbeamsmanualflagantenna[int(vis.split('/')[-3])] = ant
                                else:
                                    preflagtargetbeamsmanualflagantenna[int(vis.split('/')[-3])] = preflagtargetbeamsmanualflagantenna[int(vis.split('/')[-3])] + ',' + ant
            else:
                self.logger.warning('# Target dataset not specified. Specified antenna(s) for target beam dataset(s) will not be flagged! #')

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

        preflagfluxcalmanualflagcorr = get_param_def(self, 'preflag_fluxcal_manualflag_corr', np.full((1), '', dtype='U50') ) # Flagged correlations of fluxcal?
        preflagpolcalmanualflagcorr = get_param_def(self, 'preflag_polcal_manualflag_corr', np.full((1), '', dtype='U50') ) # Flagged correlations of polcal?
        preflagtargetbeamsmanualflagcorr = get_param_def(self, 'preflag_targetbeams_manualflag_corr', np.full((beams), '', dtype='U50') ) # Flagged correlations of target beams?

        if self.preflag_manualflag_corr != '':
            self.logger.info('# Flagging correlation(s) ' + self.preflag_manualflag_corr + ' #')
            # Flag correlation(s) for flux calibrator
            if preflagfluxcalmanualflagcorr[0] == self.preflag_manualflag_corr and self.preflag_manualflag_fluxcal == True:
                self.logger.info('# Correlation(s) ' + self.preflag_manualflag_corr + ' for flux calibrator were already flagged #')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    subs_setinit.setinitdirs(self)
                    fc_corr = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                    casacmd = [fc_corr]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged correlation(s) ' +  self.preflag_manualflag_corr + ' for flux calibrator #')
                    spltcorr = self.preflag_manualflag_corr.split(',')
                    for corr in spltcorr:
                        if preflagfluxcalmanualflagcorr[0].find(corr) == -1:
                            if preflagfluxcalmanualflagcorr[0] == '':
                                preflagfluxcalmanualflagcorr[0] = corr
                            else:
                                preflagfluxcalmanualflagcorr[0] = preflagfluxcalmanualflagcorr[0] + ',' + corr
                else:
                    self.logger.warning('# No flux calibrator dataset specified. Specified correlation(s) for flux calibrator dataset will not be flagged! #')
            # Flag correlation(s) for flux calibrator
            if preflagpolcalmanualflagcorr[0] == self.preflag_manualflag_corr and self.preflag_manualflag_polcal == True:
                self.logger.info('# Correlation(s) ' + self.preflag_manualflag_corr + ' for polarised calibrator were already flagged #')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    subs_setinit.setinitdirs(self)
                    pc_corr = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                    casacmd = [pc_corr]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged correlation(s) ' +  self.preflag_manualflag_corr + ' for polarised calibrator #')
                    spltcorr = self.preflag_manualflag_corr.split(',')
                    for corr in spltcorr:
                        if preflagpolcalmanualflagcorr[0].find(corr) == -1:
                            if preflagpolcalmanualflagcorr[0] == '':
                                preflagpolcalmanualflagcorr[0] = corr
                            else:
                                preflagpolcalmanualflagcorr[0] = preflagpolcalmanualflagcorr[0] + ',' + corr
                else:
                    self.logger.warning('# No polarised calibrator dataset specified. Specified correlation(s) for polarised calibrator dataset will not be flagged! #')
            # Flag correlation(s) for target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                    self.logger.debug('# Flagging correlation(s) ' +  self.preflag_manualflag_corr + ' for all target beams #')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                    self.logger.debug('# Flagging correlation(s) ' +  self.preflag_manualflag_corr + ' for selected target beams #')
                for vis in datasets:
                    if preflagtargetbeamsmanualflagcorr[int(vis.split('/')[-3])] == self.preflag_manualflag_corr:
                        self.logger.info('# Correlation(s) ' + self.preflag_manualflag_corr + ' for target beam ' + vis.split('/')[-3] + ' were already flagged #')
                    else:
                        self.logger.debug('# Flagging correlations(s) ' + self.preflag_manualflag_corr + ' for target beam ' + vis.split('/')[-3] + ' #')
                        tg_corr = 'flagdata(vis="' + str(vis) + '", correlation="' + self.preflag_manualflag_corr + '", flagbackup=False)'
                        casacmd = [tg_corr]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                        spltcorr = self.preflag_manualflag_corr.split(',')
                        for corr in spltcorr:
                            if preflagtargetbeamsmanualflagcorr[int(vis.split('/')[-3])].find(corr) == -1:
                                if preflagtargetbeamsmanualflagcorr[int(vis.split('/')[-3])] == '':
                                    preflagtargetbeamsmanualflagcorr[int(vis.split('/')[-3])] = corr
                                else:
                                    preflagtargetbeamsmanualflagcorr[int(vis.split('/')[-3])] = preflagtargetbeamsmanualflagcorr[int(vis.split('/')[-3])] + ',' + corr
            else:
                self.logger.warning('# Target dataset not specified. Specified correlation(s) for target beam dataset(s) will not be flagged! #')

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

        preflagfluxcalmanualflagbaseline = get_param_def(self, 'preflag_fluxcal_manualflag_baseline', np.full((1), '', dtype='U50')) # Flagged baselines of fluxcal?
        preflagpolcalmanualflagbaseline = get_param_def(self, 'preflag_polcal_manualflag_baseline', np.full((1), '', dtype='U50') ) # Flagged baselines of polcal?
        preflagtargetbeamsmanualflagbaseline = get_param_def(self, 'preflag_targetbeams_manualflag_baseline', np.full((beams), '', dtype='U50') ) # Flagged baselines of target beams?

        if self.preflag_manualflag_baseline != '':
            self.logger.info('# Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' #')
            # Flag correlation(s) for the flux calibrator
            if preflagfluxcalmanualflagbaseline[0] == self.preflag_manualflag_baseline and self.preflag_manualflag_fluxcal == True:
                self.logger.info('# Baseline(s) ' + self.preflag_manualflag_baseline + ' for flux calibrator were already flagged #')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    fc_baseline = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                    casacmd = [fc_baseline]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged baseline(s) ' +  self.preflag_manualflag_baseline + ' for flux calibrator #')
                    spltbaseline = self.preflag_manualflag_baseline.split(',')
                    for baseline in spltbaseline:
                        if preflagfluxcalmanualflagbaseline[0].find(baseline) == -1:
                            if preflagfluxcalmanualflagbaseline[0] == '':
                                preflagfluxcalmanualflagbaseline[0] = baseline
                            else:
                                preflagfluxcalmanualflagbaseline[0] = preflagfluxcalmanualflagbaseline[0] + ',' + baseline
                else:
                    self.logger.warning('# No flux calibrator dataset specified. Specified baselines(s) for flux calibrator dataset will not be flagged! #')
            # Flag correlation(s) for the polarised calibrator
            if preflagpolcalmanualflagbaseline[0] == self.preflag_manualflag_baseline and self.preflag_manualflag_polcal == True:
                self.logger.info('# Baseline(s) ' + self.preflag_manualflag_baseline + ' for polarised calibrator were already flagged #')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    pc_baseline = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                    casacmd = [pc_baseline]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged baseline(s) ' +  self.preflag_manualflag_baseline + ' for polarised calibrator #')
                    spltbaseline = self.preflag_manualflag_baseline.split(',')
                    for baseline in spltbaseline:
                        if preflagpolcalmanualflagbaseline[0].find(baseline) == -1:
                            if preflagpolcalmanualflagbaseline[0] == '':
                                preflagpolcalmanualflagbaseline[0] = baseline
                            else:
                                preflagpolcalmanualflagbaseline[0] = preflagpolcalmanualflagbaseline[0] + ',' + baseline
                else:
                    self.logger.warning('# No polarised calibrator dataset specified. Specified baselines(s) for polarised calibrator dataset will not be flagged! #')
            # Flag correlation(s) for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                    self.logger.debug('# Flagging baseline(s) ' +  self.preflag_manualflag_baseline + ' for all target beams #')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                    self.logger.debug('# Flagging baseline(s) ' +  self.preflag_manualflag_baseline + ' for selected target beams #')
                for vis in datasets:
                    if preflagtargetbeamsmanualflagbaseline[int(vis.split('/')[-3])]  == self.preflag_manualflag_baseline:
                        self.logger.info('# Correlation(s) ' + self.preflag_manualflag_baseline + ' for target beam ' + vis.split('/')[-3] + ' were already flagged #')
                    else:
                        self.logger.debug('# Flagging baseline(s) ' + self.preflag_manualflag_baseline + ' for target beam ' + vis.split('/')[-3] + ' #')
                        tg_baseline = 'flagdata(vis="' + str(vis) + '", antenna="' + self.preflag_manualflag_baseline + '", flagbackup=False)'
                        casacmd = [tg_baseline]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                        for baseline in spltbaseline:
                            if preflagtargetbeamsmanualflagbaseline[int(vis.split('/')[-3])].find(baseline) == -1:
                                if preflagtargetbeamsmanualflagbaseline[int(vis.split('/')[-3])] == '':
                                    preflagtargetbeamsmanualflagbaseline[int(vis.split('/')[-3])] = baseline
                                else:
                                    preflagtargetbeamsmanualflagbaseline[int(vis.split('/')[-3])] = preflagtargetbeamsmanualflagbaseline[int(vis.split('/')[-3])] + ',' + baseline
            else:
                self.logger.warning('# Target dataset not specified. Specified baseline(s) for target beam dataset(s) will not be flagged! #')

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

        preflagfluxcalmanualflagchannel = get_param_def(self, 'preflag_fluxcal_manualflag_channel', np.full((1), '', dtype='U50') ) # Flagged channels of fluxcal?
        preflagpolcalmanualflagchannel = get_param_def(self, 'preflag_polcal_manualflag_channel', np.full((1), '', dtype='U50') ) # Flagged channels of polcal?
        preflagtargetbeamsmanualflagchannel = get_param_def(self, 'preflag_targetbeams_manualflag_channel', np.full((beams), '', dtype='U50') ) # Flagged channels of target beams?

        if self.preflag_manualflag_channel != '':
            self.logger.info('# Flagging channel(s) ' + self.preflag_manualflag_channel + ' #')
            # Flag channel(s) for the flux calibrator
            if preflagfluxcalmanualflagchannel[0] == self.preflag_manualflag_channel and self.preflag_manualflag_fluxcal == True:
                self.logger.info('# Channel(s) ' + self.preflag_manualflag_channel + ' for flux calibrator were already flagged #')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    fc_channel = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                    casacmd = [fc_channel]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged channel(s) ' + self.preflag_manualflag_channel + ' for flux calibrator #')
                    spltchannel = self.preflag_manualflag_channel.split(',')
                    for channel in spltchannel:
                        if preflagfluxcalmanualflagchannel[0].find(channel) == -1:
                            if preflagfluxcalmanualflagchannel[0] == '':
                                preflagfluxcalmanualflagchannel[0] = channel
                            else:
                                preflagfluxcalmanualflagchannel[0] = preflagfluxcalmanualflagchannel[0] + ',' + channel
                else:
                    self.logger.warning('# No flux calibrator dataset specified. Specified channel range(s) for flux calibrator dataset will not be flagged! #')
            # Flag channel(s) for the polarised calibrator
            if preflagpolcalmanualflagchannel[0] == self.preflag_manualflag_channel and self.preflag_manualflag_polcal == True:
                self.logger.info('# Channel(s) ' + self.preflag_manualflag_channel + ' for polarised calibrator were already flagged #')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    pc_channel = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                    casacmd = [pc_channel]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged channel(s) ' + self.preflag_manualflag_channel + ' for polarised calibrator #')
                    spltchannel = self.preflag_manualflag_channel.split(',')
                    for channel in spltchannel:
                        if preflagpolcalmanualflagchannel[0].find(channel) == -1:
                            if preflagpolcalmanualflagchannel[0] == '':
                                preflagpolcalmanualflagchannel[0] = channel
                            else:
                                preflagpolcalmanualflagchannel[0] = preflagpolcalmanualflagchannel[0] + ',' + channel
                else:
                    self.logger.warning('# No polarised calibrator dataset specified. Specified channel range(s) for polarised calibrator dataset will not be flagged! #')
            # Flag channel(s) for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                    self.logger.debug('# Flagging channel(s) ' + self.preflag_manualflag_channel + ' for all target beams #')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                    self.logger.debug('# Flagging channel(s) ' + self.preflag_manualflag_channel + ' for selected target beams #')
                for vis in datasets:
                    if preflagtargetbeamsmanualflagchannel[int(vis.split('/')[-3])] == self.preflag_manualflag_channel:
                        self.logger.info('# Correlation(s) ' + self.preflag_manualflag_channel + ' for target beam ' + vis.split('/')[-3] + ' were already flagged #')
                    else:
                        self.logger.debug('# Flagging channel(s) ' + self.preflag_manualflag_channel + ' for target beam ' + vis.split('/')[-3] + ' #')
                        tg_channel = 'flagdata(vis="' + str(vis) + '", spw="0:' + self.preflag_manualflag_channel + '", flagbackup=False)'
                        casacmd = [tg_channel]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                        for channel in spltchannel:
                            if preflagtargetbeamsmanualflagchannel[int(vis.split('/')[-3])].find(channel) == -1:
                                if preflagtargetbeamsmanualflagchannel[int(vis.split('/')[-3])] == '':
                                    preflagtargetbeamsmanualflagchannel[int(vis.split('/')[-3])] = channel
                                else:
                                    preflagtargetbeamsmanualflagchannel[int(vis.split('/')[-3])] = preflagtargetbeamsmanualflagchannel[int(vis.split('/')[-3])] + ',' + channel
            else:
                self.logger.warning('# Target dataset not specified. Specified channel range(s) for target beam dataset(s) will not be flagged! #')

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

        preflagfluxcalmanualflagtime = get_param_def(self, 'preflag_fluxcal_manualflag_time', np.full((1), '', dtype='U50') ) # Flagged time range(s) of fluxcal?
        preflagpolcalmanualflagtime = get_param_def(self, 'preflag_polcal_manualflag_time', np.full((1), '', dtype='U50') ) # Flagged time range(s) of polcal?
        preflagtargetbeamsmanualflagtime = get_param_def(self, 'preflag_targetbeams_manualflag_time', np.full((beams), '', dtype='U50') ) # Flagged time range(s) of target beams?

        if self.preflag_manualflag_time != '':
            self.logger.info('# Flagging time range ' + self.preflag_manualflag_time + ' #')
            # Flag time range for the flux calibrator
            if preflagfluxcalmanualflagtime[0] == self.preflag_manualflag_time and self.preflag_manualflag_fluxcal == True:
                self.logger.info('# Time range ' + self.preflag_manualflag_time + ' for flux calibrator was already flagged #')
            else:
                if self.preflag_manualflag_fluxcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    fc_time = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", timerange="' + self.preflag_manualflag_time + '", flagbackup=False)'
                    casacmd = [fc_time]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged time range ' + self.preflag_manualflag_time + ' for flux calibrator #')
                    splttime = self.preflag_manualflag_time.split(',')
                    for time in splttime:
                        if preflagfluxcalmanualflagtime[0].find(time) == -1:
                            if preflagfluxcalmanualflagtime[0] == '':
                                preflagfluxcalmanualflagtime[0] = time
                            else:
                                preflagfluxcalmanualflagtime[0] = preflagfluxcalmanualflagtime[0] + ',' + time
                else:
                    self.logger.warning('# No flux calibrator dataset specified. Specified time range(s) for flux calibrator dataset will not be flagged! #')
            # Flag time range for the polarised calibrator
            if preflagpolcalmanualflagtime[0] == self.preflag_manualflag_time and self.preflag_manualflag_polcal == True:
                self.logger.info('# Time range ' + self.preflag_manualflag_time + ' for polarised calibrator was already flagged #')
            else:
                if self.preflag_manualflag_polcal and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    pc_time = 'flagdata(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", timerange="' + self.preflag_manualflag_time + '", flagbackup=False)'
                    casacmd = [pc_time]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    self.logger.debug('# Flagged time range ' + self.preflag_manualflag_time + ' for polarised calibrator #')
                    splttime = self.preflag_manualflag_time.split(',')
                    for time in splttime:
                        if preflagpolcalmanualflagtime[0].find(time) == -1:
                            if preflagpolcalmanualflagtime[0] == '':
                                preflagpolcalmanualflagtime[0] = time
                            else:
                                preflagpolcalmanualflagtime[0] = preflagpolcalmanualflagtime[0] + ',' + time
                else:
                    self.logger.warning('# No polariased calibrator dataset specified. Specified time range(s) for polarised calibrator dataset will not be flagged! #')
            # Flag time range for the target beams
            if self.preflag_manualflag_target:
                if self.preflag_manualflag_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                    self.logger.debug('# Flagging time range ' + self.preflag_manualflag_time + ' for all target beams #')
                else:
                    beams = self.preflag_manualflag_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                    self.logger.debug('# Flagging time range ' + self.preflag_manualflag_time + ' for selected target beams #')
                for vis in datasets:
                    if preflagtargetbeamsmanualflagtime[int(vis.split('/')[-3])] == self.preflag_manualflag_time:
                        self.logger.info('# Time range ' + self.preflag_manualflag_time + ' for target beam ' + vis.split('/')[-3] + ' was already flagged #')
                    else:
                        self.logger.debug('# Flagging time range(s) ' + self.preflag_manualflag_time + ' for target beam ' + vis.split('/')[-3] + ' #')
                        tg_time = 'flagdata(vis="' + str(vis) + '", timerange="' + self.preflag_manualflag_channel + '", flagbackup=False)'
                        casacmd = [tg_time]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                        for time in splttime:
                            if preflagtargetbeamsmanualflagtime[int(vis.split('/')[-3])].find(time) == -1:
                                if preflagtargetbeamsmanualflagtime[int(vis.split('/')[-3])] == '':
                                    preflagtargetbeamsmanualflagtime[int(vis.split('/')[-3])] = time
                                else:
                                    preflagtargetbeamsmanualflagtime[int(vis.split('/')[-3])] = preflagtargetbeamsmanualflagtime[int(vis.split('/')[-3])] + ',' + time
            else:
                self.logger.warning('# Target dataset not specified. Specified time range(s) for target beam dataset(s) will not be flagged! #')

        # Save the derived parameters for the channel flagging to the parameter file

        subs_param.add_param(self, 'preflag_fluxcal_manualflag_time', preflagfluxcalmanualflagtime)
        subs_param.add_param(self, 'preflag_polcal_manualflag_time', preflagpolcalmanualflagtime)
        subs_param.add_param(self, 'preflag_targetbeams_manualflag_time', preflagtargetbeamsmanualflagtime)

    ##########################################################
    ##### Subfunctions for the different AOFlagger steps #####
    ##########################################################

    def aoflagger_bandpass(self):
        """
        Creates a preliminary bandpass for flagging from the flux calibrator and applies it to all calibrators and target fields
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the bandpass step of the AOFLagger step

        preflagaoflaggerbandpassstatus = get_param_def(self, 'preflag_aoflagger_bandpass_status', False ) # Bandpass successfully derived
        preflagaoflaggerfluxcalbandpassapply = get_param_def(self, 'preflag_aoflagger_fluxcal_bandpass_apply', False ) # Bandpass applied to flux calibrator?
        preflagaoflaggerpolcalbandpassapply = get_param_def(self, 'preflag_aoflagger_polcal_bandpass_apply', False ) # Bandpass applied to polarised calibrator?
        preflagaoflaggertargetbeamsbandpassapply = get_param_def(self, 'preflag_aoflagger_targetbeams_bandpass_apply', np.full((beams), False) ) # Bandpass applied to target beams?

        if self.preflag_aoflagger_bandpass:
            # Check if bandpass was already derived and bandpass table is available
            if preflagaoflaggerbandpassstatus and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal[:-3] + '_Bpass'):
                self.logger.info('# Preliminary bandpass table was already derived #')
            # If not, derive the bandpass
            elif preflagaoflaggerbandpassstatus == False:
                if self.fluxcal != '' and  os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    fc_bpass = 'bandpass(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", caltable="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal[:-3] + '_Bpass")'
                    casacmd = [fc_bpass]
                    casa = drivecasa.Casapy()
                    casa.run_script(casacmd, raise_on_severe=False, timeout=1800)
                    if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal[:-3] + '_Bpass'):
                        preflagaoflaggerbandpassstatus = True
                        self.logger.info('# Derived preliminary bandpass table for AOFlagging #')
                    else:
                        preflagaoflaggerbandpassstatus = False
                        self.logger.error('# Preliminary bandpass table for flux calibrator was not derived successfully! #')
            else:
                self.logger.error('# Bandpass table not available. Preliminary bandpass cannot be applied #')
            # Apply the bandpass table
            if preflagaoflaggerbandpassstatus:
                if self.preflag_aoflagger_fluxcal:
                    if preflagaoflaggerfluxcalbandpassapply:
                        self.logger.info('# Preliminary bandpass was already applied to the flux calibrator #')
                    else:
                        # Apply the bandpass to the flux calibrator
                        if self.fluxcal != '' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                            self.logger.info('# Applying preliminary bandpass table to flux calibrator #')
                            fc_apply = 'applycal(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", gaintable=["' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal[:-3] + '_Bpass"])'
                            casacmd = [fc_apply]
                            casa = drivecasa.Casapy()
                            casa.run_script(casacmd, raise_on_severe=False, timeout=3600)
                            preflagaoflaggerfluxcalbandpassapply = True
                        else:
                            self.logger.warning('# Flux calibrator dataset not specified or not available. #')
                else:
                    self.logger.info('# Not applying preliminary bandpass to flux calibrator! #')
                if self.preflag_aoflagger_polcal:
                    if preflagaoflaggerpolcalbandpassapply:
                        self.logger.info('# Preliminary bandpass was already applied to the polarised calibrator #')
                    else:
                        # Apply the bandpass to the polarised calibrator
                        if self.polcal != '' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                            self.logger.info('# Applying preliminary bandpass table to polarised calibrator #')
                            pc_apply = 'applycal(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", gaintable=["' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal[:-3] + '_Bpass"])'
                            casacmd = [pc_apply]
                            casa = drivecasa.Casapy()
                            casa.run_script(casacmd, raise_on_severe=False, timeout=3600)
                            preflagaoflaggerpolcalbandpassapply = True
                        else:
                            self.logger.warning('# Polarised calibrator dataset not specified or not available. #')
                else:
                    self.logger.info('# Not applying preliminary bandpass to polarised calibrator! #')
                # Apply the bandpass to the target beams
                if self.preflag_aoflagger_target:
                    if self.target != '':
                        if self.preflag_aoflagger_targetbeams == 'all':
                            datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                            self.logger.info('# Applying preliminary bandpass to all target beams #')
                        else:
                            beams = self.preflag_aoflagger_targetbeams.split(",")
                            datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                            self.logger.info('# Applying preliminary bandpass to all selected target beam(s) #')
                        for vis in datasets:
                            if os.path.isdir(vis):
                                if preflagaoflaggertargetbeamsbandpassapply[int(vis.split('/')[-3])] == False:
                                    self.logger.info('# Applying preliminary bandpass table to target beam ' + vis.split('/')[-3] + ' #')
                                    tg_apply = 'applycal(vis="' + str(vis) + '", gaintable=["' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal[:-3] + '_Bpass"])'
                                    casacmd = [tg_apply]
                                    casa = drivecasa.Casapy()
                                    casa.run_script(casacmd, raise_on_severe=False, timeout=86400)
                                    preflagaoflaggertargetbeamsbandpassapply[int(vis.split('/')[-3])] = True
                                else:
                                    self.logger.info('# Preliminary bandpass for target beam ' + vis.split('/')[-3] + ' was already applied. #')
                            else:
                                self.logger.warning('# Target beam dataset ' + vis.split('/')[-3] + ' not available! #')
                    else:
                        self.logger.warning('# Target dataset not specified! #')
                else:
                    self.logger.warning('# Not applying preliminary bandpass to target beams! #')
            else:
                self.logger.error('# Bandpass table could not be applied #')

        # Save the derived parameters for the AOFlagger bandpass status to the parameter file

        subs_param.add_param(self, 'preflag_aoflagger_bandpass_status', preflagaoflaggerbandpassstatus)
        subs_param.add_param(self, 'preflag_aoflagger_fluxcal_bandpass_apply', preflagaoflaggerfluxcalbandpassapply)
        subs_param.add_param(self, 'preflag_aoflagger_polcal_bandpass_apply', preflagaoflaggerpolcalbandpassapply)
        subs_param.add_param(self, 'preflag_aoflagger_targetbeams_bandpass_apply', preflagaoflaggertargetbeamsbandpassapply)


    def aoflagger_flag(self):
        """
        Uses the aoflagger to flag the calibrators and the target data set(s). Uses the bandpass corrected visibilities if bandpass was derived and applied successfully beforehand.
        """
        subs_setinit.setinitdirs(self)
        beams = 37

        # Create the parameters for the parameter file for the bandpass step of the AOFlagger step

        preflagaoflaggerfluxcalflag = get_param_def(self, 'preflag_aoflagger_fluxcal_flag_status', False ) # AOFlagged the flux calibrator?
        preflagaoflaggerpolcalflag = get_param_def(self, 'preflag_aoflagger_polcal_flag_status', False ) # AOFlagged the polarised calibrator?
        preflagaoflaggertargetbeamsflag = get_param_def(self, 'preflag_aoflagger_targetbeams_flag_status', np.full((beams), False) ) # AOFlagged the target beams?

        if self.preflag_aoflagger:
            # Flag the flux calibrator with AOFLagger
            if self.preflag_aoflagger_fluxcal:
                if not preflagaoflaggerfluxcalflag:
                    if self.fluxcal !='' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal) and self.preflag_aoflagger_fluxcalstrat != '':
                        self.logger.info('# Using AOFlagger to flag flux calibrator dataset #')
                        preflagaoflaggerfluxcalbandpassapply = get_param_def(self, 'preflag_aoflagger_fluxcal_bandpass_apply', False) # Check if bandpass was applied successfully
                        if self.aoflagger_bandpass and preflagaoflaggerfluxcalbandpassapply:
                            os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_fluxcalstrat + ' -column CORRECTED_DATA ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
                            self.logger.debug('# Used AOFlagger to flag flux calibrator with preliminary bandpass applied #')
                            preflagaoflaggerfluxcalflag = True
                        elif self.aoflagger_bandpass == True and preflagaoflaggerfluxcalbandpassapply == False:
                            os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_fluxcalstrat + ' ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
                            self.logger.warning('# Used AOFlagger to flag flux calibrator without preliminary bandpass applied. Better results are usually obtained with a preliminary bandpass applied. #')
                            preflagaoflaggerfluxcalflag = True
                        elif self.aoflagger_bandpass == False:
                            os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_fluxcalstrat + ' ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
                            self.logger.info('# Used AOFlagger to flag flux calibrator without preliminary bandpass applied. Better results are usually obtained with a preliminary bandpass applied. #')
                            preflagaoflaggerfluxcalflag = True
                    else:
                        self.logger.error('# Flux calibrator dataset or strategy not defined properly or dataset not available. Not AOFlagging flux calibrator. #')
                else:
                    self.logger.info('# Flux calibrator was already flagged with AOFlagger! #')
            # Flag the polarised calibrator with AOFlagger
            if self.preflag_aoflagger_polcal:
                if preflagaoflaggerpolcalflag == False:
                    if self.polcal !='' and os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal) and self.preflag_aoflagger_polcalstrat != '':
                        self.logger.info('# Using AOFlagger to flag polarised calibrator dataset #')
                        preflagaoflaggerpolcalbandpassapply = get_param_def(self, 'preflag_aoflagger_polcal_bandpass_apply', False) # Check if bandpass was applied successfully
                        if self.aoflagger_bandpass and preflagaoflaggerpolcalbandpassapply:
                            os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_polcalstrat + ' -column CORRECTED_DATA ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
                            self.logger.debug('# Used AOFlagger to flag polarised calibrator with preliminary bandpass applied #')
                            preflagaoflaggerpolcalflag = True
                        elif self.aoflagger_bandpass == True and preflagaoflaggerpolcalbandpassapply == False:
                            os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_polcalstrat + ' ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
                            self.logger.warning('# Used AOFlagger to flag polarised calibrator without preliminary bandpass applied. Better results are usually obtained with a preliminary bandpass applied. #')
                            preflagaoflaggerpolcalflag = True
                        elif self.aoflagger_bandpass == False:
                            os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_polcalstrat + ' ' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
                            self.logger.info('# Used AOFlagger to flag polarised calibrator without preliminary bandpass applied. Better results are usually obtained with a preliminary bandpass applied. #')
                            preflagaoflaggerpolcalflag = True
                    else:
                        self.logger.error('# Polarised calibrator dataset or strategy not defined properly or dataset not available. Not AOFlagging polarised calibrator. #')
                else:
                    self.logger.info('# Polarised calibrator was already flagged with AOFlagger! #')
            # Flag the target beams with AOFlagger
            if self.preflag_aoflagger_target:
                if self.target !='' and self.preflag_aoflagger_targetstrat != '':
                    self.logger.info('# Using AOFlagger to flag selected target beam dataset(s) #')
                    preflagaoflaggertargetbeamsbandpassapply = get_param_def(self, 'preflag_aoflagger_targetbeams_bandpass_apply', np.full((beams), False)) # Check if parameter exists already and bandpass was applied successfully
                    if self.preflag_aoflagger_targetbeams == 'all': # Create a list of target beams
                        datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                        self.logger.info('# AOFlagging all target beams #')
                    else:
                        beams = self.preflag_aoflagger_targetbeams.split(",")
                        datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                        self.logger.info('# AOFlagging all selected target beam(s) #')
                    for vis in datasets:
                        if preflagaoflaggertargetbeamsflag[int(vis.split('/')[-3])] == False:
                            if self.aoflagger_bandpass and preflagaoflaggertargetbeamsbandpassapply[int(vis.split('/')[-3])]:
                                os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_targetstrat + ' -column CORRECTED_DATA ' + vis)
                                self.logger.debug('# Used AOFlagger to flag target beam ' + vis.split('/')[-3] + ' with preliminary bandpass applied #')
                                preflagaoflaggertargetbeamsflag[int(vis.split('/')[-3])] = True
                            elif self.aoflagger_bandpass == True and preflagaoflaggertargetbeamsbandpassapply[int(vis.split('/')[-3])] == False:
                                os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_targetstrat + ' ' + vis)
                                self.logger.warning('# Used AOFlagger to flag target beam ' + vis.split('/')[-3] + ' without preliminary bandpass applied. Better results are usually obtained with a preliminary bandpass applied. #')
                                preflagaoflaggertargetbeamsflag[int(vis.split('/')[-3])] = True
                            elif self.aoflagger_bandpass == False:
                                os.system('aoflagger -strategy ' + ao_strategies + self.preflag_aoflagger_targetstrat + ' ' + vis)
                                self.logger.warning('# Used AOFlagger to flag target beam ' + vis.split('/')[-3] + ' without preliminary bandpass applied. Better results are usually obtained with a preliminary bandpass applied. #')
                                preflagaoflaggertargetbeamsflag[int(vis.split('/')[-3])] = True
                        else:
                            self.logger.info('# Target beam ' + vis.split('/')[-3] + ' was already flagged with AOFlagger! #')
                else:
                    self.logger.error('# Target beam dataset(s) or strategy not defined properly. Not AOFlagging target beam dataset(s). #')

        # Save the derived parameters for the AOFlagger status to the parameter file

        subs_param.add_param(self, 'preflag_aoflagger_fluxcal_flag_status', preflagaoflaggerfluxcalflag)
        subs_param.add_param(self, 'preflag_aoflagger_polcal_flag_status', preflagaoflaggerpolcalflag)
        subs_param.add_param(self, 'preflag_aoflagger_targetbeams_flag_status', preflagaoflaggertargetbeamsflag)

    #################################################################
    ##### Functions to create the summaries of the PREFLAG step #####
    #################################################################

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

    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during PREFLAG. No detailed summary is available for PREFLAG
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
        df_AO = pd.DataFrame(np.ndarray.flatten(all_AO), index=dataset_indices, columns=['AOFlagger'])

        df = pd.concat([df_shadow, df_ghosts, df_edges, df_auto, df_ant, df_corr, df_baseline, df_channel, df_time, df_AO], axis=1)

        return df

    def show(self, showall=False):
        lib.show(self, 'PREFLAG', showall)

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in this step!
        """
        subs_setinit.setinitdirs(self)
        self.logger.warning('### Deleting all raw data products and their directories. You will need to start with the PREPARE step again! ###')
        subs_managefiles.director(self,'ch', self.basedir)
        deldirs = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir)
        for dir in deldirs:
            subs_managefiles.director(self,'rm', dir)
        self.logger.warning('### Deleting all parameter file entries for PREPARE and PREFLAG module ###')
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
        subs_param.del_param(self, 'preflag_aoflagger_bandpass_status')
        subs_param.del_param(self, 'preflag_aoflagger_fluxcal_bandpass_apply')
        subs_param.del_param(self, 'preflag_aoflagger_polcal_bandpass_apply')
        subs_param.del_param(self, 'preflag_aoflagger_targetbeams_bandpass_apply')
        subs_param.del_param(self, 'preflag_aoflagger_fluxcal_flag_status')
        subs_param.del_param(self, 'preflag_aoflagger_polcal_flag_status')
        subs_param.del_param(self, 'preflag_aoflagger_targetbeams_flag_status')
