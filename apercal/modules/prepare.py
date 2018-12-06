import glob
import logging
import pandas as pd
import os
import numpy as np
import pymp
import time

from apercal.modules.base import BaseModule
from apercal.subs import irods as subs_irods
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.subs.getdata_alta import getdata_alta
from apercal.libs import lib

logger = logging.getLogger(__name__)


class prepare_parallel(BaseModule):
    """
    Prepare class. Automatically copies the datasets into the directories and selects valid data (in case of multi-element observations)
    """
    module_name = 'PREPARE'

    prepare_date = None
    prepare_obsnum_fluxcal = None
    prepare_obsnum_polcal = None
    prepare_obsnum_target = None
    prepare_target_beams = None
    prepare_bypass_alta = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)

    def go(self):
        """
        Executes the complete prepare step with the parameters indicated in the config-file in the following order:
        copyobs
        """
        logger.info('Preparing data for calibration')
        self.copyobs()
        logger.info('Data prepared for calibration')
        # should be equivalent to:
        # self.go_parallel(1,1)

    def go(self, preferred_beams):
        """
        Executes the complete prepare step with the parameters indicated in the config-file in the following order:
        copyobs
        """
        logger.info('Preparing data for calibration')
        self.copyobs_parallel(1, preferred_beams)
        logger.info('Data prepared for calibration')
        # should be equivalent to:
        # self.go_parallel(1,1)

    def go_parallel(self, first_level_threads=8, preferred_beams="None"):
        """
        Executes the complete prepare step with the parameters indicated in the config-file in the following order:
        copyobs
        """
        # default preferred_beams is "None" to allow hierarchy of preferred beams:
        # - (highest): passed as parameter to this function
        # - (medium): selection set in notebook
        # - (lowest): selection set in configuration file
        # "None" means no parameter passed => selection from notebook, or from configuration file
        logger.info('Preparing data for calibration')
        original_nested = pymp.config.nested
        start = time.time()
        self.copyobs_parallel(first_level_threads, preferred_beams)
        end = time.time()
        prepare_time = end - start
        pymp.config.nested = original_nested
        logger.info('Prepare with ' + str(first_level_threads) + ' threads: ' + str(prepare_time) + ' s')
        logger.info('Data prepared for calibration')

    ##############################################
    # Continuum mosaicing of the stacked images #
    ##############################################

    def copyobs(self):
        """
        Prepares the directory structure and copies over the needed data from ALTA.
        Checks for data in the current working directories and copies only missing data.
        """
        subs_setinit.setinitdirs(self)
        beams = 37  # Number of beams

        # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #

        if not os.path.isdir(self.basedir):
            os.mkdir(self.basedir)

        # Is the fluxcal data requested?
        preparefluxcalrequested = get_param_def(self, 'prepare_fluxcal_requested', False)

        # Is the polcal data requested?
        preparepolcalrequested = get_param_def(self, 'prepare_polcal_requested', False)

        # Is the target data requested? One entry per beam
        preparetargetbeamsrequested = get_param_def(self, 'prepare_targetbeams_requested', np.full(beams, False))

        # Is the fluxcal data already on disk?
        preparefluxcaldiskstatus = get_param_def(self, 'prepare_fluxcal_diskstatus', False)

        # Is the polcal data already on disk?
        preparepolcaldiskstatus = get_param_def(self, 'prepare_polcal_diskstatus', False)

        # Is the target data already on disk? One entry per beam
        preparetargetbeamsdiskstatus = get_param_def(self, 'prepare_targetbeams_diskstatus', np.full(beams, False))

        # Is the fluxcal data on ALTA?
        preparefluxcalaltastatus = get_param_def(self, 'prepare_fluxcal_altastatus', False)

        # Is the polcal data on ALTA?
        preparepolcalaltastatus = get_param_def(self, 'prepare_polcal_altastatus', False)

        # Is the target data on disk? One entry per beam
        preparetargetbeamsaltastatus = get_param_def(self, 'prepare_targetbeams_altastatus', np.full(beams, False))

        # Is the fluxcal data copied?
        preparefluxcalcopystatus = get_param_def(self, 'prepare_fluxcal_copystatus', False)

        # Is the polcal data on copied?
        preparepolcalcopystatus = get_param_def(self, 'prepare_polcal_copystatus', False)

        # Is the target data copied? One entry per beam
        preparetargetbeamscopystatus = get_param_def(self, 'prepare_targetbeams_copystatus', np.full(beams, False))

        # Reason for flux calibrator dataset not being there
        preparefluxcalrejreason = get_param_def(self, 'prepare_fluxcal_rejreason', np.full(1, '', dtype='U50'))

        # Reason for polarisation calibrator dataset not being there
        preparepolcalrejreason = get_param_def(self, 'prepare_polcal_rejreason', np.full(1, '', dtype='U50'))

        # Reason for a beam dataset not being there
        preparetargetbeamsrejreason = get_param_def(self, 'prepare_targetbeams_rejreason', np.full(beams, '', dtype='U50'))

        ################################################
        # Start the preparation of the flux calibrator #
        ################################################

        if self.prepare_obsnum_fluxcal != '':  # If the flux calibrator is requested
            preparefluxcalrejreason[0] = ''  # Empty the comment string
            preparefluxcalrequested = True
            fluxcal = self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal
            preparefluxcaldiskstatus = os.path.isdir(fluxcal)
            if preparefluxcaldiskstatus:
                logger.debug('Flux calibrator dataset found on disk ({})'.format(fluxcal))
            else:
                logger.debug('Flux calibrator dataset not on disk ({})'.format(fluxcal))

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:
                # Check if the flux calibrator dataset is available on ALTA
                preparefluxcalaltastatus = subs_irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_fluxcal,
                                                                     '00')
                if preparefluxcalaltastatus:
                    logger.debug('Flux calibrator dataset available on ALTA')
                else:
                    logger.warning('Flux calibrator dataset not available on ALTA')
                # Copy the flux calibrator data from ALTA if needed
                if preparefluxcaldiskstatus and preparefluxcalaltastatus:
                    preparefluxcalcopystatus = True
                elif preparefluxcaldiskstatus and not preparefluxcalaltastatus:
                    preparefluxcalcopystatus = True
                    logger.warning('Flux calibrator data available on disk, but not in ALTA!')
                elif not preparefluxcaldiskstatus and preparefluxcalaltastatus:
                    subs_managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                    getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_fluxcal), 0, targetdir=self.rawdir + '/' + self.fluxcal)
                    if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal):
                        preparefluxcalcopystatus = True
                        logger.debug('Flux calibrator dataset successfully copied from ALTA')
                    else:
                        preparefluxcalcopystatus = False
                        preparefluxcalrejreason[0] = 'Copy from ALTA not successful'
                        logger.error('Flux calibrator dataset available on ALTA, but NOT successfully copied!')
                elif not preparefluxcaldiskstatus and not preparefluxcalaltastatus:
                    preparefluxcalcopystatus = False
                    preparefluxcalrejreason[0] = 'Dataset not on ALTA or disk'
                    logger.error('Flux calibrator dataset not available on disk nor in ALTA! The next steps will not work!')
        else:  # In case the flux calibrator is not specified meaning the parameter is empty.
            preparefluxcalrequested = False
            preparefluxcaldiskstatus = False
            preparefluxcalaltastatus = False
            preparefluxcalcopystatus = False
            preparefluxcalrejreason[0] = 'Dataset not specified'
            logger.error('No flux calibrator dataset specified. The next steps will not work!')

        # Save the derived parameters for the fluxcal to the parameter file

        subs_param.add_param(self, 'prepare_fluxcal_requested', preparefluxcalrequested)
        subs_param.add_param(self, 'prepare_fluxcal_diskstatus', preparefluxcaldiskstatus)
        subs_param.add_param(self, 'prepare_fluxcal_altastatus', preparefluxcalaltastatus)
        subs_param.add_param(self, 'prepare_fluxcal_copystatus', preparefluxcalcopystatus)
        subs_param.add_param(self, 'prepare_fluxcal_rejreason', preparefluxcalrejreason)

        ########################################################
        # Start the preparation of the polarisation calibrator #
        ########################################################

        if self.prepare_obsnum_polcal != '':  # If the polarised calibrator is requested
            preparepolcalrejreason[0] = ''  # Empty the comment string
            preparepolcalrequested = True
            preparepolcaldiskstatus = os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
            if preparepolcaldiskstatus:
                logger.debug('Polarisation calibrator dataset found on disk')
            else:
                logger.debug('Polarisation calibrator dataset not on disk')

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:

                # Check if the polarisation calibrator dataset is available on ALTA
                preparepolcalaltastatus = subs_irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_polcal, '00')
                if preparepolcalaltastatus:
                    logger.debug('Polarisation calibrator dataset available on ALTA')
                else:
                    logger.warning('Polarisation calibrator dataset not available on ALTA')
                # Copy the polarisation calibrator data from ALTA if needed
                if preparepolcaldiskstatus and preparepolcalaltastatus:
                    preparepolcalcopystatus = True
                elif preparepolcaldiskstatus and not preparepolcalaltastatus:
                    preparepolcalcopystatus = True
                    logger.warning('Polarisation calibrator data available on disk, but not in ALTA!')
                elif not preparepolcaldiskstatus and preparepolcalaltastatus:
                    subs_managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                    getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_polcal), 0, targetdir=self.rawdir + '/' + self.polcal)
                    if os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal):
                        preparepolcalcopystatus = True
                        logger.debug('Polarisation calibrator dataset successfully copied from ALTA')
                    else:
                        preparepolcalcopystatus = False
                        preparepolcalrejreason[0] = 'Copy from ALTA not successful'
                        logger.error('Polarisation calibrator dataset available on ALTA, but NOT successfully copied!')
                elif not preparepolcaldiskstatus and not preparepolcalaltastatus:
                    preparepolcalcopystatus = False
                    preparepolcalrejreason[0] = 'Dataset not on ALTA or disk'
                    logger.warning('Polarisation calibrator dataset not available on disk nor in ALTA! Polarisation calibration will not work!')
        else:  # In case the polarisation calibrator is not specified meaning the parameter is empty.
            preparepolcalrequested = False
            preparepolcaldiskstatus = False
            preparepolcalaltastatus = False
            preparepolcalcopystatus = False
            preparepolcalrejreason[0] = 'Dataset not specified'
            logger.warning('No polarisation calibrator dataset specified. Polarisation calibration will not work!')

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
            if self.prepare_target_beams == 'all':  # if all beams are requested
                reqbeams_nozero = range(beams)  # create a list of numbers for the beams
                reqbeams = [str(b).zfill(2) for b in reqbeams_nozero]  # Add the leading zeros
            else:  # if only certain beams are requested
                reqbeams = self.prepare_target_beams.split(",")
            for beam in reqbeams:
                preparetargetbeamsrequested[int(beam)] = True
            for b in range(beams):
                # Check which target beams are already on disk
                preparetargetbeamsrejreason[int(b)] = ''  # Empty the comment string
                preparetargetbeamsdiskstatus[b] = os.path.isdir(
                    self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
                if preparetargetbeamsdiskstatus[b]:
                    logger.debug('Target dataset for beam ' + str(b).zfill(2) + ' found on disk')
                else:
                    logger.debug('Target dataset for beam ' + str(b).zfill(2) + ' NOT found on disk')

                if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                    logger.debug("Skipping fetching dataset from ALTA")
                else:
                    # Check which target datasets are available on ALTA
                    preparetargetbeamsaltastatus[b] = subs_irods.getstatus_alta(self.prepare_date, self.prepare_obsnum_target, str(b).zfill(2))
                    if preparetargetbeamsaltastatus[b]:
                        logger.debug('Target dataset for beam ' + str(b).zfill(2) + ' available on ALTA')
                    else:
                        logger.debug('Target dataset for beam ' + str(b).zfill(2) + ' NOT available on ALTA')

            if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                logger.debug("Skipping fetching dataset from ALTA")
            else:
                # Set the copystatus of the beams and copy beams which are requested but not on disk
                for c in range(beams):  # TODO: fix this for when not all beams are requested
                    if preparetargetbeamsdiskstatus[c] and preparetargetbeamsaltastatus[c]:
                        preparetargetbeamscopystatus[c] = True
                    elif preparetargetbeamsdiskstatus[c] and not preparetargetbeamsaltastatus[c]:
                        preparetargetbeamscopystatus[c] = True
                        logger.warning('Target dataset for beam ' + str(c).zfill(2) + ' available on disk, but not in ALTA!')
                    elif not preparetargetbeamsdiskstatus[c] and preparetargetbeamsaltastatus[c] and str(c).zfill(2) in reqbeams:  # if target dataset is requested, but not on disk
                        subs_managefiles.director(self, 'mk', self.basedir + str(c).zfill(2) + '/' + self.rawsubdir, verbose=False)
                        getdata_alta(int(self.prepare_date), int(self.prepare_obsnum_target), int(str(c).zfill(2)), targetdir=self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
                        # Check if copy was successful
                        if os.path.isdir(self.basedir + str(c).zfill(2) + '/' + self.rawsubdir + '/' + self.target):
                            preparetargetbeamscopystatus[c] = True
                        else:
                            preparetargetbeamscopystatus[c] = False
                            preparetargetbeamsrejreason[int(c)] = 'Copy from ALTA not successful'
                            logger.error('Target beam dataset available on ALTA, but NOT successfully copied!')
                    elif not preparetargetbeamsdiskstatus[c] and not preparetargetbeamsaltastatus[c] and str(c).zfill(2) in reqbeams:
                        preparetargetbeamscopystatus[c] = False
                        preparetargetbeamsrejreason[int(c)] = 'Dataset not on ALTA or disk'
                        logger.error('Target beam dataset not available on disk nor in ALTA! Requested beam cannot be processed!')
        else:  # If no target dataset is requested meaning the parameter is empty
            logger.warning('No target datasets specified!')
            for b in range(beams):
                preparetargetbeamsrequested[b] = False
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

    def copyobs_parallel(self, first_level_threads=8, preferred_beams="None"):
        """
        Prepares the directory structure and copies over the needed data from ALTA.
        Checks for data in the current working directories and copies only missing data.
        """
        # default preferred_beams is "None" to allow hierarchy of preferred beams:
        # - (highest): passed as parameter to this function
        # - (medium): selection set in notebook (with self.prepare_target_beams)
        # - (lowest): selection set in configuration file (id.)
        # "None" means no parameter passed => selection from notebook, or from configuration file
        subs_setinit.setinitdirs(self)
        beams = 37 # Number of beams
        if preferred_beams == "None": # no preferred_beams specified: fall back to predefined value
            preferred_beams = self.prepare_target_beams
        if preferred_beams == "all":
            preferred_beams = "0-" + str(beams - 1)
        #else:
        #    preferred_beams is considered to be in the correct format
        #    (no checks performed on this so far)

        # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #

        if not os.path.isdir(self.basedir):
            os.mkdir(self.basedir)

        # Is the fluxcal data requested?
        preparefluxcalrequested = get_param_def(self, 'prepare_fluxcal_requested', False)

        # Is the polcal data requested?
        preparepolcalrequested = get_param_def(self, 'prepare_polcal_requested', False)

        # Is the target data requested? One entry per beam
        preparetargetbeamsrequested = get_param_def(self, 'prepare_targetbeams_requested', np.full(beams, False))

        # Is the fluxcal data already on disk?
        preparefluxcaldiskstatus = get_param_def(self, 'prepare_fluxcal_diskstatus', False)

        # Is the polcal data already on disk?
        preparepolcaldiskstatus = get_param_def(self, 'prepare_polcal_diskstatus', False)

        # Is the target data already on disk? One entry per beam
        preparetargetbeamsdiskstatus = get_param_def(self, 'prepare_targetbeams_diskstatus', np.full(beams, False))

        # Is the fluxcal data on ALTA?
        preparefluxcalaltastatus = get_param_def(self, 'prepare_fluxcal_altastatus', False)

        # Is the polcal data on ALTA?
        preparepolcalaltastatus = get_param_def(self, 'prepare_polcal_altastatus', False)

        # Is the target data on disk? One entry per beam
        preparetargetbeamsaltastatus = get_param_def(self, 'prepare_targetbeams_altastatus', np.full(beams, False))

        # Is the fluxcal data copied?
        preparefluxcalcopystatus = get_param_def(self, 'prepare_fluxcal_copystatus', False)

        # Is the polcal data on copied?
        preparepolcalcopystatus = get_param_def(self, 'prepare_polcal_copystatus', False)

        # Is the target data copied? One entry per beam
        preparetargetbeamscopystatus = get_param_def(self, 'prepare_targetbeams_copystatus', np.full(beams, False))

        # Reason for flux calibrator dataset not being there
        preparefluxcalrejreason = get_param_def(self, 'prepare_fluxcal_rejreason', np.full(1, '', dtype='U50'))

        # Reason for polarisation calibrator dataset not being there
        preparepolcalrejreason = get_param_def(self, 'prepare_polcal_rejreason', np.full(1, '', dtype='U50'))

        # Reason for a beam dataset not being there
        preparetargetbeamsrejreason = get_param_def(self, 'prepare_targetbeams_rejreason', np.full(beams, '', dtype='U50'))

        ################################################
        # Start the preparation of the target datasets #
        ################################################

        # convert the preferred_beams to a full list of integers
        # the inner brackets section transforms the input string into an equivalent list of xranges;
        # the [y for x in [...] for y in x] flattens that last result (i.e. turns it into a 1D list);
        # the way to think about this is something like: "[list_element for nested_list in list_of_lists for list_element in nested_list]"
        # (where list_element is a list element of a nested_list, which is itself an 'element' of the list_of_lists)
        # this seems a bit counterintuitive, but that's the way Python does it; you'd have to add a newline PLUS an indent before
        # the second "for" to have the same functionality with simple for-loops (and then appending list_element), but
        # this list comprehension is much faster
        beams_list = [y for x in [(lambda l: xrange(l[0], l[-1] + 1))(map(int, r.split('-'))) for r in "".join(preferred_beams.split(' ')).split(',')] for y in x]

        beams_extended = 50
        # accomodates for all possible beam configurations, plus room for flux and polarisation
        # calibrators (and some unused ones in between)
        rejreasons = ['', 'Copy from ALTA not successful', 'Dataset not on ALTA or disk', 'Dataset not specified']
        rejreasonsdict = {}
        for index in range(len(rejreasons)):
            rejreasonsdict[rejreasons[index]] = index
        # this construct is because pymp.shared.array doesn't seem to be able to handle strings (at least from first glance)
        requested_beams = sorted(beams_list[:])
        skipped_beams = [x for x in range(beams_extended - 2) if x not in requested_beams]
        preparebeamsrequested = np.isin(np.arange(beams_extended), requested_beams)
        # (originally) intended TODO: use locks when writing to the following shared arrays,
        # but tests indicate this is actually not necessary (each thread is only accessing the
        # element corresponding to its own beam)
        preparebeamsrejreason_ind = pymp.shared.array((beams_extended,), dtype='uint8')
        preparebeamsdiskstatus = pymp.shared.array((beams_extended,), dtype='bool8')
        preparebeamsaltastatus = pymp.shared.array((beams_extended,), dtype='bool8')
        preparebeamscopystatus = pymp.shared.array((beams_extended,), dtype='bool8')
        for beam in range(beams_extended):
            preparebeamsrejreason_ind[beam] = rejreasonsdict['']
            preparebeamsdiskstatus[beam] = False
            preparebeamsaltastatus[beam] = False
            preparebeamscopystatus[beam] = False
        beamlocationsdir = np.full((beams_extended), '', dtype='U150')
        beamlocations = np.full((beams_extended), '', dtype='U150')
        beamdatasettypescap = np.full((beams_extended), '', dtype='U50')
        beamdatasettypeslow = np.full((beams_extended), '', dtype='U50')
        beamobsnum = np.full((beams_extended), '', dtype='U50')
        beamnum = np.full((beams_extended), '00', dtype='U2')
        beamnotpresent = np.full((beams_extended), '', dtype='U50')
        beamwarning = np.full((beams_extended), '', dtype='U50')
        if self.prepare_obsnum_target:
            for beam in range(beams_extended - 2):
                if preparebeamsrequested[beam]:
                    beamlocationsdir[beam] = self.basedir + str(beam).zfill(2) + '/' + self.rawsubdir
                    beamlocations[beam] = beamlocationsdir[beam] + '/' + self.target
                    beamdatasettypescap[beam] = "Target dataset for beam " + str(beam).zfill(2)
                    beamobsnum[beam] = self.prepare_obsnum_target
                    beamnum[beam] = str(beam).zfill(2)
                    beamnotpresent[beam] = "Requested beam cannot be processed! "
                beamdatasettypeslow[beam] = "target dataset for beam " + str(beam).zfill(2)
        else:
            for beam in range(beams_extended - 2):
                # without an actual (target) observation number, it's basically useless to request any beams
                if beam in requested_beams:
                    preparebeamsrequested[beam] = False
                    requested_beams.remove(beam)
                    skipped_beams.append(beam)
                beamdatasettypeslow[beam] = "target dataset for beam " + str(beam).zfill(2)
        skipped_beams.sort()
        if self.prepare_obsnum_polcal:
            preparebeamsrequested[-2] = True
            beamlocationsdir[-2] = self.basedir + '00' + '/' + self.rawsubdir
            beamlocations[-2] = beamlocationsdir[-2] + '/' + self.polcal
            beamdatasettypescap[-2] = "Polarisation calibrator dataset"
            beamobsnum[-2] = self.prepare_obsnum_polcal
            beamnum[-2] = '00' # but is already assigned by default
            beamnotpresent[-2] = "Polarisation calibration will not work! "
            requested_beams.insert(0, beams_extended - 2)
        else:
            skipped_beams.insert(0, beams_extended - 2)
        beamdatasettypeslow[-2] = "polarisation calibrator dataset"
        beamwarning[-2] = "Polarisation calibration will not work! "
        if self.prepare_obsnum_fluxcal:
            preparebeamsrequested[-1] = True
            beamlocationsdir[-1] = self.basedir + '00' + '/' + self.rawsubdir
            beamlocations[-1] = beamlocationsdir[-1] + '/' + self.fluxcal
            beamdatasettypescap[-1] = "Flux calibrator dataset"
            beamobsnum[-1] = self.prepare_obsnum_fluxcal
            beamnum[-1] = '00' # but is already assigned by default
            beamnotpresent[-1] = "The next steps will not work! "
            requested_beams.insert(0, beams_extended - 1)
        else:
            skipped_beams.insert(0, beams_extended - 1)
        beamdatasettypeslow[-1] = "flux calibrator dataset"
        beamwarning[-1] = "The next steps will not work! "
        # the 'proper' order to process the beams:
        # first fluxcal, then polcal, and then the rest in order
        # (skipping those not requested)
        # due to PyMP parallellism, only beams that are actually requested are looped over;
        # those not requested are 'handled' first (not much to be done for the latter)

        for index in range(len(skipped_beams)):
            beam = skipped_beams[index]
            # beam (or flux/polcal) not specified/requested:
            preparebeamsdiskstatus[beam] = False
            preparebeamsaltastatus[beam] = False
            preparebeamscopystatus[beam] = False
            preparebeamsrejreason_ind[beam] = rejreasonsdict['Dataset not specified']
            if beam == beams_extended - 1: #fluxcal
                logger.error('No {beamtype} specified! {futuresteps}'.format(beamtype=beamdatasettypeslow[beam], futuresteps=beamwarning[beam]))
            else: #polcal or regular beam
                logger.warning('No {beamtype} specified! {futuresteps}'.format(beamtype=beamdatasettypeslow[beam], futuresteps=beamwarning[beam]))

        if preparebeamsrequested[0] or preparebeamsrequested[-1] or preparebeamsrequested[-2]:
            #directory for beam "00" needs to be created, but to avoid having to use a lock inside the loop, we do it a bit early
            beamzerodir = self.basedir + '00' + '/' + self.rawsubdir
            if not os.path.isdir(beamzerodir):
                subs_managefiles.director(self, 'mk', beamzerodir, verbose=False)

        # loop over beams:
        with pymp.Parallel(first_level_threads) as p:
            for index in p.range(len(requested_beams)):
                beam = requested_beams[index]
                logger.warning('(PARALLEL) Starting beam {beamstring} (thread {thread} out of {threads})'.format(beamstring=str(beam).zfill(2), thread=str(p.thread_num + 1), threads=str(p.num_threads)))
                # Check which beams are already on disk
                preparebeamsrejreason_ind[beam] = rejreasonsdict[''] # Empty the comment string
                preparebeamsdiskstatus[beam] = os.path.isdir(beamlocations[beam])
                if preparebeamsdiskstatus[beam]:
                    logger.debug('(PARALLEL) {beamtype} found on disk ({location}) (thread {thread})'.format(beamtype=beamdatasettypescap[beam], location=beamlocations[beam], thread=str(p.thread_num + 1)))
                else:
                    logger.debug('(PARALLEL) {beamtype} NOT found on disk ({location}) (thread {thread})'.format(beamtype=beamdatasettypescap[beam], location=beamlocations[beam], thread=str(p.thread_num + 1)))
                if hasattr(self, 'prepare_bypass_alta') and self.prepare_bypass_alta:
                    logger.debug('(PARALLEL) Skipping fetching dataset from ALTA (thread {thread})'.format(thread=str(p.thread_num + 1)))
                else:
                    # Check if the dataset is available on ALTA
                    preparebeamsaltastatus[beam] = subs_irods.getstatus_alta(self.prepare_date, beamobsnum[beam], beamnum[beam])
                    if preparebeamsaltastatus[beam]:
                        logger.debug('(PARALLEL) {beamtype} available on ALTA (thread {thread})'.format(beamtype=beamdatasettypescap[beam], thread=str(p.thread_num + 1)))
                    else:
                        logger.warning('(PARALLEL) {beamtype} NOT available on ALTA (thread {thread})'.format(beamtype=beamdatasettypescap[beam], thread=str(p.thread_num + 1)))
                    # Copy the data from ALTA if needed
                    if preparebeamsdiskstatus[beam]:
                        preparebeamscopystatus[beam] = True
                        if not preparebeamsaltastatus[beam]:
                            logger.warning('(PARALLEL) {beamtype} available on disk, but NOT in ALTA! (thread {thread})'.format(beamtype=beamdatasettypescap[beam], thread=str(p.thread_num + 1)))
                    elif not preparebeamsdiskstatus[beam] and preparebeamsaltastatus[beam]:  # if dataset is requested, but not on disk
                        #if beamnum[beam] == '00':
                        #    # flux-/polcal & beam 00 share the same directory, so the directory may already exist
                        #    with p.lock:
                        #        if not os.path.isdir(beamlocationsdir[beam]):
                        #            subs_managefiles.director(self, 'mk', beamlocationsdir[beam], verbose=False)
                        #else:
                        if beamnum[beam] != '00' and not os.path.isdir(beamlocationsdir[beam]):
                            #directory for beam '00' already created if any of beam '00', flux- or polcal requested
                            subs_managefiles.director(self, 'mk', beamlocationsdir[beam], verbose=False)
                        # for the next line, the original code had targetdir=self.rawdir + '/' + self.fluxcal or self.polcal for flux/polcal,
                        # which is equivalent IFF beam == 0 for both special cases (which is the case using int(beamnum[beam]), which is 0 for both)
                        getdata_alta(int(self.prepare_date), int(beamobsnum[beam]), int(beamnum[beam]), targetdir=beamlocations[beam], post_to_slack=False)
                        #             post_to_slack=False, check_with_rsync=False)
                        # Check if copy was successful
                        if os.path.isdir(beamlocations[beam]):
                            preparebeamscopystatus[beam] = True
                            if beam >= (beams_extended - 2):
                                logger.debug('(PARALLEL) {beamtype} successfully copied from ALTA (thread {thread})'.format(beamtype=beamdatasettypescap[beam], thread=str(p.thread_num + 1)))
                            else:#just for now, to debug PyMP parallel
                                logger.warning('(PARALLEL) {beamtype} successfully copied from ALTA (thread {thread})'.format(beamtype=beamdatasettypescap[beam], thread=str(p.thread_num + 1)))
                        else:
                            preparebeamscopystatus[beam] = False
                            preparebeamsrejreason_ind[beam] = rejreasonsdict['Copy from ALTA not successful']
                            logger.error('(PARALLEL) {beamtype} available on ALTA, but NOT successfully copied! (thread {thread})'.format(beamtype=beamdatasettypescap[beam], thread=str(p.thread_num + 1)))
                    elif not preparebeamsdiskstatus[beam] and not preparebeamsaltastatus[beam]:
                        preparebeamscopystatus[beam] = False
                        preparebeamsrejreason_ind[beam] = rejreasonsdict['Dataset not on ALTA or disk']
                        if beam == beams_extended - 2: #polcal
                            logger.warning('(PARALLEL) {beamtype} not available on disk nor in ALTA! {futuresteps} (thread {thread})'.format(beamtype=beamdatasettypescap[beam], futuresteps=beamnotpresent[beam], thread=str(p.thread_num + 1)))
                        else: #fluxcal or regular target beam
                            logger.error('(PARALLEL) {beamtype} not available on disk nor in ALTA! {futuresteps} (thread {thread})'.format(beamtype=beamdatasettypescap[beam], futuresteps=beamnotpresent[beam], thread=str(p.thread_num + 1)))
                logger.warning('(PARALLEL) Ending beam {beamstring} (thread {thread} out of {threads})'.format(beamstring=str(beam).zfill(2), thread=str(p.thread_num + 1), threads=str(p.num_threads)))

        preparebeamsrejreason = np.array([rejreasons[index] for index in preparebeamsrejreason_ind])

        # Save the derived parameters for the fluxcal to the parameter file
        preparefluxcalrequested = preparebeamsrequested[-1]
        preparefluxcaldiskstatus = preparebeamsdiskstatus[-1]
        preparefluxcalaltastatus = preparebeamsaltastatus[-1]
        preparefluxcalcopystatus = preparebeamscopystatus[-1]
        preparefluxcalrejreason = preparebeamsrejreason[-1]

        subs_param.add_param(self, 'prepare_fluxcal_requested', preparefluxcalrequested)
        subs_param.add_param(self, 'prepare_fluxcal_diskstatus', preparefluxcaldiskstatus)
        subs_param.add_param(self, 'prepare_fluxcal_altastatus', preparefluxcalaltastatus)
        subs_param.add_param(self, 'prepare_fluxcal_copystatus', preparefluxcalcopystatus)
        subs_param.add_param(self, 'prepare_fluxcal_rejreason', preparefluxcalrejreason)

        # Save the derived parameters for the polcal to the parameter file

        preparepolcalrequested = preparebeamsrequested[-2]
        preparepolcaldiskstatus = preparebeamsdiskstatus[-2]
        preparepolcalaltastatus = preparebeamsaltastatus[-2]
        preparepolcalcopystatus = preparebeamscopystatus[-2]
        preparepolcalrejreason[:] = preparebeamsrejreason[-2]
        subs_param.add_param(self, 'prepare_polcal_requested', preparepolcalrequested)
        subs_param.add_param(self, 'prepare_polcal_diskstatus', preparepolcaldiskstatus)
        subs_param.add_param(self, 'prepare_polcal_altastatus', preparepolcalaltastatus)
        subs_param.add_param(self, 'prepare_polcal_copystatus', preparepolcalcopystatus)
        subs_param.add_param(self, 'prepare_polcal_rejreason', preparepolcalrejreason)

        # Save the derived parameters for the target beams to the parameter file

        preparetargetbeamsrequested[:] = preparebeamsrequested[:beams]
        preparetargetbeamsdiskstatus[:] = preparebeamsdiskstatus[:beams]
        preparetargetbeamsaltastatus[:] = preparebeamsaltastatus[:beams]
        preparetargetbeamscopystatus[:] = preparebeamscopystatus[:beams]
        preparetargetbeamsrejreason[:] = preparebeamsrejreason[:beams]
        subs_param.add_param(self, 'prepare_targetbeams_requested', preparetargetbeamsrequested)
        subs_param.add_param(self, 'prepare_targetbeams_diskstatus', preparetargetbeamsdiskstatus)
        subs_param.add_param(self, 'prepare_targetbeams_altastatus', preparetargetbeamsaltastatus)
        subs_param.add_param(self, 'prepare_targetbeams_copystatus', preparetargetbeamscopystatus)
        subs_param.add_param(self, 'prepare_targetbeams_rejreason', preparetargetbeamsrejreason)

    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during PREPARE. No detailed summary
        is available for PREPARE

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in notebook
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

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in this step!
        """
        subs_setinit.setinitdirs(self)
        logger.warning('Deleting all raw data products and their directories.')
        subs_managefiles.director(self, 'ch', self.basedir)
        deldirs = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir)
        for dir_ in deldirs:
            subs_managefiles.director(self, 'rm', dir_)
        logger.warning('Deleting all parameter file entries for PREPARE module')
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
