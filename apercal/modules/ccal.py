import logging
import glob
import os
import numpy as np
import pandas as pd

import casacore.tables as pt

from ConfigParser import SafeConfigParser, ConfigParser

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs import msutils as subs_msutils
from apercal.subs import calmodels as subs_calmodels
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.subs import ccal_utils
from apercal.exceptions import ApercalException

from apercal.libs import lib

logger = logging.getLogger(__name__)

gencal_cmd = 'gencal(vis="{vis}", caltable="{caltable}", caltype="{caltype}", infile="{infile}")'


class ccal(BaseModule):
    """
    Crosscal class to handle applying the calibrator gains and prepare the dataset for self-calibration.
    """

    module_name = 'CROSSCAL'

    crosscaldir = None
    crosscal_initial_phase = None
    crosscal_global_delay = None
    crosscal_bandpass = None
    crosscal_gains = None
    crosscal_crosshand_delay = None
    crosscal_leakage = None
    crosscal_polarisation_angle = None
    crosscal_transfer_to_cal = None
    crosscal_transfer_to_target = None
    crosscal_refant = None
    crosscal_refant_exclude = ["RTC", "RTD"]
    crosscal_ant_list = None
    crosscal_check_bandpass = None
    crosscal_check_autocorrelation = None
    crosscal_flag_limit = 4
    crosscal_try_limit = None
    crosscal_fluxcal_try_limit = None
    crosscal_autocorrelation_amp_limit = None
    crosscal_autocorrelation_data_fraction_limit = None

    # not for config
    config_file_name = None
    crosscal_fluxcal_try_counter = 0
    crosscal_try_counter = 0
    crosscal_try_restart = False
    crosscal_fluxcal_try_restart = False
    crosscal_flag_list = None
    
    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)
        self.config_file_name = file_

        # setting some presets if not specified
        if self.crosscal_check_autocorrelation is None:
            self.crosscal_check_autocorrelation = True
            logger.info("Setting for checking autocorrelation was not specified. Setting it to default {}".format(self.crosscal_check_autocorrelation))

        if self.crosscal_try_limit is None:
            self.crosscal_try_limit = 3
            logger.info("Number of overall crosscal restarts not specified. Setting to default: {}".format(self.crosscal_try_counter))
        
        if self.crosscal_fluxcal_try_limit is None:
            self.crosscal_fluxcal_try_limit = 3
            logger.info("Number of fluxcal calibration restarts not specified. Setting to default: {}".format(
                self.crosscal_fluxcal_try_counter))

        if self.crosscal_flag_limit is None:
            self.crosscal_flag_limit = 4
            logger.info("Maximum number of antennas with at least one polarisation flagged not specified. Setting to default: {}".format(
                self.crosscal_flag_counter))
           
        if self.crosscal_autocorrelation_amp_limit is None:
            self.crosscal_autocorrelation_amp_limit = 1500.
            logger.info("Maximum value of autocorrelation ampliude not specified. Setting to default: {}".format(
                self.crosscal_autocorrelation_amp_limit))
        
        if self.crosscal_autocorrelation_data_fraction_limit is None:
            self.crosscal_autocorrelation_data_fraction_limit = 0.9
            logger.info("Limit of the fraction of data with autocorrelation amplitude above maximum value not specified. Setting to default: {}".format(
                self.crosscal_autocorrelation_data_fraction_limit))
        

    def go(self):
        """
        Executes the full cross calibration process in the following order.
        setflux
        initial_phase
        global_delay
        bandpass
        gains
        crosshand_delay
        leakage
        polarisation_angle
        transfer_to_cal
        tranfer_to_target
        """
        logger.info("Starting CROSS CALIBRATION ")

        self.check_ref_ant()
        
        self.calibrate_calibrators()
            
        self.transfer_to_target()
        logger.info("CROSS CALIBRATION done ")

    def calibrate_calibrators(self):
        """
        Function to manage the adaptive calibration of the calibrators.
        """

        cbeam = 'ccal_B' + str(self.beam).zfill(2)
        ccal_calibration_restart = get_param_def(self, cbeam + '_calibration_restart', False)
        ccal_calibration_try_counter = get_param_def(self, cbeam + '_calibration_try_counter', 0)

        # to break the crosscal loop before the limit
        crosscal_finished = False

        # loop for restarting all of cross-calibration
        while self.crosscal_try_counter < self.crosscal_try_limit and not crosscal_finished:

            logger.info("Beam {0}: Running cross-calibration attempt {1} (out of {2})".format(
                self.beam, self.crosscal_try_counter+1, self.crosscal_try_limit))

            self.crosscal_try_restart = False

            # reset counter for flux calibration
            self.crosscal_fluxcal_try_counter = 0

            # set the model
            self.setflux()

            # fluxcal
            self.calibrate_fluxcal()

            # polcal
            self.calibrate_polcal()

            # apply solutions
            #self.apply_solutions()
            self.transfer_to_cal()

            if self.crosscal_check_autocorrelation:
                self.check_autocorrelation()
            else:
                logger.warning("Beam {0}: Running cross-calibration attempt {1} (out of {2}) finished without autocorrelation check.".format(
                    self.beam, self.crosscal_try_counter+1, self.crosscal_try_limit))
                break

            if self.crosscal_try_restart:
                logger.warning("Beam {0}: Running cross-calibration attempt {1} (out of {2}) failed autocorrelation check. Going to reset, flag and restart".format(
                    self.beam, self.crosscal_try_counter+1, self.crosscal_try_limit))
                # checking the number of antennas flagged
                ccal_flag_list = self.crosscal_flag_list
                if ccal_flag_list is not None:
                    logger.info("Beam {0}: Autocorrelation check found the following flags: {1}".format(self.beam, ccal_flag_list))
                    # get a list flagged polarisation
                    pol_flag_list = np.array([flag[1] for flag in ccal_flag_list])
                    # get the flags that have both polarisation flagged
                    n_full_poll_flags_xx = len(np.where(pol_flag_list == "XX")[0])
                    n_full_poll_flags_yy = len(
                        np.where(pol_flag_list == "YY")[0])
                    if n_full_poll_flags_xx > self.crosscal_flag_limit or n_full_poll_flags_yy > self.crosscal_flag_limit:
                        error = "Beam {0}: Number of antennas with XX and YY flagged ({1}) exceeds defined limit {2}".format(self.beam, n_full_poll_flags, self.crosscal_flag_limit)
                        logger.error(error)
                        raise RuntimeError(error)


                # reset first (only fluxcal and polcal need to have theire calibration reset)
                self.reset(do_clearcal=False, do_clearcal_fluxcal=True, do_clearcal_polcal=True)

                # flagging data
                # need to do it after restart
                self.flag_data()

                # set the counter up
                self.crosscal_try_counter += 1
                # set the status parameter
                ccal_calibration_restart = self.crosscal_try_restart
                continue
            else:
                logger.info("Beam {0}: Running cross-calibration attempt {1} (out of {2}) passed autocorrelation check. Continuing".format(
                    self.beam, self.crosscal_try_counter+1, self.crosscal_try_limit))
                crosscal_finished = True
                break
        
        subs_param.add_param(
            self, cbeam + '_calibration_restart', ccal_calibration_restart)
        subs_param.add_param(
            self, cbeam + '_calibration_try_counter', ccal_calibration_try_counter)
        
        if crosscal_finished:
            logger.info(
                "Beam {}: Cross-calibration was successful".format(self.beam))
        else:
            error = "Beam {}: Cross-calibration failed. Abort".format(
                self.beam)
            logger.error(error)
            raise RuntimeError(error)


    def calibrate_fluxcal(self):
        """
        Running the calibration steps that are specific for the flux calibrator

        In case one of the calibration steps fails, the function restarts
        and tries to calibrate the flux calibrator with a different reference
        antenna
        """

        # in case crosscal finishes and all is well
        crosscal_fluxcal_finished = False

        # Status parameters to save if restarted and which try it finished
        cbeam = 'ccal_B' + str(self.beam).zfill(2)
        # Status of model of the flux and polarisation calibrator
        ccal_fluxcal_calibration_restart = get_param_def(self, cbeam + '_fluxcal_calibration_restart', False)
        ccal_fluxcal_calibration_try_counter = get_param_def(self, cbeam + '_fluxcal_calibration_try_counter', 0)

        # go through the number of tries or break loop if finished
        while self.crosscal_fluxcal_try_counter < self.crosscal_fluxcal_try_limit and not crosscal_fluxcal_finished:
            logger.info("Beam {0}: Attempt {1} (out of {2}) to run calibration taks of flux calibrator".format(self.beam, self.crosscal_fluxcal_try_counter+1, self.crosscal_fluxcal_try_limit))

            self.crosscal_fluxcal_try_restart = False

            # running initial phase calibration
            self.initial_phase()
            # if it fails, restart the loop after changing the reference antenna
            if self.crosscal_fluxcal_try_restart:
                logger.warning("Beam {0}: Attempt {1} (out of {2}) failed at initial phase calibration. Trying to restart with different reference antenna".format(self.beam, self.crosscal_fluxcal_try_counter+1, self.crosscal_fluxcal_try_limit))
                # reset first
                self.reset(do_clearcal=False)
                # change refant
                self.check_ref_ant(check_flags=False, change_ref_ant=True)
                # set the counter up
                self.crosscal_fluxcal_try_counter += 1
                # set the status parameter
                ccal_fluxcal_calibration_restart = self.crosscal_fluxcal_try_restart
                continue

            # running global delay calibration
            self.global_delay()
            # if it fails, restart the loop after changing the reference antenna
            if self.crosscal_fluxcal_try_restart:
                logger.warning(
                    "Beam {0}: Attempt {1} (out of {2}) failed at global delay calibration. Trying to restart with different reference antenna".format(self.beam, self.crosscal_fluxcal_try_counter+1, self.crosscal_fluxcal_try_limit))
                # reset first
                self.reset(do_clearcal=False)
                # change refant
                self.check_ref_ant(check_flags=False, change_ref_ant=True)
                # set the counter up
                self.crosscal_fluxcal_try_counter += 1
                # set the status parameter
                ccal_fluxcal_calibration_restart = self.crosscal_fluxcal_try_restart
                continue

            # running bandpass calibraiton
            self.bandpass()
            if self.crosscal_check_bandpass:
                logger.info("Beam {}: Checking bandpass solutions".format(self.beam))
                self.check_bandpass()
            else:
                logger.info("Beam {}: Did not check bandpass solutions".format(self.beam))
            # if it fails, restart the loop after changing the reference antenna
            if self.crosscal_fluxcal_try_restart:
                logger.warning(
                    "Beam {0}: Attempt {1} (out of {2}) failed at bandpass calibration. Trying to restart with different reference antenna".format(self.beam, self.crosscal_fluxcal_try_counter+1, self.crosscal_fluxcal_try_limit))
                # reset first
                self.reset(do_clearcal=False)
                # change refant
                self.check_ref_ant(check_flags=False, change_ref_ant=True)
                # set the counter up
                self.crosscal_fluxcal_try_counter += 1
                # set the status parameter
                ccal_fluxcal_calibration_restart = self.crosscal_fluxcal_try_restart
                continue

            self.gains()
            # if it fails, restart the loop after changing the reference antenna
            if self.crosscal_fluxcal_try_restart:
                logger.warning(
                    "Beam {0}: Attempt {1} (out of {2}) failed at gain calibration. Trying to restart with different reference antenna".format(self.beam, self.crosscal_fluxcal_try_counter+1, self.crosscal_fluxcal_try_limit))
                # reset first
                self.reset(do_clearcal=False)
                # change refant
                self.check_ref_ant(check_flags=False, change_ref_ant=True)
                # set the counter up
                self.crosscal_fluxcal_try_counter += 1
                # set the status parameter
                ccal_fluxcal_calibration_restart = self.crosscal_fluxcal_try_restart
                continue

            # if this point is reached, crosscalibration should have worked
            crosscal_fluxcal_finished = True
            # leave the loop
            break
        
        # save parameters
        subs_param.add_param(
            self, cbeam + '_fluxcal_calibration_restart', ccal_fluxcal_calibration_restart)
        subs_param.add_param(
            self, cbeam + '_fluxcal_calibration_try_counter', ccal_fluxcal_calibration_try_counter)

        if crosscal_fluxcal_finished:
            logger.info("Beam {}: Calibration of flux calibrator successful. Continue with pol calibrator".format(self.beam))
        else:
            error = "Beam {}: Cross-calibration of flux calibrator was not successful. Abort".format(self.beam)
            logger.error(error)
            raise RuntimeError(error)
    
    def calibrate_polcal(self):
        """
        Running the calibration steps that are specific for the pol calibrator
        """

        self.crosshand_delay()
        self.leakage()
        self.polarisation_angle()

    def apply_solutions(self):
        """
        Apply the solutions to the calibrators and the target
        """

        self.transfer_to_cal()
        self.transfer_to_target()

    def get_antenna_list(self):

        # get a list of antennas from the fluxcal MS file
        query = "SELECT NAME FROM {}::ANTENNA".format(self.get_fluxcal_path())
        query_result = pt.taql(query)
        self.crosscal_ant_list = np.array(query_result.getcol("NAME"))

    def check_ref_ant(self, check_flags=True, change_ref_ant = False):
        """
        Check that the default reference antenna.

        This function tests whether the default reference antenna is 
        available or not. If not, it uses the next antenna. It changes
        the config file settings for crosscal and selfcal accordingly.
        RTC and RTD have been excluded because of their performance. 
        At the moment, the function only tests whether the entire reference
        antenna is flagged.

        Theses tests are based on the flux calibrator
        """

        # get the reference antenna
        self.get_antenna_list()
        crosscal_refant = self.crosscal_refant
        logger.info(
            "Beam {0}: Checking reference antenna {1} set in config file".format(self.beam, crosscal_refant))

        if self.polcal != '':
            # get a list of antennas from the polcal MS file
            query = "SELECT NAME FROM {}::ANTENNA".format(self.get_polcal_path())
            query_result = pt.taql(query)
            polcal_ant_list = np.array(query_result.getcol("NAME"))
        else:
            polcal_ant_list = None

        # check that the reference antenna is in the list of antennas
        refant_in_fluxcal = crosscal_refant in self.crosscal_ant_list

        if refant_in_fluxcal:
            logger.info("Beam {0}: Reference antenna {1} exists in flux calibrator".format(self.beam, crosscal_refant))
        else:
            # since the reference antenna does not exists, choose the first available one in the list
            # this should not be RTC and RTD but just in case test it
            for ant in self.crosscal_ant_list:
                if ant not in self.crosscal_refant_exclude:
                    logger.info("Beam {0}: Could not find reference antenna {1} in flux calibrator. Chose {2} instead".format(self.beam, crosscal_refant, ant))
                    crosscal_refant = ant
                    refant_in_fluxcal = True
                    break

        # get the index of the reference antenna
        refant_fluxcal_index = np.where(self.crosscal_ant_list == crosscal_refant)[0][0]

        if check_flags:
            # check if the entire referance antenna is flagged
            # dropping "==0" would give the number of non-flagged data points
            query = "SELECT GNFALSE(FLAG)==0 as all_flagged FROM {0} WHERE ANTENNA1=={1}".format(self.get_fluxcal_path(), refant_fluxcal_index)
            query_result = pt.taql(query)

            # if reference antenna is completely flagged, another one needs to be chosen
            if query_result[0]['all_flagged']:
                logger.info("Beam {0}: All visibilities of reference antenna {1} are flagged. Choosing another one".format(self.beam, crosscal_refant))
                # go through the list of antennas
                ant_name = ""
                for ant_index in range(refant_fluxcal_index + 1, len(self.crosscal_ant_list)):
                    # check if it completely flagged
                    query_ref_search = "SELECT GNFALSE(FLAG)==0 as all_flagged FROM {0} WHERE ANTENNA1=={1}".format(
                        self.get_fluxcal_path(), ant_index)
                    query_ref_search_result = pt.taql(query_ref_search)
                    # if this one is not flagged
                    if not query_ref_search_result[0]['all_flagged']:
                        # get the name
                        ant_name = self.crosscal_ant_list[ant_index]
                        # check that it is not in the exclude list
                        if ant_name not in self.crosscal_refant_exclude:
                            logger.info(
                                "Beam {0}: Choosing {1} as the reference antenna".format(self.beam, ant_name))
                            crosscal_refant = ant_name
                            refant_fluxcal_index = ant_index
                            break
                # not sure if this check is necessary
                if ant_name == "":
                    error = "Beam {0}: Could not find a new reference antenna. Abort crosscal".format(self.beam)
                    logger.error(error)
                    raise RuntimeError(error)
            # reference antenna is not completely flagged
            else:
                logger.info("Reference antenna {0} is not completely flagged. Keeping it.".format(crosscal_refant))
        
        # another option is to just change the reference antenna
        if change_ref_ant:
            # only if it hasn't already been changed
            if crosscal_refant == self.crosscal_refant:
                # set the index of the reference antenna one up
                refant_fluxcal_index += 1
                # get the corresponding reference antenna
                crosscal_refant = self.crosscal_ant_list[refant_fluxcal_index]
                if crosscal_refant not in self.crosscal_refant_exclude:
                     logger.info("Beam {0}: Changing reference antenna to {1}".format(self.beam, crosscal_refant))
                else:
                    # maybe a restart would be better, in case there is another antenna
                    error = "Beam {0}: New reference antenna {1} should be excluded. Abort".format(self.beam, crosscal_refant)
                    logger.error(error)
                    raise RuntimeError(error)         

        if crosscal_refant != self.crosscal_refant:
            if self.config_file_name is not None:
                logger.info("Beam {0}: Chosen reference antenna {1} is different from config file setting. Adjusting settings for crosscal and selfcal".format(self.beam, crosscal_refant))
                # set config parser
                config = ConfigParser()
                # read the config file settings
                with open(self.config_file_name, "r") as fp:
                    config.readfp(fp)

                # change the setting in crosscal
                # not strictly necessary here, but good to make the config file consistent
                config.set("CROSSCAL", "crosscal_refant", "'{}'".format(crosscal_refant))
                self.crosscal_refant = crosscal_refant

                # change the setting in selfcal
                config.set("SELFCAL", "selfcal_refant", "'{}'".format(refant_fluxcal_index + 1))

                # make a copy of old config file
                logger.info("Beam {0}: Creating backup of config file before adjusting settings".format(self.beam))
                subs_managefiles.director(
                    self, 'rn', self.config_file_name.replace(".cfg", "_backup_wrong_refant.cfg"), file_=self.config_file_name, ignore_nonexistent=True)

                # write changes to config file
                logger.info("Beam {0}: Writing changes to config file {1}".format(self.beam, self.config_file_name))
                with open(self.config_file_name, "w") as fp:
                    config.write(fp)
            else:
                logger.info("Beam {0}: No config file was specified. Cannot adjust setting for selfcal. Changing reference antenna only for crosscal to {1}".format(self.beam, crosscal_refant))
                self.crosscal_refant = crosscal_refant
        else:
            logger.info("Beam {0}: Reference antenna {1} set in config file is valid".format(self.beam, crosscal_refant))

        # Checking polcal but not doing anything at the moment if it fails
        refant_in_polcal = crosscal_refant in polcal_ant_list
        if refant_in_polcal and self.polcal != '':
            logger.info("Beam {0}: Reference antenna {1} exists in polarisation calibrator".format(
                self.beam, crosscal_refant))
        else:
            logger.warning("Beam {0}: Reference antenna {1} does NOT exists in polarisation calibrator. Polarisation will probably fail.".format(
                self.beam, crosscal_refant))


    def setflux(self):
        """
        Sets the models for the flux and polarisation calibrators
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Status of model of the flux and polarisation calibrator
        ccalfluxcalmodel = get_param_def(self, cbeam + '_fluxcal_model', False)
        ccalpolcalmodel = get_param_def(self, cbeam + '_polcal_model', False)

        if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
            # Ingest the model of the flux calibrator into the MODEL column
            if ccalfluxcalmodel:
                logger.info('Beam ' + self.beam + ': Model was already ingested into the flux calibrator dataset!')
            else:
                # Get the name of the calibrator
                ms = self.get_fluxcal_path()
                t = pt.table("%s::FIELD" % ms, ack=False)
                srcname = t.getcol('NAME')[0].split('_')[0].upper()
                av, fluxdensity, spix, reffreq, rotmeas = subs_calmodels.get_calparameters(srcname)
                cc_fluxcal_model = 'setjy(vis = "' + self.get_fluxcal_path() + '", scalebychan = True, standard = "manual", fluxdensity = [' + fluxdensity + '], spix = [' + spix + '], reffreq = "' + reffreq + '", rotmeas = ' + rotmeas + ', usescratch = True)'
                if av:
                    pass
                else:
                    error = 'Beam ' + self.beam + ': Calibrator model not in database for source ' + srcname
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_model', ccalfluxcalmodel)
                    subs_param.add_param(self, cbeam + '_polcal_model', ccalpolcalmodel)
                    raise ApercalException(error)
                lib.run_casa([cc_fluxcal_model], log_output=True, timeout=3600)

                # Check if model was ingested successfully
                if subs_msutils.has_good_modeldata(self.get_fluxcal_path()):
                    ccalfluxcalmodel = True
                else:
                    ccalfluxcalmodel = False
                    logger.warning('Beam ' + self.beam + ': Model not ingested properly. Flux scale and bandpass corrections will not be right!')
        else:
            logger.warning('Beam ' + self.beam + ': Fluxcal not set! No model ingested for flux calibrator!')


        if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
            # Ingest the model of the polarised calibrator into the MODEL column
            if ccalpolcalmodel:
                logger.info('Beam ' + self.beam + ': Model was already ingested into the polarised calibrator dataset!')
            else:
                # Get the name of the calibrator
                ms = self.get_polcal_path()
                t = pt.table("%s::FIELD" % ms, ack=False)
                srcname = t.getcol('NAME')[0].split('_')[0].upper()
                av, fluxdensity, spix, reffreq, rotmeas = subs_calmodels.get_calparameters(srcname)
                cc_polcal_model = 'setjy(vis = "' + self.get_polcal_path() + '", scalebychan = True, standard = "manual", fluxdensity = [' + fluxdensity + '], spix = [' + spix + '], reffreq = "' + reffreq + '", rotmeas = ' + rotmeas + ', usescratch = True)'
                if av:
                    pass
                else:
                    error = 'Beam ' + self.beam + ': Calibrator model not in database for source ' + srcname
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_model', ccalfluxcalmodel)
                    subs_param.add_param(self, cbeam + '_polcal_model', ccalpolcalmodel)
                    raise ApercalException(error)
                lib.run_casa([cc_polcal_model], log_output=True, timeout=3600)

                # Check if model was ingested successfully
                if subs_msutils.has_good_modeldata(self.get_polcal_path()):
                    ccalpolcalmodel = True
                else:
                    ccalpolcalmodel = False
                    logger.warning('Beam ' + self.beam + ': Model not ingested properly. Polarisation calibration corrections will not be right!')
        else:
            logger.warning('Beam ' + self.beam + ': Polcal not set! No model ingested for polarised calibrator!')

        subs_param.add_param(self, cbeam + '_fluxcal_model', ccalfluxcalmodel)
        subs_param.add_param(self, cbeam + '_polcal_model', ccalpolcalmodel)


    def initial_phase(self):
        """
        Initial phase calibration for the calibrators
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Status of the initial phase calibration for the flux calibrator
        ccalfluxcalmodel = get_param_def(self, cbeam + '_fluxcal_model', False)
        ccalfluxcalinitialphase = get_param_def(self, cbeam + '_fluxcal_initialphase', False)

        if self.crosscal_initial_phase:
            logger.info('Beam ' + self.beam + ': Calculating initial phase corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):

                # Check if model was ingested properly
                if ccalfluxcalmodel:

                    # Create the initial phase correction tables for the flux calibrator
                    fluxcal_G0ph = self.get_fluxcal_path().rstrip('.MS') + '.G0ph'
                    if ccalfluxcalinitialphase or os.path.isdir(fluxcal_G0ph):
                        logger.info('Beam ' + self.beam + ': Initial phase gain table for flux calibrator was already generated')
                        ccalfluxcalinitialphase = True
                    else:
                        gaincal_cmd = 'gaincal(vis="{vis}", caltable="{caltable}", gaintype="G", solint="int", ' \
                                      'refant="{refant}", calmode = "{calmode}")'
    
                        cc_fluxcal_ph = gaincal_cmd.format(vis=self.get_fluxcal_path(), caltable=fluxcal_G0ph, calmode="p", refant=self.crosscal_refant)
    
                        lib.run_casa([cc_fluxcal_ph], timeout=3600)
                        if os.path.isdir(fluxcal_G0ph):  # Check if calibration table was created successfully
                            ccalfluxcalinitialphase = True
                        else:
                            ccalfluxcalinitialphase = False
                            error = 'Beam ' + self.beam + ': Initial phase calibration table for flux calibrator was not created successfully!'
                            logger.error(error)
                            
                            # leaving function in order to restart
                            self.crosscal_try_restart = True
                            return
                            #subs_param.add_param(self, cbeam + '_fluxcal_initialphase', ccalfluxcalinitialphase)
                            #raise RuntimeError(error)
                else:
                    ccalfluxcalinitialphase = False
                    error = 'Beam ' + self.beam + ': Model for flux calibrator not ingested properly. Initial phase calibration not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_initialphase', ccalfluxcalinitialphase)
                    raise RuntimeError(error)
            else:
                error = 'Beam ' + self.beam + ': Flux calibrator dataset not specified or dataset not available. Cross calibration will probably not work!'
                logger.error(error)
                subs_param.add_param(self, cbeam + '_fluxcal_initialphase', ccalfluxcalinitialphase)
                raise RuntimeError(error)
        else:
            logger.warning('Beam ' + self.beam + ': Initial phase calibration for flux calibrator switched off!')

        subs_param.add_param(self, cbeam + '_fluxcal_initialphase', ccalfluxcalinitialphase)


    def global_delay(self):
        """
        Calculates the global delay corrections from the flux calibrator
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the global delay correction step

        ccalfluxcalmodel = get_param_def(self, cbeam + '_fluxcal_model', False)  # Status of model of the flux calibrator
        ccalfluxcalinitialphase = get_param_def(self, cbeam + '_fluxcal_initialphase', False)  # Status of the initial phase gains for the flux calibrator
        ccalfluxcalglobaldelay = get_param_def(self, cbeam + '_fluxcal_globaldelay', False)  # Status of the global delay corrections for the flux calibrator

        if self.crosscal_global_delay:
            logger.info('Beam ' + self.beam + ': Calculating global delay corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):

                # Check if model was ingested properly
                if ccalfluxcalmodel:

                    # Create the global delay correction table for the flux calibrator
                    fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                    if ccalfluxcalglobaldelay or os.path.isdir(fluxcal_K):
                        logger.info('Beam ' + self.beam + ': Global delay correction table for flux calibrator was already generated')
                        ccalfluxcalglobaldelay = True
                    else:
                        prevtables = '""'
                        interp = '""'
                        # Check for the initial phase calibration tbales
                        if ccalfluxcalinitialphase:
                            fluxcal_G0ph = self.get_fluxcal_path().rstrip('.MS') + '.G0ph'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_G0ph + '"', '"nearest"')
    
    
                        cc_fluxcal_globaldelay = 'gaincal(vis = "' + self.get_fluxcal_path() + '", caltable = "' + fluxcal_K + '", combine = "scan", gaintype = "K", solint = "inf", refant = "' + self.crosscal_refant + '", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                        lib.run_casa([cc_fluxcal_globaldelay], timeout=3600)
                        if os.path.isdir(fluxcal_K):  # Check if delay table was created successfully
                            ccalfluxcalglobaldelay = True
                        else:
                            ccalfluxcalglobaldelay = False
                            logger.error('Beam ' + self.beam + ': Global delay correction table for flux calibrator was not created successfully!')
                            
                            # leaving function in order to restart
                            self.crosscal_try_restart = True
                            return
                else:
                    ccalfluxcalglobaldelay = False
                    error = 'Beam ' + self.beam + ': Model for flux calibrator not ingested properly. Global delay calibration not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_globaldelay', ccalfluxcalglobaldelay)
                    raise RuntimeError(error)
            else:
                error = 'Beam ' + self.beam + ': Flux calibrator dataset not specified or dataset not available. Cross calibration will probably not work!'
                logger.error(error)
                subs_param.add_param(self, cbeam + '_fluxcal_globaldelay', ccalfluxcalglobaldelay)
                raise RuntimeError(error)
        else:
            logger.warning('Beam ' + self.beam + ': Global Delay calibration for flux calibrator switched off!')

        subs_param.add_param(self, cbeam + '_fluxcal_globaldelay', ccalfluxcalglobaldelay)


    def bandpass(self):
        """
        Creates the bandpass correction table using the flux calibrator.
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the bandpass correction step

        ccalfluxcalmodel = get_param_def(self, cbeam + '_fluxcal_model', False)  # Status of model of the flux calibrator
        ccalfluxcalinitialphase = get_param_def(self, cbeam + '_fluxcal_initialphase', False)  # Status of the initial phase gains for the flux calibrator
        ccalfluxcalglobaldelay = get_param_def(self, cbeam + '_fluxcal_globaldelay', False)  # Status of the global delay corrections for the flux calibrator
        ccalfluxcalbandpass = get_param_def(self, cbeam + '_fluxcal_bandpass', False) # Status of the bandpass table of the flux calibrator

        if self.crosscal_bandpass:
            logger.info('Beam ' + self.beam + ': Calculating bandpass corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):

                # Check if model was ingested properly
                if ccalfluxcalmodel:

                    # Calculate the bandpass for the flux calibrator
                    fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                    if ccalfluxcalbandpass or os.path.isdir(fluxcal_bscan):
                        logger.info('Beam ' + self.beam + ': Bandpass for flux calibrator was already derived successfully!')
                        ccalfluxcalbandpass = True
                    else:
                        prevtables = '""'
                        interp = '""'
                        if ccalfluxcalinitialphase:
                            fluxcal_G0ph = self.get_fluxcal_path().rstrip('.MS') + '.G0ph'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + fluxcal_G0ph + '"', '"nearest"')
                        if ccalfluxcalglobaldelay:
                            fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_K + '"', '"nearest"')
    
                        bandpass_cmd = 'bandpass(vis="{vis}", caltable="{caltable}", solint="inf", combine="scan, obs", ' \
                                       'refant="{refant}", solnorm=True, gaintable=[{gaintable}], interp=[{interp}])'
    
                        cc_fluxcal_bp = bandpass_cmd.format(vis=self.get_fluxcal_path(),
                                                            caltable=fluxcal_bscan,
                                                            refant=self.crosscal_refant,
                                                            gaintable=prevtables,
                                                            interp=interp)
    
                        lib.run_casa([cc_fluxcal_bp], timeout=3600)
                        # Check if bandpass table was created successfully
                        if os.path.isdir(fluxcal_bscan):
                            ccalfluxcalbandpass = True
                        else:
                            ccalfluxcalbandpass = False
                            error = 'Beam ' + self.beam + ': Initial bandpass calibration table for flux calibrator was not created successfully!'
                            logger.error(error)

                            # leaving function in order to restart
                            self.crosscal_try_restart = True
                            return
                            #subs_param.add_param(self, cbeam + '_fluxcal_bandpass', ccalfluxcalbandpass)
                            #raise RuntimeError(error)
                else:
                    ccalfluxcalbandpass = False
                    error = 'Beam ' + self.beam + ': Model for flux calibrator not ingested properly. Bandpass calibration not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_bandpass', ccalfluxcalbandpass)
                    raise RuntimeError(error)
            else:
                error = 'Beam ' + self.beam + ': Flux calibrator dataset {} not specified or dataset not available. Bandpass corrections ' + \
                        'are not available!'.format(self.get_fluxcal_path())
                logger.error(error)
        else:
            logger.warning('Beam ' + self.beam + ': Bandpass calibration for flux calibrator switched off!')

        subs_param.add_param(self, cbeam + '_fluxcal_bandpass', ccalfluxcalbandpass)

    def check_bandpass(self):
        """
        Function to check the quality of the bandpass phase solutions
        """

        logger.info("Beam {}: Nothing to check yet".format(self.beam))

    def gains(self):
        """
        Calculates the amplitude and phase gains for the flux calibrator
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the gain correction step

        ccalfluxcalmodel = get_param_def(self, cbeam + '_fluxcal_model', False)  # Status of model of the flux calibrator
        ccalfluxcalglobaldelay = get_param_def(self, cbeam + '_fluxcal_globaldelay', False)  # Status of the global delay corrections for the flux calibrator
        ccalfluxcalbandpass = get_param_def(self, cbeam + '_fluxcal_bandpass', False)  # Status of the bandpass table of the flux calibrator
        ccalfluxcalapgains = get_param_def(self, cbeam + '_fluxcal_apgains', False) # Status of the amplitude and phase gains for the flux calibrator

        if self.crosscal_gains:
            logger.info('Beam ' + self.beam + ': Calculating gain corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):

                # Check if model was ingested properly
                if ccalfluxcalmodel:

                    fluxcal_g1ap = self.get_fluxcal_path().rstrip('.MS') + '.G1ap'
    
                    # Create the amplitude and phase correction table for the flux calibrator
                    if ccalfluxcalapgains or os.path.isdir(fluxcal_g1ap):
                        logger.info('Beam ' + self.beam + ': Initial gain table for flux calibrator was already generated')
                        ccalfluxcalapgains = True
                    else:
                        prevtables = '""'
                        interp = '""'
    
                        # Check for the delay table to apply on the fly
                        if ccalfluxcalglobaldelay:
                            fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_K + '"', '"nearest"')
                        # Check for the bandpass calibration table to apply on-the-fly
                        if ccalfluxcalbandpass:
                            fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + fluxcal_bscan + '"', '"nearest"')
                        cc_fluxcal_apgain = 'gaincal(vis = "' + self.get_fluxcal_path() + '", caltable = "' + fluxcal_g1ap + '", gaintype = "G", solint = "int", refant = "' + self.crosscal_refant + '", calmode = "ap", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                        lib.run_casa([cc_fluxcal_apgain], timeout=3600)
                        # Check if gain table was created successfully
                        if os.path.isdir(fluxcal_g1ap):
                            ccalfluxcalapgains = True
                        else:
                            ccalfluxcalapgains = False
                            error = 'Beam ' + self.beam + ': Gain calibration table for flux calibrator was not created successfully!'
                            logger.error(error)

                            # leaving function in order to restart
                            self.crosscal_try_restart = True
                            return
                            
                            #subs_param.add_param(self, cbeam + '_fluxcal_apgains', ccalfluxcalapgains)
                            #raise RuntimeError(error)
                else:
                    ccalfluxcalapgains = False
                    error = 'Beam ' + self.beam + ': Model for flux calibrator not ingested properly. Gain calibration not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_apgains', ccalfluxcalapgains)
                    raise RuntimeError(error)
            else:
                error = 'Beam ' + self.beam + ': Flux calibrator dataset not specified or dataset {} not available. Cross calibration will probably not work!'.format(self.get_fluxcal_path())
                logger.error(error)
                subs_param.add_param(self, cbeam + '_fluxcal_apgains', ccalfluxcalapgains)
                raise RuntimeError(error)
        else:
            logger.warning('Beam ' + self.beam + ': Gain calibration for flux calibrator switched off!')

        subs_param.add_param(self, cbeam + '_fluxcal_apgains', ccalfluxcalapgains)


    def crosshand_delay(self):
        """
        Calculates the cross-hand delay corrections from the polarised calibrator
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the cross hand delay correction step

        ccalpolcalmodel = get_param_def(self, cbeam + '_polcal_model', False)  # Status of model of the polarised calibrator
        ccalfluxcalglobaldelay = get_param_def(self, cbeam + '_fluxcal_globaldelay', False)  # Status of the global delay corrections for the flux calibrator
        ccalfluxcalbandpass = get_param_def(self, cbeam + '_fluxcal_bandpass', False)  # Status of the bandpass table of the flux calibrator
        ccalfluxcalapgains = get_param_def(self, cbeam + '_fluxcal_apgains', False) # Status of the amplitude and phase gains for the flux calibrator
        ccalpolcalcrosshanddelay = get_param_def(self, cbeam + '_polcal_crosshanddelay', False) # Status of the cross hand delay calibration from the polarised calibrator

        if self.crosscal_crosshand_delay:
            logger.info('Beam ' + self.beam + ': Calculating cross-hand delay corrections for polarised calibrator')

            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):

                # Check if model was ingested properly
                if ccalpolcalmodel:

                # Create the cross hand delay correction table for the polarised calibrator

                    polcal_Kcross = self.get_polcal_path().rstrip('.MS') + '.Kcross'
                    if ccalpolcalcrosshanddelay or os.path.isdir(polcal_Kcross):
                        logger.info('Beam ' + self.beam + ': Cross hand delay correction table for polarised calibrator was already generated')
                        ccalpolcalcrosshanddelay = True
                    else:
                        prevtables = '""'
                        interp = '""'

                        # Check for the global delay table to apply on-the-fly
                        if ccalfluxcalglobaldelay:
                            fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_K + '"', '"nearest"')

                        # Check for the bandpass calibration table to apply on-the-fly
                        if ccalfluxcalbandpass:
                            fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_bscan + '"', '"nearest"')

                        # Check for the gain calibration table to apply on-the-fly
                        if ccalfluxcalapgains:
                            fluxcal_g1ap = self.get_fluxcal_path().rstrip('.MS') + '.G1ap'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,'"' + fluxcal_g1ap + '"', '"nearest"')

                        cc_polcal_crosshanddelay = 'gaincal(vis = "' + self.get_polcal_path() + '", caltable = "' + polcal_Kcross + '", combine = "scan", gaintype = "KCROSS", solint = "inf", refant = "' + self.crosscal_refant + '", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                        lib.run_casa([cc_polcal_crosshanddelay], timeout=3600)
                        if os.path.isdir(polcal_Kcross):  # Check if the cross hand delay table was created successfully
                            ccalpolcalcrosshanddelay = True
                        else:
                            ccalpolcalcrosshanddelay = False
                            logger.error('Beam ' + self.beam + ': Cross hand delay correction table for polarised calibrator was '
                                         'not created successfully!')
                else:
                    ccalpolcalcrosshanddelay = False
                    error = 'Beam ' + self.beam + ': Model for polarised calibrator not ingested properly. Cross hand delay calibration not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_polcal_crosshanddelay', ccalpolcalcrosshanddelay)
                    raise RuntimeError(error)
            else:
                ccalpolcalcrosshanddelay = False
                error = 'Beam ' + self.beam + ': Polarised calibrator dataset not specified or dataset not available. Polarisation ' + \
                        'calibration will probably not work!'
                logger.error(error)

        subs_param.add_param(self, cbeam + '_polcal_crosshanddelay', ccalpolcalcrosshanddelay)


    def leakage(self):
        """
        Calculates the leakage corrections from the flux calibrator
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the leakage correction step

        ccalfluxcalmodel = get_param_def(self, cbeam + '_fluxcal_model', False)  # Status of model of the flux calibrator
        ccalfluxcalglobaldelay = get_param_def(self, cbeam + '_fluxcal_globaldelay', False)  # Status of the global delay corrections for the flux calibrator
        ccalfluxcalbandpass = get_param_def(self, cbeam + '_fluxcal_bandpass', False)  # Status of the bandpass table of the flux calibrator
        ccalfluxcalapgains = get_param_def(self, cbeam + '_fluxcal_apgains', False) # Status of the amplitude and phase gains for the flux calibrator
        ccalpolcalcrosshanddelay = get_param_def(self, cbeam + '_polcal_crosshanddelay', False) # Status of the cross hand delay calibration from the polarised calibrator
        ccalfluxcalleakage = get_param_def(self, cbeam + '_fluxcal_leakage', False)  # Status of the leakage corrections for the flux calibrator

        if self.crosscal_leakage:
            logger.info('Beam ' + self.beam + ': Calculating leakage corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):

                # Check if model was ingested properly
                if ccalfluxcalmodel:

                    # Create the leakage correction table for the flux calibrator

                    fluxcal_Df = self.get_fluxcal_path().rstrip('.MS') + '.Df'
                    if ccalfluxcalleakage or os.path.isdir(fluxcal_Df):
                        logger.info('Beam ' + self.beam + ': Leakage correction table for flux calibrator was already generated')
                        ccalfluxcalleakage = True
                    else:
                        prevtables = '""'
                        interp = '""'

                        # Check for the global delay table to apply on-the-fly
                        if ccalfluxcalglobaldelay:
                            fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_K + '"', '"nearest"')

                        # Check for the bandpass calibration table to apply on-the-fly
                        if ccalfluxcalbandpass:
                            fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_bscan + '"', '"nearest"')

                        # Check for the gain calibration table to apply on-the-fly
                        if ccalfluxcalapgains:
                            fluxcal_g1ap = self.get_fluxcal_path().rstrip('.MS') + '.G1ap'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,'"' + fluxcal_g1ap + '"', '"nearest"')

                        # Check for the cross hand calibration table to apply on-the-fly
                        if ccalpolcalcrosshanddelay:
                            polcal_Kcross = self.get_polcal_path().rstrip('.MS') + '.Kcross'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + polcal_Kcross + '"', '"nearest"')

                        cc_fluxcal_leakage = 'polcal(vis = "' + self.get_fluxcal_path() + '", caltable = "' + fluxcal_Df  + '", combine = "scan", poltype = "Df", solint = "inf", refant = "' + self.crosscal_refant + '", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                        lib.run_casa([cc_fluxcal_leakage], timeout=3600)
                        if os.path.isdir(fluxcal_Df):  # Check if gain table was created successfully
                            ccalfluxcalleakage = True
                        else:
                            ccalfluxcalleakage = False
                            logger.error('Beam ' + self.beam + ': Leakage correction table for flux calibrator was not created successfully!')
                else:
                    ccalfluxcalleakage = False
                    error = 'Beam ' + self.beam + ': Model for flux calibrator not ingested properly. Leakage calibration not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_leakage', ccalfluxcalleakage)
                    raise RuntimeError(error)
            else:
                error = 'Beam ' + self.beam + ': Flux calibrator dataset not specified or dataset not available. Cross calibration will probably not work!'
                logger.error(error)
                subs_param.add_param(self, cbeam + '_fluxcal_leakage', ccalfluxcalleakage)
                raise RuntimeError(error)

        subs_param.add_param(self, cbeam + '_fluxcal_leakage', ccalfluxcalleakage)


    def polarisation_angle(self):
        """
        Calculates the polarisation angle corrections from the polarised calibrator
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the polarisation angle correction step

        ccalpolcalmodel = get_param_def(self, cbeam + '_polcal_model', False)  # Status of model of the polarised calibrator
        ccalfluxcalglobaldelay = get_param_def(self, cbeam + '_fluxcal_globaldelay', False)  # Status of the global delay corrections for the flux calibrator
        ccalfluxcalbandpass = get_param_def(self, cbeam + '_fluxcal_bandpass', False)  # Status of the bandpass table of the flux calibrator
        ccalfluxcalapgains = get_param_def(self, cbeam + '_fluxcal_apgains', False) # Status of the amplitude and phase gains for the flux calibrator
        ccalpolcalcrosshanddelay = get_param_def(self, cbeam + '_polcal_crosshanddelay', False) # Status of the cross hand delay calibration from the polarised calibrator
        ccalfluxcalleakage = get_param_def(self, cbeam + '_fluxcal_leakage', False)  # Status of the leakage corrections for the flux calibrator
        ccalpolcalpolarisationangle = get_param_def(self, cbeam + '_polcal_polarisationangle', False)  # Status of the polarisation angle corrections for the polarised calibrator

        if not subs_calmodels.is_polarised(self.polcal) and self.crosscal_polarisation_angle:
            self.crosscal_polarisation_angle = False
            logger.warning('Beam ' + self.beam + ': Changing crosscal_polarisation angle to false because ' + self.polcal +
                           'is unpolarised.')

        if self.crosscal_polarisation_angle:
            logger.info('Beam ' + self.beam + ': Calculating polarisation angle corrections for polarised calibrator')

            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                # Create the polarisation angle correction table for the polarised calibrator

                # Check if model was ingested properly
                if ccalpolcalmodel:

                    polcal_Xf = self.get_polcal_path().rstrip('.MS') + '.Xf'
                    if ccalpolcalpolarisationangle or os.path.isdir(polcal_Xf):
                        logger.info(
                            'Beam ' + self.beam + ': Polarisation angle correction table for polarised calibrator was already generated')
                        ccalpolcalpolarisationangle = True
                    else:
                        prevtables = '""'
                        interp = '""'

                        # Check for the global delay table to apply on-the-fly
                        if ccalfluxcalglobaldelay:
                            fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_K + '"', '"nearest"')

                        # Check for the bandpass calibration table to apply on-the-fly
                        if ccalfluxcalbandpass:
                            fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_bscan + '"', '"nearest"')

                        # Check for the gain calibration table to apply on-the-fly
                        if ccalfluxcalapgains:
                            fluxcal_g1ap = self.get_fluxcal_path().rstrip('.MS') + '.G1ap'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_g1ap + '"', '"nearest"')

                        # Check for the cross hand calibration table to apply on-the-fly
                        if ccalpolcalcrosshanddelay:
                            polcal_Kcross = self.get_polcal_path().rstrip('.MS') + '.Kcross'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + polcal_Kcross + '"', '"nearest"')

                        # Check for the leakage calibration table to apply on-the-fly
                        if ccalfluxcalleakage:
                            fluxcal_Df = self.get_fluxcal_path().rstrip('.MS') + '.Df'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_Df + '"', '"nearest"')

                        cc_polcal_polarisationangle = 'polcal(vis = "' + self.get_polcal_path() + '", caltable = "' + polcal_Xf + '", combine = "scan", poltype = "Xf", solint = "inf", refant = "' + self.crosscal_refant + '", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                        lib.run_casa([cc_polcal_polarisationangle], timeout=3600)
                        if os.path.isdir(polcal_Xf):  # Check if gain table was created successfully
                            ccalpolcalpolarisationangle = True
                        else:
                            ccalpolcalpolarisationangle = False
                            logger.error('Beam ' + self.beam + ': Polarisation angle correction table for polarised calibrator '
                                         'was not created successfully!')

                else:
                    ccalpolcalpolarisationangle = False
                    error = 'Beam ' + self.beam + ': Model for polarised calibrator not ingested properly. Polarisation angle calibration not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_polcal_polarisationangle', ccalpolcalpolarisationangle)
                    raise RuntimeError(error)

            else:
                msg = 'Beam ' + self.beam + ': Polarised calibrator dataset not specified or dataset not available.' + \
                      'Cross calibration will probably not work!'
                logger.error(msg)

        subs_param.add_param(self, cbeam + '_polcal_polarisationangle', ccalpolcalpolarisationangle)


    def transfer_to_cal(self):
        """
        Applies the correction tables to the calibrators
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the transfer step

        ccalfluxcalmodel = get_param_def(self, cbeam + '_fluxcal_model', False)  # Status of model of the flux calibrator
        ccalpolcalmodel = get_param_def(self, cbeam + '_polcal_model', False)  # Status of model of the polarised calibrator
        ccalfluxcalglobaldelay = get_param_def(self, cbeam + '_fluxcal_globaldelay', False)  # Status of the global delay corrections for the flux calibrator
        ccalfluxcalbandpass = get_param_def(self, cbeam + '_fluxcal_bandpass', False)  # Status of the bandpass table of the flux calibrator
        ccalfluxcalapgains = get_param_def(self, cbeam + '_fluxcal_apgains', False) # Status of the amplitude and phase gains for the flux calibrator
        ccalpolcalcrosshanddelay = get_param_def(self, cbeam + '_polcal_crosshanddelay', False) # Status of the cross hand delay calibration from the polarised calibrator
        ccalfluxcalleakage = get_param_def(self, cbeam + '_fluxcal_leakage', False)  # Status of the leakage corrections for the flux calibrator
        ccalpolcalpolarisationangle = get_param_def(self, cbeam + '_polcal_polarisationangle', False)  # Status of the polarisation angle corrections for the polarised calibrator
        ccalfluxcaltransfer = get_param_def(self, cbeam + '_fluxcal_transfer', False)  # Status of the solution transfer for the flux calibrator
        ccalpolcaltransfer = get_param_def(self, cbeam + '_polcal_transfer', False)  # Status of the solution transfer for the polarised calibrator

        if self.crosscal_transfer_to_cal:
            logger.info('Beam ' + self.beam + ': Applying solutions to calibrators')

            # Apply solutions to the flux calibrator

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                
                # Check if model was ingested properly
                if ccalfluxcalmodel:

                    if ccalfluxcaltransfer:
                        logger.info('Beam ' + self.beam + ': Solution tables were already applied to flux calibrator')
                        ccalfluxcaltransfer = True
                    else:
                        # Check which calibration tables are available for the flux calibrator
                        prevtables = '""'
                        interp = '""'
    
                        # Check for the global delay table to apply on-the-fly
                        if ccalfluxcalglobaldelay:
                            fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_K + '"', '"nearest"')
    
                        # Check for the bandpass calibration table to apply on-the-fly
                        if ccalfluxcalbandpass:
                            fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_bscan + '"', '"nearest"')
    
                        # Check for the gain calibration table to apply on-the-fly
                        if ccalfluxcalapgains:
                            fluxcal_g1ap = self.get_fluxcal_path().rstrip('.MS') + '.G1ap'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_g1ap + '"', '"nearest"')
    
                        # Check for the cross hand calibration table to apply on-the-fly
                        if ccalpolcalcrosshanddelay:
                            polcal_Kcross = self.get_polcal_path().rstrip('.MS') + '.Kcross'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + polcal_Kcross + '"', '"nearest"')
    
                        # Check for the leakage calibration table to apply on-the-fly
                        if ccalfluxcalleakage:
                            fluxcal_Df = self.get_fluxcal_path().rstrip('.MS') + '.Df'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_Df + '"', '"nearest"')

                        # Check for the polarisation angle calibration on-the-fly
                        if ccalpolcalpolarisationangle:
                            polcal_Xf = self.get_polcal_path().rstrip('.MS') + '.Xf'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + polcal_Xf + '"', '"nearest"')
                            
                        cc_fluxcal_saveflags = 'flagmanager(vis = "' + self.get_fluxcal_path() + '", mode = "save", versionname = "ccal")'
                        cc_fluxcal_apply = 'applycal(vis = "' + self.get_fluxcal_path() + '", gaintable = [' + prevtables + '], interp = [' + interp + '], parang = False, flagbackup = False)'
                        lib.run_casa([cc_fluxcal_saveflags, cc_fluxcal_apply], timeout=3600)
                        if subs_msutils.has_correcteddata(self.get_fluxcal_path()):
                            ccalfluxcaltransfer = True
                        else:
                            ccalfluxcaltransfer = False
                            logger.warning('Beam ' + self.beam + ': Corrected visibilities were not written to flux calibrator dataset !')
                else:
                    ccalfluxcaltransfer = False
                    error = 'Beam ' + self.beam + ': Model for flux calibrator not ingested properly. Application of cross calibration solutions not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_transfer', ccalfluxcaltransfer)
                    subs_param.add_param(self, cbeam + '_polcal_transfer', ccalpolcaltransfer)
                    raise RuntimeError(error)
            else:
                ccalfluxcaltransfer = False
                error = 'Beam ' + self.beam + ': Flux calibrator dataset not specified or dataset not available. Application of cross calibration solutions not possible!'
                subs_param.add_param(self, cbeam + '_fluxcal_transfer', ccalfluxcaltransfer)
                subs_param.add_param(self, cbeam + '_polcal_transfer', ccalpolcaltransfer)
                logger.error(error)
                raise RuntimeError(error)
                

            # Apply solutions to the polarised calibrator

            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):

                # Check if model was ingested properly
                if ccalpolcalmodel:

                    if ccalpolcaltransfer:
                        logger.info('Beam ' + self.beam + ': Solution tables were already applied to the polarised calibrator')
                        ccalpolcaltransfer = True
                    else:
                        # Check which calibration tables are available for the polarised calibrator
                        prevtables = '""'
                        interp = '""'

                        # Check for the global delay table to apply on-the-fly
                        if ccalfluxcalglobaldelay:
                            fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_K + '"', '"nearest"')

                        # Check for the bandpass calibration table to apply on-the-fly
                        if ccalfluxcalbandpass:
                            fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_bscan + '"', '"nearest"')

                        # Check for the gain calibration table to apply on-the-fly
                        if ccalfluxcalapgains:
                            fluxcal_g1ap = self.get_fluxcal_path().rstrip('.MS') + '.G1ap'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_g1ap + '"', '"nearest"')

                        # Check for the cross hand calibration table to apply on-the-fly
                        if ccalpolcalcrosshanddelay:
                            polcal_Kcross = self.get_polcal_path().rstrip('.MS') + '.Kcross'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + polcal_Kcross + '"', '"nearest"')

                        # Check for the leakage calibration table to apply on-the-fly
                        if ccalfluxcalleakage:
                            fluxcal_Df = self.get_fluxcal_path().rstrip('.MS') + '.Df'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_Df + '"', '"nearest"')

                        # Check for the polarisation angle calibration on-the-fly
                        if ccalpolcalpolarisationangle:
                            polcal_Xf = self.get_polcal_path().rstrip('.MS') + '.Xf'
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + polcal_Xf + '"', '"nearest"')

                        cc_polcal_saveflags = 'flagmanager(vis = "' + self.get_polcal_path() + '", mode = "save", versionname = "ccal")'
                        cc_polcal_apply = 'applycal(vis = "' + self.get_polcal_path() + '", gaintable = [' + prevtables + '], interp = [' + interp + '], parang = False, flagbackup = False)'
                        lib.run_casa([cc_polcal_saveflags, cc_polcal_apply], timeout=3600)
                        if subs_msutils.has_correcteddata(self.get_polcal_path()):
                            ccalpolcaltransfer = True
                        else:
                            ccalpolcaltransfer = False
                            logger.warning('Beam ' + self.beam + ': Corrected visibilities were not written to polarised calibrator dataset !')
                else:
                    ccalpolcaltransfer = False
                    error = 'Beam ' + self.beam + ': Model for polarised calibrator not ingested properly. Application of cross calibration solutions not possible!'
                    logger.error(error)
                    subs_param.add_param(self, cbeam + '_fluxcal_transfer', ccalfluxcaltransfer)
                    subs_param.add_param(self, cbeam + '_polcal_transfer', ccalpolcaltransfer)
                    raise RuntimeError(error)
            else:
                ccalfluxcaltransfer = False
                error = 'Beam ' + self.beam + ': Polarised calibrator dataset not specified or dataset not available. Application of cross calibration solutions not possible!'
                subs_param.add_param(self, cbeam + '_fluxcal_transfer', ccalfluxcaltransfer)
                subs_param.add_param(self, cbeam + '_polcal_transfer', ccalpolcaltransfer)
                logger.error(error)
                # do not raise exception as it prevents the pipeline from running with fluxcal-only
                # raise RuntimeError(error)

        subs_param.add_param(self, cbeam + '_fluxcal_transfer', ccalfluxcaltransfer)
        subs_param.add_param(self, cbeam + '_polcal_transfer', ccalpolcaltransfer)


    def transfer_to_target(self):
        """
        Applies the correction tables to the target beams
        """

        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the transfer step

        # Status of the solution transfer for the target beams
        ccalfluxcalglobaldelay = get_param_def(self, cbeam + '_fluxcal_globaldelay', False)  # Status of the global delay corrections for the flux calibrator
        ccalfluxcalbandpass = get_param_def(self, cbeam + '_fluxcal_bandpass', False)  # Status of the bandpass table of the flux calibrator
        ccalfluxcalapgains = get_param_def(self, cbeam + '_fluxcal_apgains', False) # Status of the amplitude and phase gains for the flux calibrator
        ccalpolcalcrosshanddelay = get_param_def(self, cbeam + '_polcal_crosshanddelay', False) # Status of the cross hand delay calibration from the polarised calibrator
        ccalfluxcalleakage = get_param_def(self, cbeam + '_fluxcal_leakage', False)  # Status of the leakage corrections for the flux calibrator
        ccalpolcalpolarisationangle = get_param_def(self, cbeam + '_polcal_polarisationangle', False)  # Status of the polarisation angle corrections for the polarised calibrator
        ccaltargetbeamstransfer = get_param_def(self, cbeam + '_targetbeams_transfer', False)

        if self.crosscal_transfer_to_target:
            logger.info('Beam ' + self.beam + ': Applying solutions to target dataset')

            # Apply solutions to the target beams

            if self.target != '' and os.path.isdir(self.get_target_path()):
                if ccaltargetbeamstransfer:
                    logger.info('Beam ' + self.beam + ': Solutions were already applied to target dataset')
                    ccaltargetbeamstransfer = True
                else:
                    # Check which calibration tables are available for each beam
                    prevtables = '""'
                    interp = '""'

                    # Check for the global delay table to apply on-the-fly
                    if ccalfluxcalglobaldelay:
                        fluxcal_K = self.get_fluxcal_path().rstrip('.MS') + '.K'
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_K + '"', '"nearest"')

                    # Check for the bandpass calibration table to apply on-the-fly
                    if ccalfluxcalbandpass:
                        fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_bscan + '"', '"nearest"')

                    # Check for the gain calibration table to apply on-the-fly
                    if ccalfluxcalapgains:
                        fluxcal_g1ap = self.get_fluxcal_path().rstrip('.MS') + '.G1ap'
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_g1ap + '"', '"nearest"')

                    # Check for the cross hand calibration table to apply on-the-fly
                    if ccalpolcalcrosshanddelay:
                        polcal_Kcross = self.get_polcal_path().rstrip('.MS') + '.Kcross'
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + polcal_Kcross + '"', '"nearest"')

                    # Check for the leakage calibration table to apply on-the-fly
                    if ccalfluxcalleakage:
                        fluxcal_Df = self.get_fluxcal_path().rstrip('.MS') + '.Df'
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + fluxcal_Df + '"', '"nearest"')

                    # Check for the polarisation angle calibration on-the-fly
                    if ccalpolcalpolarisationangle:
                        polcal_Xf = self.get_polcal_path().rstrip('.MS') + '.Xf'
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp, '"' + polcal_Xf + '"', '"nearest"')

                    # Execute the CASA command to apply the solutions
                    logger.debug('Beam ' + self.beam + ': Applying solutions to target dataset')
                    cc_targetbeams_saveflags = 'flagmanager(vis = "' + self.get_target_path() + '", mode = "save", versionname = "ccal")'  # Save the flags before applying solutions
                    cc_targetbeams_apply = 'applycal(vis = "' + self.get_target_path() + '", gaintable = [' + prevtables + '], interp = [' + interp + '], parang = False, flagbackup = False)'
                    lib.run_casa([cc_targetbeams_saveflags, cc_targetbeams_apply], timeout=10000)
                    if subs_msutils.has_correcteddata(self.get_target_path()):
                        ccaltargetbeamstransfer = True
                    else:
                        ccaltargetbeamstransfer = False
                        logger.warning('Beam ' + self.beam + ': Corrected visibilities were not written to target dataset!')
            else:
                ccaltargetbeamstransfer = False
                error = 'Beam ' + self.beam + ': No target dataset specified or target dataset not available! Not applying solutions to target dataset'
                subs_param.add_param(self, cbeam + '_targetbeams_transfer', ccaltargetbeamstransfer)
                logger.error(error)
                raise RuntimeError(error)


        subs_param.add_param(self, cbeam + '_targetbeams_transfer', ccaltargetbeamstransfer)

    def check_autocorrelation(self):
        """
        Check the autocorrelation in relation to expected values and flag data
        if necessary.

        The function will check the autocorrelation for each telescope in XX and YY
        with respect to an expected distribution. It will check the relative offset 
        and the to some extent the shape of the autocorrelation. If one or the other
        shows an issue, the polarisation of this telescope will get flagged
        """

        logger.info("Beam {}: Checking autocorrelation".format(self.beam))

        # check only the flux calibrator
        msfile = self.get_fluxcal_path()

        # get the names of all antennas
        taql_antnames = "SELECT NAME FROM {0}::ANTENNA".format(msfile)
        try:
            t = pt.taql(taql_antnames)
        except Exception as e:
            logger.exception(e)
            raise RuntimeError(e)
        ant_names = t.getcol("NAME")
        if ant_names is None:
            error = "No antenna names available from the MS file. Abort"
            logger.error(error)
            raise RuntimeError(error)

        #then get frequencies:
        taql_freq = "SELECT CHAN_FREQ FROM {0}::SPECTRAL_WINDOW".format(
            msfile)
        try:
            t = pt.taql(taql_freq)
        except Exception as e:
            logger.exception(e)
            raise RuntimeError(e)
        freqs = t.getcol('CHAN_FREQ')[0, :]
        if freqs is None:
            error = "No frequency information available from the MS file. Abort"
            logger.error(error)
            raise RuntimeError(error)

        #and number of stokes params
        taql_stokes = "SELECT abs(DATA) AS amp from {0} limit 1" .format(
            msfile)
        try:
            t_pol = pt.taql(taql_stokes)
        except Exception as e:
            logger.exception(e)
            raise RuntimeError(e)
        pol_array = t_pol.getcol('amp')
        if pol_array is None:
            error = "No polarisation information available from the MS file. Abort"
            logger.error(error)
            raise RuntimeError(error)
        
        n_stokes = pol_array.shape[2]  # shape is time, one, nstokes
    
        logger.info("Beam {}: Inspecting autocorrelation of each antenna".format(self.beam))

        # list of flags
        ccal_flag_list = []
        #flag_pol = []
        # list of polarisation
        # 0 = 'XX', 3 = 'YY'
        pol_list_ms = [0, 3]
        pol_list = ['XX', 'XY', 'YX', 'YY']

        # take MS file and get calibrated data
        # amp_ant_array = np.empty(
        #     (len(ant_names), len(freqs), n_stokes), dtype=np.float64)        
        for ant, ant_name in enumerate(ant_names):
            # getting the autocorrelation amplitude
            try:
                taql_command = ("SELECT abs(gmeans(CORRECTED_DATA[FLAG])) AS amp "
                                "FROM {0} "
                                "WHERE ANTENNA1==ANTENNA2 && (ANTENNA1={1} || ANTENNA2={1})").format(msfile, ant)
                t = pt.taql(taql_command)
                test = t.getcol('amp')
                amp_ant = t.getcol('amp')[0, :, :]
            except Exception as e:
                logger.warning("Beam {}: Could not get autocorrelation information for antenna {}".format(self.beam, ant_name))
                logger.exception(e)
                continue    
            
            # get XX and YY
            # amp_XX = amp_ant[:, 0]
            # amp_YY = amp_ant[:, 3]
            # freqs_XX_selected = freqs[np.where(amp_XX != 0)[0]]
            # amp_XX_selected = amp_XX[np.where(amp_XX != 0)[0]]
            # freqs_YY_selected = freqs[np.where(amp_YY != 0)[0]]
            # amp_YY_selected = amp_YY[np.where(amp_YY != 0)[0]]
        
            logger.info("Beam {0}: Checking autocorrelation amplitude of antenna {1}".format(self.beam, ant_name))
            for pol_nr in pol_list_ms:
                amp = amp_ant[:, pol_nr]
                freqs_selected = freqs[np.where(amp != 0)[0]]
                amp_selected = amp[np.where(amp != 0)[0]]

                if len(amp_selected) == 0:
                    logger.warning("Beam {0}, Antenna {1} (polarization {2}): No autocorrelation data available".format(
                        self.beam, ant_name, pol_list[pol_nr], ratio_vis_above_limit))
                    continue

                ratio_vis_above_limit = ccal_utils.get_ratio_autocorrelation_above_limit(amp_selected, self.crosscal_autocorrelation_amp_limit)
                if ratio_vis_above_limit > self.crosscal_autocorrelation_data_fraction_limit:
                    logger.info(
                        "Beam {0}, Antenna {1} (polarization {2}): fraction of autocorrelation data above amplitude threshold: {3} => Flagging polarisation {2}".format(self.beam, ant_name, pol_list[pol_nr], ratio_vis_above_limit))
                    ccal_flag_list.append([ant_name, pol_list[pol_nr]])
                    #flag_ant = flag_ant.append(ant_name)
                    #flag_pol = flag_pol.append(pol_list[pol_nr])
                else:
                    logger.info(
                        "Beam {0}, Antenna {1} (polarization {2}): fraction of autocorrelation data above amplitude threshold: {3} => No flagging".format(self.beam, ant_name, pol_list[pol_nr], ratio_vis_above_limit))
                
            # run check of fit to autocorrelation
            logger.info("Checking fit of autocorrelation not yet available")

            # run check of bandpass phase solutions
            logger.info("Checking bandpass phase solution not yet available")
        
        # cannot flag here only set restart
        # need to flag after resetting, otherwise flags are gone
        if len(ccal_flag_list) != 0:
            logger.info("Found data for flagging. Setting restart")
            
            # for ant, pol in zip(flag_ant, flag_pol):
            #     # call function for flagging
            #     flag_data(polarisation = flag_pol, antenna = ant)
            
            self.crosscal_try_restart = True
            self.crosscal_flag_list = ccal_flag_list
        else:
            self.crosscal_flag_list = None

        logger.info("Beam {}: Checking autocorrelation ... Done".format(self.beam))

    def flag_data(self):
        """
        Function to flag a polarisation for a given antenna
        """

        cbeam = 'ccal_B' + str(self.beam).zfill(2)
        ccal_flag_list = subs_param.get_param_def(
            self, cbeam + '_flag_list', None)

        if self.crosscal_flag_list is not None:

            logger.info("Beam {}: Flagging data".format(self.beam))
            # create a casa-conform list
            casa_list = ["antenna={1} corr={2}".format(flag[0], flag[1]) for flag in self.crosscal_flag_list]
            logger.info("Beam {0}: Flagging polarisation {1} for antenna {2}".format(self.beam, polarisation, antenna))
            flag_cmd = 'flagdata(vis="{0}", mode="list", {1}, flagbackup=False)'.format(self.get_fluxcal_path(), antenna, polarisation)
            logger.debug(flag_cmd)
            lib.run_casa([flag_cmd])
            logger.info("Beam {0}: Flagging data ... Done".format(self.beam))
            # check if there is already a flag list

            ccal_flag_list = ccal_flag_list + self.crosscal_flag_list
            
        subs_param.add_param(self, cbeam + '_flag_list', ccal_flag_list)

            

    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during CROSSCAL. No detailed
        summary is available for CROSSCAL.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in
        the notebook
        """

        # Load the parameters from the parameter file

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        FMOD = subs_param.get_param_def(self, cbeam + '_fluxcal_model', False)
        PMOD = subs_param.get_param_def(self, cbeam + '_polcal_model', False)
        FIPH = subs_param.get_param_def(self, cbeam + '_fluxcal_initial_phase', False)
        FGD = subs_param.get_param_def(self, cbeam + '_fluxcal_globaldelay', False)
        FBP = subs_param.get_param_def(self, cbeam + '_fluxcal_bandpass', False)
        FG = subs_param.get_param_def(self, cbeam + '_fluxcal_apgains', False)
        PCD = subs_param.get_param_def(self, cbeam + '_polcal_crosshanddelay', False)
        FL = subs_param.get_param_def(self, cbeam + '_fluxcal_leakage', False)
        PPA = subs_param.get_param_def(self, cbeam + '_polcal_polarisationangle', False)
        FT = subs_param.get_param_def(self, cbeam + '_fluxcal_transfer', False)
        PT = subs_param.get_param_def(self, cbeam + '_polcal_transfer', False)
        TT = get_param_def(self, cbeam + '_targetbeams_transfer', False)

        # Create the data frame

        beam_range = range(self.NBEAMS)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = ['Flux calibrator (' + self.fluxcal[:-3] + ')',
                           'Polarised calibrator (' + self.polcal[:-3] + ')'] + dataset_beams

        all_MOD = np.full(self.NBEAMS + 2, '   NA')
        all_MOD[0] = str(FMOD)
        all_MOD[1] = str(PMOD)

        all_IPH = np.full(self.NBEAMS + 2, '   NA')
        all_IPH[0] = str(FIPH)

        all_GD = np.full(self.NBEAMS + 2, '   NA')
        all_GD[0] = str(FGD)

        all_BP = np.full(self.NBEAMS + 2, '   NA')
        all_BP[0] = str(FBP)

        all_G = np.full(self.NBEAMS + 2, '   NA')
        all_G[0] = str(FG)

        all_CD = np.full(self.NBEAMS + 2, '   NA')
        all_CD[1] = str(PCD)

        all_L = np.full(self.NBEAMS + 2, '   NA')
        all_L[0] = str(FL)

        all_PA = np.full(self.NBEAMS + 2, '   NA')
        all_PA[1] = str(PPA)

        all_T = np.full(self.NBEAMS + 2, False)
        all_T[0] = FT
        all_T[1] = PT
        all_T[2:] = TT

        df_mod = pd.DataFrame(np.ndarray.flatten(all_MOD), index=dataset_indices, columns=['Model'])
        df_iph = pd.DataFrame(np.ndarray.flatten(all_IPH), index=dataset_indices, columns=['Initial Phase'])
        df_gd = pd.DataFrame(np.ndarray.flatten(all_GD), index=dataset_indices, columns=['Global Delay'])
        df_bp = pd.DataFrame(np.ndarray.flatten(all_BP), index=dataset_indices, columns=['Bandpass'])
        df_g = pd.DataFrame(np.ndarray.flatten(all_G), index=dataset_indices, columns=['Gains'])
        df_cd = pd.DataFrame(np.ndarray.flatten(all_CD), index=dataset_indices, columns=['Cross Hand Delay'])
        df_l = pd.DataFrame(np.ndarray.flatten(all_L), index=dataset_indices, columns=['Leakage'])
        df_pa = pd.DataFrame(np.ndarray.flatten(all_PA), index=dataset_indices, columns=['Polarisation Angle'])
        df_t = pd.DataFrame(np.ndarray.flatten(all_T), index=dataset_indices, columns=['Transfer'])

        df = pd.concat([df_mod, df_iph, df_gd, df_bp, df_g, df_cd, df_l, df_pa, df_t], axis=1)

        return df


    def reset(self, do_clearcal = True, do_clearcal_fluxcal = False, do_clearcal_polcal=False, do_clearcal_target=False):
        """
        Function to reset the current step and clear all calibration from datasets as well as all calibration tables.
        """
        subs_setinit.setinitdirs(self)

        cbeam = 'ccal_B' + str(self.beam).zfill(2)

        logger.warning('Beam ' + self.beam + ': Resetting flags and data values to before cross-calibration step')
        # Remove the calibration tables
        # for all beams and calibrators
        subs_managefiles.director(self, 'rm', self.get_fluxcal_path().rstrip(
                                  '.MS') + '.G0ph', ignore_nonexistent=True)
        subs_managefiles.director(self, 'rm', self.get_fluxcal_path().rstrip(
                                  '.MS') + '.Bscan', ignore_nonexistent=True)
        subs_managefiles.director(self, 'rm', self.get_fluxcal_path().rstrip(
                                 '.MS') + '.G1ap', ignore_nonexistent=True)
        subs_managefiles.director(self, 'rm',
                                  self.get_fluxcal_path().rstrip('.MS') + '.K',
                                  ignore_nonexistent=True)
        subs_managefiles.director(self, 'rm',
                                  self.get_fluxcal_path().rstrip('.MS') + '.Df',
                                  ignore_nonexistent=True)
        subs_managefiles.director(self, 'rm', self.get_polcal_path().rstrip(
                                  '.MS') + '.Kcross',
                                  ignore_nonexistent=True)
        subs_managefiles.director(self, 'rm',
                                  self.get_polcal_path().rstrip('.MS') + '.Xf',
                                  ignore_nonexistent=True)
        if do_clearcal or do_clearcal_fluxcal:
            # Run a clearcal on the fluxcal and revert to the last flagversion
            logger.info("Beam {}: Removing calibration from flux calibrator".format(self.beam))
            dataset = self.get_fluxcal_path()
            try:
                cc_dataset_clear = 'clearcal(vis = "' + dataset + '")'
                cc_dataset_resetflags = 'flagmanager(vis = "' + dataset + '", mode = "restore", versionname = "ccal")'
                cc_dataset_removeflagtable = 'flagmanager(vis = "' + dataset + '", mode = "delete", versionname = "ccal")'
                lib.run_casa([cc_dataset_clear, cc_dataset_resetflags, cc_dataset_removeflagtable], timeout=10000)
            except Exception:
                logger.error('Beam ' + self.beam + ': Calibration could not completely be removed from ' + dataset + '. Flags might also not have been properly reset!')
        if do_clearcal or do_clearcal_polcal:
            # Run a clearcal on the polcal and revert to the last flagversion
            logger.info("Beam {}: Removing calibration from polarisation calibrator".format(self.beam))
            dataset = self.get_polcal_path()
            try:
                cc_dataset_clear = 'clearcal(vis = "' + dataset + '")'
                cc_dataset_resetflags = 'flagmanager(vis = "' + dataset + '", mode = "restore", versionname = "ccal")'
                cc_dataset_removeflagtable = 'flagmanager(vis = "' + dataset + '", mode = "delete", versionname = "ccal")'
                lib.run_casa([cc_dataset_clear, cc_dataset_resetflags, cc_dataset_removeflagtable], timeout=10000)
            except Exception:
                logger.error('Beam ' + self.beam + ': Calibration could not completely be removed from ' + dataset + '. Flags might also not have been properly reset!')
        if do_clearcal or do_clearcal_target:
            # Run a clearcal on the target and revert to the last flagversion
            logger.info(
                "Beam {}: Removing calibration from target".format(self.beam))
            dataset = self.get_target_path()
            try:
                cc_dataset_clear = 'clearcal(vis = "' + dataset + '")'
                cc_dataset_resetflags = 'flagmanager(vis = "' + \
                    dataset + '", mode = "restore", versionname = "ccal")'
                cc_dataset_removeflagtable = 'flagmanager(vis = "' + \
                    dataset + '", mode = "delete", versionname = "ccal")'
                lib.run_casa([cc_dataset_clear, cc_dataset_resetflags,
                                cc_dataset_removeflagtable], timeout=10000)
            except Exception:
                logger.error('Beam ' + self.beam + ': Calibration could not completely be removed from ' +
                                dataset + '. Flags might also not have been properly reset!')
        # Remove the keywords in the parameter file
        if do_clearcal:
            logger.warning('Beam ' + self.beam + ': Deleting all parameter file entries for CROSSCAL module')
            if do_clearcal_fluxcal:
                subs_param.del_param(self, cbeam + '_fluxcal_model')
            if do_clearcal_polcal:
                subs_param.del_param(self, cbeam + '_polcal_model')
        else:
            logger.warning(
                'Beam ' + self.beam + ': Deleting all parameter file entries for CROSSCAL module except fluxcal and polcal model parameters')
        subs_param.del_param(self, cbeam + '_fluxcal_initialphase')
        subs_param.del_param(self, cbeam + '_fluxcal_globaldelay')
        subs_param.del_param(self, cbeam + '_fluxcal_bandpass')
        subs_param.del_param(self, cbeam + '_fluxcal_apgains')
        subs_param.del_param(self, cbeam + '_polcal_crosshanddelay')
        subs_param.del_param(self, cbeam + '_fluxcal_leakage')
        subs_param.del_param(self, cbeam + '_polcal_polarisationangle')
        subs_param.del_param(self, cbeam + '_fluxcal_transfer')
        subs_param.del_param(self, cbeam + '_polcal_transfer')
        subs_param.del_param(self, cbeam + '_targetbeams_transfer')
