import ConfigParser
import glob
import logging
import pandas as pd
import os
import numpy as np

from apercal.subs import irods as subs_irods
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.subs.getdata_alta import getdata_alta
from apercal.libs import lib


logger = logging.getLogger(__name__)


class prepare:
    """
    Prepare class. Automatically copies the datasets into the directories and selects valid data (in case of multi-element observations)
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

    prepare_date = None
    prepare_obsnum_fluxcal = None
    prepare_obsnum_polcal = None
    prepare_obsnum_target = None
    prepare_target_beams = None
    prepare_bypass_alta = None

    def __init__(self, file=None, **kwargs):
        self.default = lib.load_config(self, file)
        subs_setinit.setinitdirs(self)


    def go(self):
        """
        Executes the complete prepare step with the parameters indicated in the config-file in the following order:
        copyobs
        """
        logger.info('####### Preparing data for calibration ##########')
        self.copyobs()
        logger.info('####### Data prepared for calibration ##########')

    ##############################################
    # Continuum mosaicing of the stacked images #
    ##############################################

    def copyobs(self):
        """
        Prepares the directory structure and copies over the needed data from ALTA.
        Checks for data in the current working directories and copies only missing data.
        """
        subs_setinit.setinitdirs(self)
        beams = 37 # Number of beams

        ##########################################################################################################
        # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #
        ##########################################################################################################

        if not os.path.isdir(self.basedir):
            os.mkdir(self.basedir)

        preparefluxcalrequested = get_param_def(self, 'prepare_fluxcal_requested', False ) # Is the fluxcal data requested?

        preparepolcalrequested = get_param_def(self, 'prepare_polcal_requested', False ) # Is the polcal data requested?

        preparetargetbeamsrequested = get_param_def(self, 'prepare_targetbeams_requested', np.full((beams), False) ) # Is the target data requested? One entry per beam

        preparefluxcaldiskstatus = get_param_def(self, 'prepare_fluxcal_diskstatus', False ) # Is the fluxcal data already on disk?

        preparepolcaldiskstatus = get_param_def(self, 'prepare_polcal_diskstatus', False ) # Is the polcal data already on disk?

        preparetargetbeamsdiskstatus = get_param_def(self, 'prepare_targetbeams_diskstatus', np.full((beams), False) ) # Is the target data already on disk? One entry per beam

        preparefluxcalaltastatus = get_param_def(self, 'prepare_fluxcal_altastatus', False ) # Is the fluxcal data on ALTA?

        preparepolcalaltastatus = get_param_def(self, 'prepare_polcal_altastatus', False ) # Is the polcal data on ALTA?

        preparetargetbeamsaltastatus = get_param_def(self, 'prepare_targetbeams_altastatus', np.full((beams), False) ) # Is the target data on disk? One entry per beam

        preparefluxcalcopystatus = get_param_def(self, 'prepare_fluxcal_copystatus', False ) # Is the fluxcal data copied?

        preparepolcalcopystatus = get_param_def(self, 'prepare_polcal_copystatus', False ) # Is the polcal data on copied?

        preparetargetbeamscopystatus = get_param_def(self, 'prepare_targetbeams_copystatus', np.full((beams), False) ) # Is the target data copied? One entry per beam

        preparefluxcalrejreason = get_param_def(self, 'prepare_fluxcal_rejreason', np.full((1), '', dtype='U50') ) # Reason for flux calibrator dataset not being there

        preparepolcalrejreason = get_param_def(self, 'prepare_polcal_rejreason', np.full((1), '', dtype='U50') ) # Reason for polarisation calibrator dataset not being there

        preparetargetbeamsrejreason = get_param_def(self, 'prepare_targetbeams_rejreason', np.full((beams), '', dtype='U50') ) # Reason for a beam dataset not being there

        ################################################
        # Start the preparation of the flux calibrator #
        ################################################

        if self.prepare_obsnum_fluxcal != '': # If the flux calibrator is requested
            preparefluxcalrejreason[0] = '' # Empty the comment string
            preparefluxcalrequested = True
            fluxcal = self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal
            preparefluxcaldiskstatus = os.path.isdir(fluxcal)
            if preparefluxcaldiskstatus:
                logger.debug('# Flux calibrator dataset found on disk ({})#'.format(fluxcal))
            else:
                logger.debug('# Flux calibrator dataset not on disk ({})#'.format(fluxcal))

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:
                # Check if the flux calibrator dataset is available on ALTA
                preparefluxcalaltastatus = subs_irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_fluxcal, '00')
                if preparefluxcalaltastatus:
                    logger.debug('Flux calibrator dataset available on ALTA #')
                else:
                    logger.warning('Flux calibrator dataset not available on ALTA #')
                # Copy the flux calibrator data from ALTA if needed
                if preparefluxcaldiskstatus and preparefluxcalaltastatus:
                    preparefluxcalcopystatus = True
                elif preparefluxcaldiskstatus and preparefluxcalaltastatus == False:
                    preparefluxcalcopystatus = True
                    logger.warning('Flux calibrator data available on disk, but not in ALTA! #')
                elif preparefluxcaldiskstatus == False and preparefluxcalaltastatus:
                    subs_managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                    getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_fluxcal), 0, targetdir=self.rawdir + '/' + self.fluxcal)
                    if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                        preparefluxcalcopystatus = True
                        logger.debug('# Flux calibrator dataset successfully copied from ALTA #')
                    else:
                        preparefluxcalcopystatus = False
                        preparefluxcalrejreason[0] = 'Copy from ALTA not successful'
                        logger.error('# Flux calibrator dataset available on ALTA, but NOT successfully copied! #')
                elif preparefluxcaldiskstatus == False and preparefluxcalaltastatus == False:
                    preparefluxcalcopystatus = False
                    preparefluxcalrejreason[0] = 'Dataset not on ALTA or disk'
                    logger.error('# Flux calibrator dataset not available on disk nor in ALTA! The next steps will not work! #')
        else: # In case the flux calibrator is not specified meaning the parameter is empty.
            preparefluxcalrequested = False
            preparefluxcaldiskstatus = False
            preparefluxcalaltastatus = False
            preparefluxcalcopystatus = False
            preparefluxcalrejreason[0] = 'Dataset not specified'
            logger.error('# No flux calibrator dataset specified. The next steps will not work! #')

        # Save the derived parameters for the fluxcal to the parameter file

        subs_param.add_param(self, 'prepare_fluxcal_requested', preparefluxcalrequested)
        subs_param.add_param(self, 'prepare_fluxcal_diskstatus', preparefluxcaldiskstatus)
        subs_param.add_param(self, 'prepare_fluxcal_altastatus', preparefluxcalaltastatus)
        subs_param.add_param(self, 'prepare_fluxcal_copystatus', preparefluxcalcopystatus)
        subs_param.add_param(self, 'prepare_fluxcal_rejreason', preparefluxcalrejreason)

        ########################################################
        # Start the preparation of the polarisation calibrator #
        ########################################################

        if self.prepare_obsnum_polcal != '': # If the polarised calibrator is requested
            preparepolcalrejreason[0] = '' # Empty the comment string
            preparepolcalrequested = True
            preparepolcaldiskstatus = os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
            if preparepolcaldiskstatus:
                logger.debug('# Polarisation calibrator dataset found on disk #')
            else:
                logger.debug('# Polarisation calibrator dataset not on disk #')

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:

                # Check if the polarisation calibrator dataset is available on ALTA
                preparepolcalaltastatus = subs_irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_polcal, '00')
                if preparepolcalaltastatus:
                    logger.debug('Polarisation calibrator dataset available on ALTA #')
                else:
                    logger.warning('Polarisation calibrator dataset not available on ALTA #')
                # Copy the polarisation calibrator data from ALTA if needed
                if preparepolcaldiskstatus and preparepolcalaltastatus:
                    preparepolcalcopystatus = True
                elif preparepolcaldiskstatus and preparepolcalaltastatus == False:
                    preparepolcalcopystatus = True
                    logger.warning('Polarisation calibrator data available on disk, but not in ALTA! #')
                elif preparepolcaldiskstatus == False and preparepolcalaltastatus:
                    subs_managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                    getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_polcal), 0, targetdir=self.rawdir + '/' + self.polcal)
                    if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                        preparepolcalcopystatus = True
                        logger.debug('# Polarisation calibrator dataset successfully copied from ALTA #')
                    else:
                        preparepolcalcopystatus = False
                        preparepolcalrejreason[0] = 'Copy from ALTA not successful'
                        logger.error('# Polarisation calibrator dataset available on ALTA, but NOT successfully copied! #')
                elif preparepolcaldiskstatus == False and preparepolcalaltastatus == False:
                    preparepolcalcopystatus = False
                    preparepolcalrejreason[0] = 'Dataset not on ALTA or disk'
                    logger.warning('# Polarisation calibrator dataset not available on disk nor in ALTA! Polarisation calibration will not work! #')
        else: # In case the polarisation calibrator is not specified meaning the parameter is empty.
            preparepolcalrequested = False
            preparepolcaldiskstatus = False
            preparepolcalaltastatus = False
            preparepolcalcopystatus = False
            preparepolcalrejreason[0] = 'Dataset not specified'
            logger.warning('# No polarisation calibrator dataset specified. Polarisation calibration will not work! #')

        # Save the derived parameters for the polcal to the parameter file

        subs_param.add_param(self, 'prepare_polcal_requested', preparepolcalrequested)
        subs_param.add_param(self, 'prepare_polcal_diskstatus', preparepolcaldiskstatus)
        subs_param.add_param(self, 'prepare_polcal_altastatus', preparepolcalaltastatus)
        subs_param.add_param(self, 'prepare_polcal_copystatus', preparepolcalcopystatus)
        subs_param.add_param(self, 'prepare_polcal_rejreason', preparepolcalrejreason)

        ################################################
        # Start the preparation of the target datasets #
        ################################################

        if self.prepare_obsnum_target != '':
            if self.prepare_target_beams == 'all': # if all beams are requested
                reqbeams_nozero = range(beams) # create a list of numbers for the beams
                reqbeams = [str(b).zfill(2) for b in reqbeams_nozero] # Add the leading zeros
            else: # if only certain beams are requested
                reqbeams = self.prepare_target_beams.split(",")
            for beam in reqbeams:
                preparetargetbeamsrequested[int(beam)] = True
            for b in range(beams):
                # Check which target beams are already on disk
                preparetargetbeamsrejreason[int(b)] = '' # Empty the comment string
                preparetargetbeamsdiskstatus[b] = os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
                if preparetargetbeamsdiskstatus[b]:
                    logger.debug('# Target dataset for beam ' + str(b).zfill(2) + ' found on disk #')
                else:
                    logger.debug('# Target dataset for beam ' + str(b).zfill(2) + ' NOT found on disk #')

                if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                    logger.debug("Skipping fetching dataset from ALTA")
                else:
                    # Check which target datasets are available on ALTA
                    preparetargetbeamsaltastatus[b] = subs_irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_target, str(b).zfill(2))
                    if preparetargetbeamsaltastatus[b]:
                        logger.debug('# Target dataset for beam ' + str(b).zfill(2) + ' available on ALTA #')
                    else:
                        logger.debug('# Target dataset for beam ' + str(b).zfill(2) + ' NOT available on ALTA #')

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:
                # Set the copystatus of the beams and copy beams which are requested but not on disk
                for c in range(beams): # TODO: fix this for when not all beams are requested
                    if preparetargetbeamsdiskstatus[c] and preparetargetbeamsaltastatus[c]:
                        preparetargetbeamscopystatus[c] = True
                    elif preparetargetbeamsdiskstatus[c] and preparetargetbeamsaltastatus[c] == False:
                        preparetargetbeamscopystatus[c] = True
                        logger.warning('Target dataset for beam ' + str(c).zfill(2) + ' available on disk, but not in ALTA! #')
                    elif preparetargetbeamsdiskstatus[c] == False and preparetargetbeamsaltastatus[c] and str(c).zfill(2) in reqbeams: # if target dataset is requested, but not on disk
                        subs_managefiles.director(self, 'mk', self.basedir + str(c).zfill(2) + '/' + self.rawsubdir, verbose=False)
                        getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_target), int(str(c).zfill(2)),targetdir=self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
                        # Check if copy was successful
                        if os.path.isdir(self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target):
                            preparetargetbeamscopystatus[c] = True
                        else:
                            preparetargetbeamscopystatus[c] = False
                            preparetargetbeamsrejreason[int(c)] = 'Copy from ALTA not successful'
                            logger.error('# Target beam dataset available on ALTA, but NOT successfully copied! #')
                    elif preparetargetbeamsdiskstatus[c] == False and preparetargetbeamsaltastatus[c] == False and str(c).zfill(2) in reqbeams:
                        preparetargetbeamscopystatus[c] = False
                        preparetargetbeamsrejreason[int(c)] = 'Dataset not on ALTA or disk'
                        logger.error('# Target beam dataset not available on disk nor in ALTA! Requested beam cannot be processed! #')
        else: # If no target dataset is requested meaning the parameter is empty
            logger.warning('# No target datasets specified! #')
            for b in range(beams):
                preparetargetbeamsrequested[b] =  False
                preparetargetbeamsdiskstatus[b] = False
                preparetargetbeamsaltastatus[b] = False
                preparetargetbeamscopystatus[b] = False
                preparetargetbeamsrejreason[int(b)] = 'Dataset not specified'

        # Save the derived parameters for the target beams to the parameter file

        subs_param.add_param(self, 'prepare_targetbeams_requested', preparetargetbeamsrequested)
        subs_param.add_param(self, 'prepare_targetbeams_diskstatus', preparetargetbeamsdiskstatus)
        subs_param.add_param(self, 'prepare_targetbeams_altastatus', preparetargetbeamsaltastatus)
        subs_param.add_param(self, 'prepare_targetbeams_copystatus', preparetargetbeamscopystatus)
        subs_param.add_param(self, 'prepare_targetbeams_rejreason', preparetargetbeamsrejreason)

        #################################################################
        ##### Functions to create the summaries of the PREPARE step #####
        #################################################################

    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during PREPARE. No detailed summary is available for PREPARE
        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        """

        beams = 37

        # Load the parameters from the parameter file

        FR = subs_param.get_param(self, 'prepare_fluxcal_requested')
        FD = subs_param.get_param(self, 'prepare_fluxcal_diskstatus')
        FA = subs_param.get_param(self, 'prepare_fluxcal_altastatus')
        FC = subs_param.get_param(self, 'prepare_fluxcal_copystatus')
        Frej = subs_param.get_param(self, 'prepare_fluxcal_rejreason')
        PR = subs_param.get_param(self, 'prepare_polcal_requested')
        PD = subs_param.get_param(self, 'prepare_polcal_diskstatus')
        PA = subs_param.get_param(self, 'prepare_polcal_altastatus')
        PC = subs_param.get_param(self, 'prepare_polcal_copystatus')
        Prej = subs_param.get_param(self, 'prepare_polcal_rejreason')
        TR = subs_param.get_param(self, 'prepare_targetbeams_requested')
        TD = subs_param.get_param(self, 'prepare_targetbeams_diskstatus')
        TA = subs_param.get_param(self, 'prepare_targetbeams_altastatus')
        TC = subs_param.get_param(self, 'prepare_targetbeams_copystatus')
        Trej = subs_param.get_param(self, 'prepare_targetbeams_rejreason')

        # Create the data frame

        beam_range = range(beams)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = ['Flux calibrator (' + self.fluxcal[:-3] + ')', 'Polarised calibrator (' + self.polcal[:-3] + ')'] + dataset_beams

        all_r = np.full(39, False)
        all_r[0] = FR
        all_r[1] = PR
        all_r[2:] = TR

        all_d = np.full(39, False)
        all_d[0] = FD
        all_d[1] = PD
        all_d[2:] = TD

        all_a = np.full(39, False)
        all_a[0] = FA
        all_a[1] = PA
        all_a[2:] = TA

        all_c = np.full(39, False)
        all_c[0] = FC
        all_c[1] = PC
        all_c[2:] = TC

        all_rej = np.concatenate((Frej, Prej, Trej), axis=0)

        df_req = pd.DataFrame(np.ndarray.flatten(all_r), index=dataset_indices, columns=['Requested?'])
        df_disk = pd.DataFrame(np.ndarray.flatten(all_d), index=dataset_indices, columns=['On disk?'])
        df_alta = pd.DataFrame(np.ndarray.flatten(all_a), index=dataset_indices, columns=['On ALTA?'])
        df_copy = pd.DataFrame(np.ndarray.flatten(all_c), index=dataset_indices, columns=['Copied?'])
        df_rej = pd.DataFrame(all_rej, index=dataset_indices, columns=['Comment'])

        df = pd.concat([df_req, df_disk, df_alta, df_copy, df_rej], axis=1)

        return df

    def show(self, showall=False):
        lib.show(self, 'PREPARE', showall)

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in this step!
        """
        subs_setinit.setinitdirs(self)
        logger.warning(' Deleting all raw data products and their directories.')
        subs_managefiles.director(self,'ch', self.basedir)
        deldirs = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir)
        for dir in deldirs:
            subs_managefiles.director(self,'rm', dir)
        logger.warning(' Deleting all parameter file entries for PREPARE module')
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
