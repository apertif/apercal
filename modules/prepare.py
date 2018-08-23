__author__ = "V. A. Moss, Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "moss@astron.nl, adebahr@astro.rub.de"

import ConfigParser
import glob
import logging
import pandas as pd
import os
import numpy as np

import subs.irods
import subs.setinit
import subs.managefiles


####################################################################################################

class prepare:
    '''
    Prepare class. Automatically copies the datasets into the directories and selects valid data (in case of multi-element observations)
    '''
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger('PREPARE')
        config = ConfigParser.ConfigParser()  # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('prepare.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        subs.setinit.setinitdirs(self)

    ####################################################
    ##### Function to execute the data preparation #####
    ####################################################

    def go(self):
        '''
        Executes the complete prepare step with the parameters indicated in the config-file in the following order:
        copyobs
        '''
        self.logger.info('########## Preparing data for calibration ##########')
        self.copyobs()
        self.logger.info('########## Data prepared for calibration ##########')

    ##############################################
    # Continuum mosaicing of the stacked images #
    ##############################################

    def copyobs(self):
        '''
        Prepares the directory structure and copies over the needed data from ALTA.
        Checks for data in the current working directories and copies only only missing data.
        '''
        subs.setinit.setinitdirs(self)
        beams = 37 # Number of beams

        ##########################################################################################################
        # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #
        ##########################################################################################################

        if subs.param.check_param(self, 'prepare_fluxcal_requested'):
            preparefluxcalrequested = subs.param.get_param(self, 'prepare_fluxcal_requested')
        else:
            preparefluxcalrequested = False  # Is the fluxcal data requested?

        if subs.param.check_param(self, 'prepare_polcal_requested'):
            preparepolcalrequested = subs.param.get_param(self, 'prepare_polcal_requested')
        else:
            preparepolcalrequested = False  # Is the polcal data requested?

        if subs.param.check_param(self, 'prepare_targetbeams_requested'):
            preparetargetbeamsrequested = subs.param.get_param(self, 'prepare_targetbeams_requested')
        else:
            preparetargetbeamsrequested = np.full((beams), False)  # Is the target data requested? One entry per beam

        if subs.param.check_param(self, 'prepare_fluxcal_diskstatus'):
            preparefluxcaldiskstatus = subs.param.get_param(self, 'prepare_fluxcal_diskstatus')
        else:
            preparefluxcaldiskstatus = False  # Is the fluxcal data already on disk?

        if subs.param.check_param(self, 'prepare_polcal_diskstatus'):
            preparepolcaldiskstatus = subs.param.get_param(self, 'prepare_polcal_diskstatus')
        else:
            preparepolcaldiskstatus = False  # Is the polcal data already on disk?

        if subs.param.check_param(self, 'prepare_targetbeams_diskstatus'):
            preparetargetbeamsdiskstatus = subs.param.get_param(self, 'prepare_targetbeams_diskstatus')
        else:
            preparetargetbeamsdiskstatus = np.full((beams), False)  # Is the target data already on disk? One entry per beam

        if subs.param.check_param(self, 'prepare_fluxcal_altastatus'):
            preparefluxcalaltastatus = subs.param.get_param(self, 'prepare_fluxcal_altastatus')
        else:
            preparefluxcalaltastatus = False  # Is the fluxcal data on ALTA?

        if subs.param.check_param(self, 'prepare_polcal_altastatus'):
            preparepolcalaltastatus = subs.param.get_param(self, 'prepare_polcal_altastatus')
        else:
            preparepolcalaltastatus = False  # Is the polcal data on ALTA?

        if subs.param.check_param(self, 'prepare_targetbeams_altastatus'):
            preparetargetbeamsaltastatus = subs.param.get_param(self, 'prepare_targetbeams_altastatus')
        else:
            preparetargetbeamsaltastatus = np.full((beams), False)  # Is the target data on disk? One entry per beam

        if subs.param.check_param(self, 'prepare_fluxcal_copystatus'):
            preparefluxcalcopystatus = subs.param.get_param(self, 'prepare_fluxcal_copystatus')
        else:
            preparefluxcalcopystatus = False  # Is the fluxcal data copied?

        if subs.param.check_param(self, 'prepare_polcal_copystatus'):
            preparepolcalcopystatus = subs.param.get_param(self, 'prepare_polcal_copystatus')
        else:
            preparepolcalcopystatus = False  # Is the polcal data on copied?

        if subs.param.check_param(self, 'prepare_targetbeams_copystatus'):
            preparetargetbeamscopystatus = subs.param.get_param(self, 'prepare_targetbeams_copystatus')
        else:
            preparetargetbeamscopystatus = np.full((beams), False)  # Is the target data copied? One entry per beam

        if subs.param.check_param(self, 'prepare_fluxcal_rejreason'):
            preparefluxcalrejreason = subs.param.get_param(self, 'prepare_fluxcal_rejreason')
        else:
            preparefluxcalrejreason = np.full((1), '', dtype='U50')  # Reason for flux calibrator dataset not being there

        if subs.param.check_param(self, 'prepare_polcal_rejreason'):
            preparepolcalrejreason = subs.param.get_param(self, 'prepare_polcal_rejreason')
        else:
            preparepolcalrejreason = np.full((1), '', dtype='U50')  # Reason for polarisation calibrator dataset not being there

        if subs.param.check_param(self, 'prepare_targetbeams_rejreason'):
            preparetargetbeamsrejreason = subs.param.get_param(self, 'prepare_targetbeams_rejreason')
        else:
            preparetargetbeamsrejreason = np.full((beams), '', dtype='U50')  # Reason for a beam dataset not being there

        ################################################
        # Start the preparation of the flux calibrator #
        ################################################

        if self.prepare_obsnum_fluxcal != '': # If the flux calibrator is requested
            preparefluxcalrejreason[0] = '' # Empty the comment string
            preparefluxcalrequested = True
            preparefluxcaldiskstatus = os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
            if preparefluxcaldiskstatus:
                self.logger.debug('# Flux calibrator dataset found on disk #')
            else:
                self.logger.debug('# Flux calibrator dataset not on disk #')
            # Check if the flux calibrator dataset is available on ALTA
            preparefluxcalaltastatus = subs.irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_fluxcal, '00')
            if preparefluxcalaltastatus:
                self.logger.debug('Flux calibrator dataset available on ALTA #')
            else:
                self.logger.warning('Flux calibrator dataset not available on ALTA #')
            # Copy the flux calibrator data from ALTA if needed
            if preparefluxcaldiskstatus and preparefluxcalaltastatus:
                preparefluxcalcopystatus = True
            elif preparefluxcaldiskstatus and preparefluxcalaltastatus == False:
                preparefluxcalcopystatus = True
                self.logger.warning('Flux calibrator data available on disk, but not in ALTA! #')
            elif preparefluxcaldiskstatus == False and preparefluxcalaltastatus:
                subs.managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                subs.irods.getdata_alta(self.prepare_date, self.prepare_obsnum_fluxcal, '00', self.rawdir + '/' + self.fluxcal)
                if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                    preparefluxcalcopystatus = True
                    self.logger.debug('# Flux calibrator dataset successfully copied from ALTA #')
                else:
                    preparefluxcalcopystatus = False
                    preparefluxcalrejreason[0] = 'Copy from ALTA not successful'
                    self.logger.error('# Flux calibrator dataset available on ALTA, but NOT successfully copied! #')
            elif preparefluxcaldiskstatus == False and preparefluxcalaltastatus == False:
                preparefluxcalcopystatus = False
                preparefluxcalrejreason[0] = 'Dataset not on ALTA or disk'
                self.logger.error('# Flux calibrator dataset not available on disk nor in ALTA! The next steps will not work! #')
        else: # In case the flux calibrator is not specified meaning the parameter is empty.
            preparefluxcalrequested = False
            preparefluxcaldiskstatus = False
            preparefluxcalaltastatus = False
            preparefluxcalcopystatus = False
            preparefluxcalrejreason[0] = 'Dataset not specified'
            self.logger.error('# No flux calibrator dataset specified. The next steps will not work! #')

        # Save the derived parameters for the fluxcal to the parameter file

        subs.param.add_param(self, 'prepare_fluxcal_requested', preparefluxcalrequested)
        subs.param.add_param(self, 'prepare_fluxcal_diskstatus', preparefluxcaldiskstatus)
        subs.param.add_param(self, 'prepare_fluxcal_altastatus', preparefluxcalaltastatus)
        subs.param.add_param(self, 'prepare_fluxcal_copystatus', preparefluxcalcopystatus)
        subs.param.add_param(self, 'prepare_fluxcal_rejreason', preparefluxcalrejreason)

        ########################################################
        # Start the preparation of the polarisation calibrator #
        ########################################################

        if self.prepare_obsnum_polcal != '': # If the polarised calibrator is requested
            preparepolcalrejreason[0] = '' # Empty the comment string
            preparepolcalrequested = True
            preparepolcaldiskstatus = os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
            if preparepolcaldiskstatus:
                self.logger.debug('# Polarisation calibrator dataset found on disk #')
            else:
                self.logger.debug('# Polarisation calibrator dataset not on disk #')
            # Check if the polarisation calibrator dataset is available on ALTA
            preparepolcalaltastatus = subs.irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_polcal, '00')
            if preparepolcalaltastatus:
                self.logger.debug('Polarisation calibrator dataset available on ALTA #')
            else:
                self.logger.warning('Polarisation calibrator dataset not available on ALTA #')
            # Copy the polarisation calibrator data from ALTA if needed
            if preparepolcaldiskstatus and preparepolcalaltastatus:
                preparepolcalcopystatus = True
            elif preparepolcaldiskstatus and preparepolcalaltastatus == False:
                preparepolcalcopystatus = True
                self.logger.warning('Polarisation calibrator data available on disk, but not in ALTA! #')
            elif preparepolcaldiskstatus == False and preparepolcalaltastatus:
                subs.managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                subs.irods.getdata_alta(self.prepare_date, self.prepare_obsnum_polcal, '00', self.rawdir + '/' + self.polcal)
                if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                    preparepolcalcopystatus = True
                    self.logger.debug('# Polarisation calibrator dataset successfully copied from ALTA #')
                else:
                    preparepolcalcopystatus = False
                    preparepolcalrejreason[0] = 'Copy from ALTA not successful'
                    self.logger.error('# Polarisation calibrator dataset available on ALTA, but NOT successfully copied! #')
            elif preparepolcaldiskstatus == False and preparepolcalaltastatus == False:
                preparepolcalcopystatus = False
                preparepolcalrejreason[0] = 'Dataset not on ALTA or disk'
                self.logger.warning('# Polarisation calibrator dataset not available on disk nor in ALTA! Polarisation calibration will not work! #')
        else: # In case the polarisation calibrator is not specified meaning the parameter is empty.
            preparepolcalrequested = False
            preparepolcaldiskstatus = False
            preparepolcalaltastatus = False
            preparepolcalcopystatus = False
            preparepolcalrejreason[0] = 'Dataset not specified'
            self.logger.warning('# No polarisation calibrator dataset specified. Polarisation calibration will not work! #')

        # Save the derived parameters for the polcal to the parameter file

        subs.param.add_param(self, 'prepare_polcal_requested', preparepolcalrequested)
        subs.param.add_param(self, 'prepare_polcal_diskstatus', preparepolcaldiskstatus)
        subs.param.add_param(self, 'prepare_polcal_altastatus', preparepolcalaltastatus)
        subs.param.add_param(self, 'prepare_polcal_copystatus', preparepolcalcopystatus)
        subs.param.add_param(self, 'prepare_polcal_rejreason', preparepolcalrejreason)

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
                    self.logger.debug('# Target dataset for beam ' + str(b).zfill(2) + ' found on disk #')
                else:
                    self.logger.debug('# Target dataset for beam ' + str(b).zfill(2) + ' NOT found on disk #')
                # Check which target datasets are available on ALTA
                preparetargetbeamsaltastatus[b] = subs.irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_target, str(b).zfill(2))
                if preparetargetbeamsaltastatus[b]:
                    self.logger.debug('# Target dataset for beam ' + str(b).zfill(2) + ' available on ALTA #')
                else:
                    self.logger.debug('# Target dataset for beam ' + str(b).zfill(2) + ' NOT available on ALTA #')
            # Set the copystatus of the beams and copy beams which are requested but not on disk
            for c in range(beams):
                if preparetargetbeamsdiskstatus[c] and preparetargetbeamsaltastatus[c]:
                    preparetargetbeamscopystatus[c] = True
                elif preparetargetbeamsdiskstatus[c] and preparetargetbeamsaltastatus[c] == False:
                    preparetargetbeamscopystatus[c] = True
                    self.logger.warning('Target dataset for beam ' + str(c).zfill(2) + ' available on disk, but not in ALTA! #')
                elif preparetargetbeamsdiskstatus[c] == False and preparetargetbeamsaltastatus[c] and str(c).zfill(2) in reqbeams: # if target dataset is requested, but not on disk
                    subs.managefiles.director(self, 'mk', self.basedir + str(c).zfill(2) + '/' + self.rawsubdir, verbose=False)
                    subs.irods.getdata_alta(self.prepare_date, self.prepare_obsnum_target, str(c).zfill(2),self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
                    # Check if copy was successful
                    if os.path.isdir(self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target):
                        preparetargetbeamscopystatus[c] = True
                    else:
                        preparetargetbeamscopystatus[c] = False
                        preparetargetbeamsrejreason[int(c)] = 'Copy from ALTA not successful'
                        self.logger.error('# Target beam dataset available on ALTA, but NOT successfully copied! #')
                elif preparetargetbeamsdiskstatus[c] == False and preparetargetbeamsaltastatus[c] == False and str(c).zfill(2) in reqbeams:
                    preparetargetbeamscopystatus[c] = False
                    preparetargetbeamsrejreason[int(c)] = 'Dataset not on ALTA or disk'
                    self.logger.error('# Target beam dataset not available on disk nor in ALTA! Requested beam cannot be processed! #')
        else: # If no target dataset is requested meaning the parameter is empty
            self.logger.warning('# No target datasets specified! #')
            for b in range(beams):
                preparetargetbeamsrequested[b] =  False
                preparetargetbeamsdiskstatus[b] = False
                preparetargetbeamsaltastatus[b] = False
                preparetargetbeamscopystatus[b] = False
                preparetargetbeamsrejreason[int(b)] = 'Dataset not specified'

        # Save the derived parameters for the target beams to the parameter file

        subs.param.add_param(self, 'prepare_targetbeams_requested', preparetargetbeamsrequested)
        subs.param.add_param(self, 'prepare_targetbeams_diskstatus', preparetargetbeamsdiskstatus)
        subs.param.add_param(self, 'prepare_targetbeams_altastatus', preparetargetbeamsaltastatus)
        subs.param.add_param(self, 'prepare_targetbeams_copystatus', preparetargetbeamscopystatus)
        subs.param.add_param(self, 'prepare_targetbeams_rejreason', preparetargetbeamsrejreason)

        #################################################################
        ##### Functions to create the summaries of the PREPARE step #####
        #################################################################

    def summary(self):
        '''
        Creates a general summary of the parameters in the parameter file generated during the prepare. No detailed summary is available for prepare
        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        '''

        beams = 37

        # Load the parameters from the parameter file

        FR = subs.param.get_param(self, 'prepare_fluxcal_requested')
        FD = subs.param.get_param(self, 'prepare_fluxcal_diskstatus')
        FA = subs.param.get_param(self, 'prepare_fluxcal_altastatus')
        FC = subs.param.get_param(self, 'prepare_fluxcal_copystatus')
        Frej = subs.param.get_param(self, 'prepare_fluxcal_rejreason')
        PR = subs.param.get_param(self, 'prepare_polcal_requested')
        PD = subs.param.get_param(self, 'prepare_polcal_diskstatus')
        PA = subs.param.get_param(self, 'prepare_polcal_altastatus')
        PC = subs.param.get_param(self, 'prepare_polcal_copystatus')
        Prej = subs.param.get_param(self, 'prepare_polcal_rejreason')
        TR = subs.param.get_param(self, 'prepare_targetbeams_requested')
        TD = subs.param.get_param(self, 'prepare_targetbeams_diskstatus')
        TA = subs.param.get_param(self, 'prepare_targetbeams_altastatus')
        TC = subs.param.get_param(self, 'prepare_targetbeams_copystatus')
        Trej = subs.param.get_param(self, 'prepare_targetbeams_rejreason')

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

    ##########################################################################
    ##### Individual functions to show the parameters and reset the step #####
    ##########################################################################

    def show(self, showall=False):
        '''
        show: Prints the current settings of the pipeline. Only shows keywords, which are in the default config file default.cfg
        showall: Set to true if you want to see all current settings instead of only the ones from the current step
        '''
        subs.setinit.setinitdirs(self)
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.apercaldir + '/modules/default.cfg'))
        for s in config.sections():
            if showall:
                print(s)
                o = config.options(s)
                for o in config.items(s):
                    try:
                        print('\t' + str(o[0]) + ' = ' + str(self.__dict__.__getitem__(o[0])))
                    except KeyError:
                        pass
            else:
                if s == 'PREPARE':
                    print(s)
                    o = config.options(s)
                    for o in config.items(s):
                        try:
                            print('\t' + str(o[0]) + ' = ' + str(self.__dict__.__getitem__(o[0])))
                        except KeyError:
                            pass
                else:
                    pass

    def reset(self):
        '''
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in this step!
        '''
        subs.setinit.setinitdirs(self)
        self.logger.warning('### Deleting all raw data products and their directories. ###')
        subs.managefiles.director(self,'ch', self.basedir)
        deldirs = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir)
        for dir in deldirs:
            subs.managefiles.director(self,'rm', dir)
        self.logger.warning('### Deleteing all parameter file entries for PREPARE module ###')
        subs.param.del_param(self, 'prepare_fluxcal_requested')
        subs.param.del_param(self, 'prepare_fluxcal_diskstatus')
        subs.param.del_param(self, 'prepare_fluxcal_altastatus')
        subs.param.del_param(self, 'prepare_fluxcal_copystatus')
        subs.param.del_param(self, 'prepare_fluxcal_rejreason')
        subs.param.del_param(self, 'prepare_polcal_requested')
        subs.param.del_param(self, 'prepare_polcal_diskstatus')
        subs.param.del_param(self, 'prepare_polcal_altastatus')
        subs.param.del_param(self, 'prepare_polcal_copystatus')
        subs.param.del_param(self, 'prepare_polcal_rejreason')
        subs.param.del_param(self, 'prepare_targetbeams_requested')
        subs.param.del_param(self, 'prepare_targetbeams_diskstatus')
        subs.param.del_param(self, 'prepare_targetbeams_altastatus')
        subs.param.del_param(self, 'prepare_targetbeams_copystatus')
        subs.param.del_param(self, 'prepare_targetbeams_rejreason')