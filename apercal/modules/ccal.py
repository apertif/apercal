import logging
import glob
import os
import numpy as np
import pandas as pd

import casacore.tables as pt

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs import msutils as subs_msutils
from apercal.subs import calmodels as subs_calmodels
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param

from apercal.libs import lib

logger = logging.getLogger(__name__)

gencal_cmd = 'gencal(vis="{vis}", caltable="{caltable}", caltype="{caltype}", infile="{infile}")'


class ccal(BaseModule):
    """
    Crosscal class to handle applying the calibrator gains and prepare the dataset for self-calibration.
    """

    module_name = 'CROSSCAL'

    crosscaldir = None
    crosscal_bandpass = None
    crosscal_delay = None
    crosscal_polarisation = None
    crosscal_transfer_to_target = None

    crosscal_tec = None
    crosscal_global_delay = None
    crosscal_gains = None
    crosscal_refant = None
    crosscal_transfer_to_target_targetbeams = None
    crosscal_polarisation_angle = None
    crosscal_crosshand_delay = None

    crosscal_leakage = None
    crosscal_transfer_to_cal = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)

    def go(self):
        """
        Executes the full cross calibration process in the following order.
        TEC
        bandpass
        gains
        global_delay
        crosshand_delay
        leakage
        polarisation_angle
        transfer_to_cal
        tranfer_to_target
        """
        logger.info("Starting CROSS CALIBRATION ")
        self.TEC()
        self.bandpass()
        self.gains()
        self.global_delay()
        self.crosshand_delay()
        self.leakage()
        self.polarisation_angle()
        self.transfer_to_cal()
        self.transfer_to_target()
        logger.info("CROSS CALIBRATION done ")

    def TEC(self):
        """
        Creates the TEC correction images and TEC calibration tables for all datasets
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the TEC correction step

        # Status of TEC correction table for the flux calibrator
        ccalfluxcalTEC = get_param_def(self, 'ccal_fluxcal_TEC', False)

        # Status of TEC correction table for the polarised calibrator
        ccalpolcalTEC = get_param_def(self, 'ccal_polcal_TEC', False)

        # Status of TEC correction table for the target beams
        ccaltargetbeamsTEC = get_param_def(self, 'ccal_targetbeams_TEC', np.full(self.NBEAMS, False))

        if self.crosscal_tec:
            logger.info('Calculating TEC corrections')

            # Create the TEC correction tables for the flux calibrator

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                fluxcal_tecim = self.get_fluxcal_path().rstrip('.MS') + '.tecim'
                if ccalfluxcalTEC or os.path.isdir(fluxcal_tecim):
                    logger.warning('TEC correction tables for flux calibrator were already generated')
                    ccalfluxcalTEC = True
                else:
                    cc_load_tec_maps = 'from recipes import tec_maps'
                    cc_fluxcal_TEC = 'tec_maps.create(vis="{}", doplot=False)'.format(self.get_fluxcal_path())
                    lib.run_casa([cc_load_tec_maps, cc_fluxcal_TEC])
                    fluxcal_infile = self.get_fluxcal_path().rstrip('.MS') + ".IGS_TEC.im"
                    # Check if the TEC corrections could be downloaded
                    if os.path.isdir(fluxcal_infile):
                        cc_load_tec_maps = 'from recipes import tec_maps'
                        cc_fluxcal_genTEC = gencal_cmd.format(vis=self.get_fluxcal_path(),
                                                              caltable=fluxcal_tecim,
                                                              caltype="tecim",
                                                              infile=fluxcal_infile)

                        lib.run_casa([cc_load_tec_maps, cc_fluxcal_genTEC])
                        # Check if the calibration table was created
                        if os.path.isdir(fluxcal_infile):
                            ccalfluxcalTEC = True
                        else:
                            logger.warning(
                                '# TEC calibration tables for flux calibrator could not be generated!')
                            ccalfluxcalTEC = False
                    else:
                        logger.warning('TEC images could not be generated for flux calibrator')
                        ccalfluxcalTEC = False
            else:
                error = 'Flux calibrator dataset not specified or dataset not available. ' \
                        'TEC corrections will not be used for flux calibrator'
                logger.error(error)
                raise RuntimeError(error)
                ccalfluxcalTEC = False

            # Create the TEC-correction tables for the polarised calibrator

            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                if ccalpolcalTEC or os.path.isdir(
                        self.get_polcal_path().rstrip('.MS') + '.tecim'):
                    logger.warning('TEC correction tables for polarised calibrator were already generated')
                    ccalpolcalTEC = True
                else:
                    cc_load_tec_maps = 'from recipes import tec_maps'
                    cc_polcal_TEC = 'tec_maps.create(vis = "' + self.get_polcal_path() + '", doplot = False)'
                    lib.run_casa([cc_load_tec_maps, cc_polcal_TEC])

                    polcal_infile = self.get_polcal_path().rstrip('.MS') + '.IGS_TEC.im'
                    # Check if the TEC corrections could be downloaded
                    if os.path.isdir(polcal_infile):
                        cc_load_tec_maps = 'from recipes import tec_maps'

                        cc_polcal_genTEC = gencal_cmd.format(vis=self.get_polcal_path(),
                                                             caltable=self.get_polcal_path().rstrip('.MS') + ".tecim",
                                                             caltype="tecim",
                                                             infile=polcal_infile)

                        lib.run_casa([cc_load_tec_maps, cc_polcal_genTEC])
                        if os.path.isdir(polcal_infile):  # Check if the calibration table was created
                            ccalpolcalTEC = True
                        else:
                            logger.warning('TEC calibration tables for polarised calibrator could not be generated!')
                            ccalpolcalTEC = False
                    else:
                        logger.warning('TEC images could not be generated for polarised calibrator')
                        ccalpolcalTEC = False
            else:
                logger.error('Polarised calibrator dataset not specified or dataset not available. '
                             'TEC corrections will not be used for polarised calibrator')
                ccalpolcalTEC = False

            # Create the TEC correction tables for the target beam datasets

            if self.target != '':
                for vis, beam in self.get_datasets():
                    if ccaltargetbeamsTEC[int(beam)] or os.path.isdir(self.get_target_path().rstrip('.MS') + '_B' +
                                                                      beam + '.MS.tecim'):
                        logger.info(
                            '# TEC correction tables for beam ' + beam + ' were already generated')
                        ccalpolcalTEC[int(beam)] = True
                    else:
                        cc_load_tec_maps = 'from recipes import tec_maps'
                        cc_targetbeam_TEC = 'tec_maps.create(vis = "' + vis + '", doplot = False)'
                        lib.run_casa([cc_load_tec_maps, cc_targetbeam_TEC])
                        # Check if the TEC corrections could be downloaded
                        target_infile = vis.rstrip('.MS') + '.IGS_TEC.im'
                        if os.path.isdir(target_infile):
                            cc_load_tec_maps = 'from recipes import tec_maps'

                            target_caltable = self.get_target_path().rstrip('.MS') + '_B' + beam + '.tecim'

                            cc_targetbeams_genTEC = gencal_cmd.format(vis=vis,
                                                                      calltable=target_caltable,
                                                                      caltype="tecim",
                                                                      infile=target_infile)

                            lib.run_casa([cc_load_tec_maps, cc_targetbeams_genTEC])
                            # Check if the calibration table was created
                            if os.path.isdir(target_caltable):
                                ccalpolcalTEC[int(beam)] = True
                            else:
                                logger.warning('TEC calibration tables for beam ' + beam + ' could not be generated!')
                                ccalpolcalTEC[int(beam)] = False
                        else:
                            logger.warning('TEC images could not be generated for target beam ' + beam)
                            ccaltargetbeamsTEC[int(beam)] = False
            else:
                logger.warning('No target dataset specified! Not using any TEC corrections for target beam datasets')

        # Save the derived parameters for the TEC corrections to the parameter file
        subs_param.add_param(self, 'ccal_fluxcal_TEC', ccalfluxcalTEC)
        subs_param.add_param(self, 'ccal_polcal_TEC', ccalpolcalTEC)
        subs_param.add_param(self, 'ccal_targetbeams_TEC', ccaltargetbeamsTEC)

    def bandpass(self):
        """
        Creates the bandpass correction table using the flux calibrator. Derives phase gains and looks up calibrator
        models on the fly
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the bandpass correction step

        # Status of the initial phase gains for the flux calibrator
        ccalfluxcalphgains = get_param_def(self, 'ccal_fluxcal_phgains', False)
        # Status of the bandpass table of the flux calibrator
        ccalfluxcalbandpass = get_param_def(self, 'ccal_fluxcal_bandpass', False)
        # Status of model of the flux calibrator
        ccalfluxcalmodel = get_param_def(self, 'ccal_fluxcal_model', False)

        if self.crosscal_bandpass:
            logger.info('Calculating bandpass corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                # Ingest the model of the flux calibrator into the MODEL column
                if ccalfluxcalmodel:
                    logger.info('Model was already ingested into the flux calibrator dataset!')
                else:
                    ms = self.get_fluxcal_path()  # Get the name of the calibrator
                    t = pt.table("%s::FIELD" % ms, ack=False)
                    srcname = t.getcol('NAME')[0]
                    av, fluxdensity, spix, reffreq, rotmeas = subs_calmodels.get_calparameters(srcname)
                    cc_fluxcal_model = 'setjy(vis = "' + self.get_fluxcal_path() + '", scalebychan = True, standard = "manual", fluxdensity = [' + \
                                       fluxdensity + '], spix = [' + spix + '], reffreq = "' + reffreq + \
                                       '", rotmeas = ' + rotmeas + ', usescratch = True)'
                    if av:
                        pass
                    else:
                        logger.warning('Calibrator model not in database. Using unpolarised calibrator model with a '
                                       'constant flux density of 1.0Jy!')
                    lib.run_casa([cc_fluxcal_model], log_output=True, timeout=3600)

                    # Check if model was ingested successfully
                    if subs_msutils.has_good_modeldata(self.get_fluxcal_path()):
                        ccalfluxcalmodel = True
                    else:
                        ccalfluxcalmodel = False
                        logger.warning(
                            '# Model not ingested properly. Flux scale and bandpass corrections will not be right!')

                # Create the initial phase correction tables for the flux calibrator
                fluxcal_G0ph = self.get_fluxcal_path().rstrip('.MS') + '.G0ph'
                if ccalfluxcalphgains or os.path.isdir(fluxcal_G0ph):
                    logger.info('Initial phase gain table for flux calibrator was already generated')
                    ccalfluxcalphgains = True
                else:
                    prevtables = '""'
                    interp = '""'
                    # Check for the TEC calibration table to apply on-the-fly
                    TECstatus = subs_param.get_param(self, 'ccal_fluxcal_TEC')
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.tecim', 'nearest')

                    gaincal_cmd = 'gaincal(vis="{vis}", caltable="{caltable}", gaintype="G", solint="int", ' \
                                  'refant="{refant}", calmode = "{calmode}", gaintable=[{gaintable}],' \
                                  'interp=[{interp}], smodel = [1,0,0,0])'

                    cc_fluxcal_ph = gaincal_cmd.format(vis=self.get_fluxcal_path(),
                                                       caltable=fluxcal_G0ph,
                                                       calmode="p",
                                                       refant=self.crosscal_refant,
                                                       gaintable=prevtables,
                                                       interp=interp)

                    lib.run_casa([cc_fluxcal_ph], timeout=3600)
                    if os.path.isdir(fluxcal_G0ph):  # Check if calibration table was created successfully
                        ccalfluxcalphgains = True
                    else:
                        ccalfluxcalphgains = False
                        error = 'Initial phase calibration table for flux calibrator was not created successfully!'
                        logger.error(error)
                        raise RuntimeError(error)

                    # Calculate the bandpass for the flux calibrator

                fluxcal_bscan = self.get_fluxcal_path().rstrip('.MS') + '.Bscan'
                if ccalfluxcalbandpass or os.path.isdir(fluxcal_bscan):
                    logger.info('Bandpass for flux calibrator was already derived successfully!')
                    ccalfluxcalbandpass = True
                else:
                    prevtables = '""'
                    interp = '""'
                    # Check for the TEC calibration table to apply on-the-fly
                    TECstatus = subs_param.get_param(self, 'ccal_fluxcal_TEC')
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.tecim"', '"nearest"')
                    phgainstatus = ccalfluxcalphgains
                    if phgainstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + fluxcal_G0ph + '"', '"nearest"')

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
                        error = 'Initial bandpass calibration table for flux calibrator was not created successfully!'
                        logger.error(error)
                        raise RuntimeError(error)
            else:
                logger.error('Flux calibrator dataset not specified or dataset not available. Bandpass corrections '
                             'are not available!')

        subs_param.add_param(self, 'ccal_fluxcal_phgains', ccalfluxcalphgains)
        subs_param.add_param(self, 'ccal_fluxcal_bandpass', ccalfluxcalbandpass)
        subs_param.add_param(self, 'ccal_fluxcal_model', ccalfluxcalmodel)

    def gains(self):
        """
        Calculates the amplitude and phase gains for the flux calibrator
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the gain correction step

        # Status of the amplitude and phase gains for the flux calibrator
        ccalfluxcalapgains = get_param_def(self, 'ccal_fluxcal_apgains', False)

        if self.crosscal_gains:
            logger.info('Calculating gain corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):

                fluxcal_g1ap = self.get_fluxcal_path().rstrip('.MS') + '.G1ap'

                # Create the amplitude and phase correction table for the flux calibrator
                if ccalfluxcalapgains or os.path.isdir(fluxcal_g1ap):
                    logger.info('Initial phase gain table for flux calibrator was already generated')
                    ccalfluxcalapgains = True
                else:
                    prevtables = '""'
                    interp = '""'
                    # Check for the TEC calibration table to apply on-the-fly
                    TECstatus = subs_param.get_param(self, 'ccal_fluxcal_TEC')
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.tecim"', '"nearest"')
                    # Check for the bandpass calibration table to apply on-the-fly
                    bandpassstatus = subs_param.get_param(self, 'ccal_fluxcal_bandpass')
                    if bandpassstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Bscan"', '"nearest"')
                    cc_fluxcal_apgain = 'gaincal(vis = "' + self.get_fluxcal_path() + '", caltable = "' + fluxcal_g1ap + '", gaintype = "G", solint = "int", refant = "' + self.crosscal_refant + '", calmode = "ap", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                    lib.run_casa([cc_fluxcal_apgain], timeout=3600)
                    # Check if gain table was created successfully
                    if os.path.isdir(fluxcal_g1ap):
                        ccalfluxcalapgains = True
                    else:
                        ccalfluxcalapgains = False
                        error = 'Gain calibration table for flux calibrator was not created successfully!'
                        logger.error(error)
                        raise RuntimeError(error)
            else:
                logger.error('Flux calibrator dataset not specified or dataset not available. Cross calibration '
                             'will probably not work!')

        subs_param.add_param(self, 'ccal_fluxcal_apgains', ccalfluxcalapgains)

    def global_delay(self):
        """
        Calculates the global delay corrections from the flux calibrator
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the global delay correction step

        ccalfluxcalglobaldelay = get_param_def(self, 'ccal_fluxcal_globaldelay',
                                               False)  # Status of the global delay corrections for the flux calibrator

        if self.crosscal_global_delay:
            logger.info('Calculating global delay corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):
                # Create the global delay correction table for the flux calibrator

                if ccalfluxcalglobaldelay or os.path.isdir(
                        self.get_fluxcal_path().rstrip('.MS') + '.K'):
                    logger.info('Global delay correction table for flux calibrator was already generated')
                    ccalfluxcalglobaldelay = True
                else:
                    prevtables = '""'
                    interp = '""'
                    # Check for the TEC calibration table to apply on-the-fly
                    TECstatus = subs_param.get_param(self, 'ccal_fluxcal_TEC')
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.tecim"', '"nearest"')

                    # Check for the bandpass calibration table to apply on-the-fly
                    bandpassstatus = subs_param.get_param(self, 'ccal_fluxcal_bandpass')
                    if bandpassstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Bscan"', '"nearest"')
                    apgainstatus = subs_param.get_param(self,
                                                        'ccal_fluxcal_apgains')  # Check for the gain calibration table to apply on-the-fly
                    if apgainstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.G1ap"', '"nearest"')
                    cc_fluxcal_globaldelay = 'gaincal(vis = "' + self.get_fluxcal_path() + '", caltable = "' + self.get_fluxcal_path().rstrip(
                        '.MS') + '.K", combine = "scan", gaintype = "K", solint = "inf", refant = "' + self.crosscal_refant + '", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                    lib.run_casa([cc_fluxcal_globaldelay], timeout=3600)
                    if os.path.isdir(self.get_fluxcal_path().rstrip(
                            '.MS') + '.K'):  # Check if gain table was created successfully
                        ccalfluxcalglobaldelay = True
                    else:
                        ccalfluxcalglobaldelay = False
                        logger.error(
                            '# Global delay correction table for flux calibrator was not created successfully!')
            else:
                logger.error(
                    '# Flux calibrator dataset not specified or dataset not available. Cross calibration will probably not work!')

        subs_param.add_param(self, 'ccal_fluxcal_globaldelay', ccalfluxcalglobaldelay)

    def crosshand_delay(self):
        """
        Calculates the cross-hand delay corrections from the polarised calibrator
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the cross hand delay correction step

        ccalpolcalmodel = get_param_def(self, 'ccal_polcal_model', False)  # Status of model of the polarised calibrator

        # Status of the cross hand delay calibration from the polarised calibrator
        ccalpolcalcrosshanddelay = get_param_def(self, 'ccal_polcal_crosshanddelay', False)

        if self.crosscal_crosshand_delay:
            logger.info('Calculating cross-hand delay corrections for polarised calibrator')

            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):

                # Ingest the model of the polarised calibrator into the MODEL column

                if ccalpolcalmodel:
                    logger.info('Model was already ingested into the polarised calibrator dataset!')
                else:
                    # Get the name of the calibrator
                    ms = self.get_polcal_path()
                    t = pt.table("%s::FIELD" % ms, ack=False)
                    srcname = t.getcol('NAME')[0]
                    av, fluxdensity, spix, reffreq, rotmeas = subs_calmodels.get_calparameters(srcname)
                    cc_polcal_model = 'setjy(vis = "' + self.get_polcal_path() + '", scalebychan = True, standard = "manual", fluxdensity = [' + \
                                      fluxdensity + '], spix = [' + spix + '], reffreq = "' + reffreq + \
                                      '", rotmeas = ' + rotmeas + ', usescratch = True)'
                    if av:
                        pass
                    else:
                        logger.warning(
                            '# Calibrator model not in database. Using unpolarised calibrator model with a constant flux density of 1.0Jy!')
                    lib.run_casa([cc_polcal_model], log_output=True, timeout=3600)

                    # Check if model was ingested successfully
                    if subs_msutils.has_good_modeldata(self.get_polcal_path()):
                        ccalpolcalmodel = True
                    else:
                        ccalpolcalmodel = False
                        logger.warning(
                            'Model not ingested properly. Polarisation calibration corrections will not be right!')

                # Create the cross hand delay correction table for the polarised calibrator

                if ccalpolcalcrosshanddelay or os.path.isdir(
                        self.get_polcal_path().rstrip('.MS') + '.Kcross'):
                    logger.info(
                        'Cross hand delay correction table for polarised calibrator was already generated')
                    ccalpolcalcrosshanddelay = True
                else:
                    prevtables = '""'
                    interp = '""'

                    # Check for the TEC calibration table to apply on-the-fly
                    TECstatus = subs_param.get_param(self, 'ccal_polcal_TEC')
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_polcal_path().rstrip(
                                                                            '.MS') + '.tecim"', '"nearest"')

                    # Check for the bandpass calibration table to apply on-the-fly
                    bandpassstatus = subs_param.get_param(self, 'ccal_fluxcal_bandpass')
                    if bandpassstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Bscan"', '"nearest"')

                    # Check for the gain calibration table to apply on-the-fly
                    apgainstatus = subs_param.get_param(self, 'ccal_fluxcal_apgains')
                    if apgainstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.G1ap"', '"nearest"')

                    # Check for the global delay table to apply on-the-fly
                    globaldelaystatus = subs_param.get_param(self, 'ccal_fluxcal_globaldelay')
                    if globaldelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.K"', '"nearest"')
                    cc_polcal_crosshanddelay = 'gaincal(vis = "' + self.get_polcal_path() + '", caltable = "' + self.get_polcal_path().rstrip(
                        '.MS') + '.Kcross", combine = "scan", gaintype = "KCROSS", solint = "inf", refant = "' + self.crosscal_refant + '", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                    lib.run_casa([cc_polcal_crosshanddelay], timeout=3600)
                    if os.path.isdir(self.get_polcal_path().rstrip(
                            '.MS') + '.Kcross'):  # Check if the cross hand delay table was created successfully
                        ccalpolcalcrosshanddelay = True
                    else:
                        ccalpolcalcrosshanddelay = False
                        logger.error('Cross hand delay correction table for polarised calibrator was '
                                     'not created successfully!')
            else:
                logger.error('Polarised calibrator dataset not specified or dataset not available. Polarisation '
                             'calibration will probably not work!')

        subs_param.add_param(self, 'ccal_polcal_model', ccalpolcalmodel)
        subs_param.add_param(self, 'ccal_polcal_crosshanddelay', ccalpolcalcrosshanddelay)

    def leakage(self):
        """
        Calculates the leakage corrections from the flux calibrator
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the leakage correction step

        ccalfluxcalleakage = get_param_def(self, 'ccal_fluxcal_leakage',
                                           False)  # Status of the leakage corrections for the flux calibrator

        if self.crosscal_leakage:
            logger.info('Calculating leakage corrections for flux calibrator')

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):

                # Create the leakage correction table for the flux calibrator

                if ccalfluxcalleakage or os.path.isdir(
                        self.get_fluxcal_path().rstrip('.MS') + '.Df'):
                    logger.info('Leakage correction table for flux calibrator was already generated')
                    ccalfluxcalleakage = True
                else:
                    prevtables = '""'
                    interp = '""'
                    TECstatus = subs_param.get_param(self,
                                                     'ccal_fluxcal_TEC')  # Check for the TEC calibration table to apply on-the-fly
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.tecim"', '"nearest"')
                    bandpassstatus = subs_param.get_param(self,
                                                          'ccal_fluxcal_bandpass')  # Check for the bandpass calibration table to apply on-the-fly
                    if bandpassstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Bscan"', '"nearest"')
                    apgainstatus = subs_param.get_param(self,
                                                        'ccal_fluxcal_apgains')  # Check for the gain calibration table to apply on-the-fly
                    if apgainstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.G1ap"', '"nearest"')
                    globaldelaystatus = subs_param.get_param(self,
                                                             'ccal_fluxcal_globaldelay')  # Check for the global delay table to apply on-the-fly
                    if globaldelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.K"', '"nearest"')
                    crosshanddelaystatus = subs_param.get_param(self,
                                                                'ccal_polcal_crosshanddelay')  # Check for the crosshand delay table to apply on-the-fly
                    if crosshanddelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_polcal_path().rstrip(
                                                                            '.MS') + '.Kcross"', '"nearest"')
                    cc_fluxcal_leakage = 'polcal(vis = "' + self.get_fluxcal_path() + '", caltable = "' + self.get_fluxcal_path().rstrip(
                        '.MS') + '.Df", combine = "scan", poltype = "Df", solint = "inf", refant = "' + self.crosscal_refant + '", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                    lib.run_casa([cc_fluxcal_leakage], timeout=3600)
                    if os.path.isdir(self.get_fluxcal_path().rstrip(
                            '.MS') + '.Df'):  # Check if gain table was created successfully
                        ccalfluxcalleakage = True
                    else:
                        ccalfluxcalleakage = False
                        logger.error(
                            '# Leakage correction table for flux calibrator was not created successfully!')
            else:
                logger.error(
                    '# Flux calibrator dataset not specified or dataset not available. Cross calibration will probably not work!')

        subs_param.add_param(self, 'ccal_fluxcal_leakage', ccalfluxcalleakage)

    def polarisation_angle(self):
        """
        Calculates the polarisation angle corrections from the polarised calibrator
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the polarisation angle correction step

        ccalpolcalpolarisationangle = get_param_def(self, 'ccal_polcal_polarisationangle',
                                                    False)  # Status of the polarisation angle corrections for the polarised calibrator

        if not subs_calmodels.is_polarised(self.polcal) and self.crosscal_polarisation_angle:
            self.crosscal_polarisation_angle = False
            logger.warning("Changing crosscal_polarisation angle to false because " + self.polcal +
                           "is unpolarised.")

        if self.crosscal_polarisation_angle:
            logger.info('Calculating polarisation angle corrections for polarised calibrator')

            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):
                # Create the polarisation angle correction table for the polarised calibrator

                if ccalpolcalpolarisationangle or os.path.isdir(
                        self.get_polcal_path().rstrip('.MS') + '.Xf'):
                    logger.info(
                        '# Polarisation angle correction table for polarised calibrator was already generated')
                    ccalpolcalpolarisationangle = True
                else:
                    prevtables = '""'
                    interp = '""'
                    # Check for the TEC calibration table to apply on-the-fly
                    TECstatus = subs_param.get_param(self, 'ccal_fluxcal_TEC')
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.tecim"', '"nearest"')

                    # Check for the bandpass calibration table to apply on-the-fly
                    bandpassstatus = subs_param.get_param(self, 'ccal_fluxcal_bandpass')
                    if bandpassstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Bscan"', '"nearest"')

                    # Check for the gain calibration table to apply on-the-fly
                    apgainstatus = subs_param.get_param(self, 'ccal_fluxcal_apgains')
                    if apgainstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.G1ap"', '"nearest"')

                    # Check for the global delay table to apply on-the-fly
                    globaldelaystatus = subs_param.get_param(self, 'ccal_fluxcal_globaldelay')
                    if globaldelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.K"', '"nearest"')

                    # Check for the crosshand delay table to apply on-the-fly
                    crosshanddelaystatus = subs_param.get_param(self, 'ccal_polcal_crosshanddelay')
                    if crosshanddelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_polcal_path().rstrip(
                                                                            '.MS') + '.Kcross"', '"nearest"')

                    # Check for the leakage table to apply on-the-fly
                    leakagestatus = subs_param.get_param(self, 'ccal_fluxcal_leakage')
                    if leakagestatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Df"', '"nearest"')
                    cc_polcal_polarisationangle = 'polcal(vis = "' + self.get_polcal_path() + '", caltable = "' + self.get_polcal_path().rstrip(
                        '.MS') + '.Xf", combine = "scan", poltype = "Xf", solint = "inf", refant = "' + self.crosscal_refant + '", gaintable = [' + prevtables + '], interp = [' + interp + '])'
                    lib.run_casa([cc_polcal_polarisationangle], timeout=3600)
                    if os.path.isdir(self.get_polcal_path().rstrip(
                            '.MS') + '.Xf'):  # Check if gain table was created successfully
                        ccalpolcalpolarisationangle = True
                    else:
                        ccalpolcalpolarisationangle = False
                        logger.error('Polarisation angle correction table for polarised calibrator '
                                     'was not created successfully!')
            else:
                msg = 'Polarised calibrator dataset not specified or dataset not available.' + \
                      'Cross calibration will probably not work!'
                logger.error(msg)

        subs_param.add_param(self, 'ccal_polcal_polarisationangle', ccalpolcalpolarisationangle)

    def transfer_to_cal(self):
        """
        Applies the correction tables to the calibrators
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the transfer step

        ccalfluxcaltransfer = get_param_def(self, 'ccal_fluxcal_transfer',
                                            False)  # Status of the solution transfer for the flux calibrator
        ccalpolcaltransfer = get_param_def(self, 'ccal_polcal_transfer',
                                           False)  # Status of the solution transfer for the polarised calibrator

        if self.crosscal_transfer_to_cal:
            logger.info('Applying solutions to calibrators')

            # Apply solutions to the flux calibrator

            if self.fluxcal != '' and os.path.isdir(self.get_fluxcal_path()):

                if ccalfluxcaltransfer:
                    logger.info('Solution tables were already applied to flux calibrator')
                    ccalfluxcaltransfer = True
                else:
                    # Check which calibration tables are available for the flux calibrator
                    prevtables = '""'
                    interp = '""'
                    TECstatus = subs_param.get_param(self,
                                                     'ccal_fluxcal_TEC')  # Check for the TEC calibration table to apply on-the-fly
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.tecim"', '"nearest"')
                    bandpassstatus = subs_param.get_param(self,
                                                          'ccal_fluxcal_bandpass')  # Check for the bandpass calibration table to apply
                    if bandpassstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Bscan"', '"nearest"')
                    apgainstatus = subs_param.get_param(self,
                                                        'ccal_fluxcal_apgains')  # Check for the gain calibration table to apply
                    if apgainstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.G1ap"', '"nearest"')
                    globaldelaystatus = subs_param.get_param(self,
                                                             'ccal_fluxcal_globaldelay')  # Check for the global delay table to apply
                    if globaldelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.K"', '"nearest"')
                    crosshanddelaystatus = subs_param.get_param(self,
                                                                'ccal_polcal_crosshanddelay')  # Check for the crosshand delay table to apply
                    if crosshanddelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_polcal_path().rstrip(
                                                                            '.MS') + '.Kcross"', '"nearest"')
                    leakagestatus = subs_param.get_param(self,
                                                         'ccal_fluxcal_leakage')  # Check for the leakage table to apply
                    if leakagestatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Df"', '"nearest"')
                    polarisationanglestatus = subs_param.get_param(self,
                                                                   'ccal_polcal_polarisationangle')  # Check for the polarisation angle corrections to apply
                    if polarisationanglestatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_polcal_path().rstrip(
                                                                            '.MS') + '.Xf"', '"nearest"')
                    cc_fluxcal_saveflags = 'flagmanager(vis = "' + self.get_fluxcal_path() + '", mode = "save", versionname = "ccal")'
                    cc_fluxcal_apply = 'applycal(vis = "' + self.get_fluxcal_path() + '", gaintable = [' + prevtables + '], interp = [' + interp + '], parang = False, flagbackup = False)'
                    lib.run_casa([cc_fluxcal_saveflags, cc_fluxcal_apply], timeout=3600)
                    if subs_msutils.has_correcteddata(self.get_fluxcal_path()):
                        ccalfluxcaltransfer = True
                    else:
                        ccalfluxcaltransfer = False
                        logger.warning('Corrected visibilities were not written to flux calibrator dataset !')
            else:
                logger.error(
                    '# Flux calibrator dataset not specified or dataset not available. Application of cross calibration solutions not possible!')
                ccalfluxcaltransfer = False

            # Apply solutions to the polarised calibrator

            if self.polcal != '' and os.path.isdir(self.get_polcal_path()):

                if ccalpolcaltransfer:
                    logger.info('Solution tables were already applied to the polarised calibrator')
                    ccalpolcaltransfer = True
                else:
                    # Check which calibration tables are available for the polarised calibrator
                    prevtables = '""'
                    interp = '""'
                    TECstatus = subs_param.get_param(self,
                                                     'ccal_polcal_TEC')  # Check for the TEC calibration table to apply on-the-fly
                    if TECstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_polcal_path().rstrip(
                                                                            '.MS') + '.tecim"', '"nearest"')
                    bandpassstatus = subs_param.get_param(self,
                                                          'ccal_fluxcal_bandpass')  # Check for the bandpass calibration table to apply
                    if bandpassstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Bscan"', '"nearest"')
                    apgainstatus = subs_param.get_param(self,
                                                        'ccal_fluxcal_apgains')  # Check for the gain calibration table to apply
                    if apgainstatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.G1ap"', '"nearest"')
                    globaldelaystatus = subs_param.get_param(self,
                                                             'ccal_fluxcal_globaldelay')  # Check for the global delay table to apply
                    if globaldelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.K"', '"nearest"')
                    crosshanddelaystatus = subs_param.get_param(self,
                                                                'ccal_polcal_crosshanddelay')  # Check for the crosshand delay table to apply
                    if crosshanddelaystatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_polcal_path().rstrip(
                                                                            '.MS') + '.Kcross"', '"nearest"')
                    leakagestatus = subs_param.get_param(self,
                                                         'ccal_fluxcal_leakage')  # Check for the leakage table to apply
                    if leakagestatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_fluxcal_path().rstrip(
                                                                            '.MS') + '.Df"', '"nearest"')
                    polarisationanglestatus = subs_param.get_param(self,
                                                                   'ccal_polcal_polarisationangle')  # Check for the polarisation angle corrections to apply
                    if polarisationanglestatus:
                        prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                        '"' + self.get_polcal_path().rstrip(
                                                                            '.MS') + '.Xf"', '"nearest"')
                    cc_polcal_saveflags = 'flagmanager(vis = "' + self.get_polcal_path() + '", mode = "save", versionname = "ccal")'
                    cc_polcal_apply = 'applycal(vis = "' + self.get_polcal_path() + '", gaintable = [' + prevtables + '], interp = [' + interp + '], parang = False, flagbackup = False)'
                    lib.run_casa([cc_polcal_saveflags, cc_polcal_apply], timeout=3600)
                    if subs_msutils.has_correcteddata(self.get_polcal_path()):
                        ccalpolcaltransfer = True
                    else:
                        ccalpolcaltransfer = False
                        logger.warning(
                            '# Corrected visibilities were not written to polarised calibrator dataset !')
            else:
                logger.error(
                    '# Polarised calibrator dataset not specified or dataset not available. Application of cross calibration solutions not possible!')
                ccalpolcaltransfer = False

        subs_param.add_param(self, 'ccal_fluxcal_transfer', ccalfluxcaltransfer)
        subs_param.add_param(self, 'ccal_polcal_transfer', ccalpolcaltransfer)

    def transfer_to_target(self):
        """
        Applies the correction tables to the target beams
        """

        subs_setinit.setinitdirs(self)
        subs_managefiles.director(self, 'ch', self.get_rawsubdir_path())

        # Create the parameters for the parameter file for the transfer step

        # Status of the solution transfer for the target beams
        ccaltargetbeamstransfer = get_param_def(self, 'ccal_targetbeams_transfer', np.full(self.NBEAMS, False))

        if self.crosscal_transfer_to_target:
            logger.info('Applying solutions to target beams')

            # Apply solutions to the target beams

            if self.target != '':

                # Check which beams are requested for applying solutions

                if self.crosscal_transfer_to_target_targetbeams == 'all':  # if all beams are requested
                    datasets = self.get_datasets()
                else:  # if only certain beams are requested
                    beams = self.crosscal_transfer_to_target_targetbeams.split(",")
                    datasets = self.get_datasets(beams=beams)

                for vis, beam in datasets:
                    if ccaltargetbeamstransfer[int(beam)]:
                        logger.info('Solutions were already applied to beam ' + beam + '')
                        ccaltargetbeamstransfer[int(beam)] = True
                    else:
                        # Check which calibration tables are available for each beam
                        prevtables = '""'
                        interp = '""'

                        # Check for the TEC calibration table to apply on-the-fly
                        TECstatus = subs_param.get_param(self, 'ccal_targetbeams_TEC')
                        if TECstatus[int(beam)]:
                            # fix this for right location of TEC table
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + vis.rstrip('.MS') + '.tecim"',
                                                                            '"nearest"')

                        bandpassstatus = subs_param.get_param(self,
                                                              'ccal_fluxcal_bandpass')  # Check for the bandpass calibration table to apply
                        if bandpassstatus:
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + self.get_fluxcal_path().rstrip(
                                                                                '.MS') + '.Bscan"', '"nearest"')

                        apgainstatus = subs_param.get_param(self,
                                                            'ccal_fluxcal_apgains')  # Check for the gain calibration table to apply
                        if apgainstatus:
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + self.get_fluxcal_path().rstrip(
                                                                                '.MS') + '.G1ap"', '"nearest"')

                        # Check for the global delay table to apply
                        globaldelaystatus = subs_param.get_param(self, 'ccal_fluxcal_globaldelay')
                        if globaldelaystatus:
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + self.get_fluxcal_path().rstrip(
                                                                                '.MS') + '.K"', '"nearest"')

                        # Check for the crosshand delay table to apply
                        crosshanddelaystatus = subs_param.get_param(self, 'ccal_polcal_crosshanddelay')
                        if crosshanddelaystatus:
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + self.get_polcal_path().rstrip(
                                                                                '.MS') + '.Kcross"', '"nearest"')

                        # Check for the leakage table to apply
                        leakagestatus = subs_param.get_param(self, 'ccal_fluxcal_leakage')
                        if leakagestatus:
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + self.get_fluxcal_path().rstrip(
                                                                                '.MS') + '.Df"', '"nearest"')

                        # Check for the polarisation angle corrections to apply
                        polarisationanglestatus = subs_param.get_param(self, 'ccal_polcal_polarisationangle')
                        if polarisationanglestatus:
                            prevtables, interp = subs_msutils.add_caltables(prevtables, interp,
                                                                            '"' + self.get_polcal_path().rstrip(
                                                                                '.MS') + '.Xf"', '"nearest"')

                        # Execute the CASA command to apply the solutions
                        logger.debug('Applying solutions to beam ' + beam + '')
                        cc_targetbeams_saveflags = 'flagmanager(vis = "' + vis + '", mode = "save", versionname = "ccal")'  # Save the flags before applying solutions
                        cc_targetbeams_apply = 'applycal(vis = "' + vis + '", gaintable = [' + prevtables + '], interp = [' + interp + '], parang = False, flagbackup = False)'
                        lib.run_casa([cc_targetbeams_saveflags, cc_targetbeams_apply], timeout=10000)
                        if subs_msutils.has_correcteddata(vis):
                            ccaltargetbeamstransfer[int(beam)] = True
                        else:
                            ccaltargetbeamstransfer[int(beam)] = False
                            logger.warning(
                                '# Corrected visibilities were not written to dataset for beam ' + vis.split('/')[
                                    -3] + ' !')
            else:
                logger.warning('No target dataset specified! Not applying solutions to target datasets')

        subs_param.add_param(self, 'ccal_targetbeams_transfer', ccaltargetbeamstransfer)

    def plot_bandpass(self):
        """
        Creates a plot of the bandpass calibration for each antenna. The two different feeds are plotted in the same plots
        """
        if os.path.isfile(self.get_fluxcal_path().rstrip('.MS') + '.Bscan.png'):
            subs_managefiles.director(self, 'rm',
                                      self.get_fluxcal_path().rstrip(
                                          '.MS') + '.Bscan.png')
        cc_plot_bandpass = 'plotcal(caltable = "' + self.get_fluxcal_path().rstrip('.MS') + \
                           '.Bscan", xaxis = "freq", yaxis="amp", subplot=431, iteration="antenna", ' \
                           'plotsymbol=".", markersize=1.0, fontsize=5.0, showgui=False, figfile="' + \
                           self.get_fluxcal_path().rstrip('.MS') + '.Bscan.png")'
        lib.run_casa([cc_plot_bandpass], timeout=10000)
        return self.get_fluxcal_path().rstrip('.MS') + '.Bscan.png'

    def plot_gains_amp(self):
        """
        Creates a plot of the amplitude calibrator gains
        """
        if os.path.isfile(
                self.get_fluxcal_path().rstrip('.MS') + '.G1ap_amp.png'):
            subs_managefiles.director(self, 'rm',
                                      self.get_fluxcal_path().rstrip(
                                          '.MS') + '.G1ap_amp.png')
        cc_plot_gains_amp = 'plotcal(caltable = "' + self.get_fluxcal_path().rstrip('.MS') + \
                            '.G1ap", xaxis = "time", yaxis="amp", subplot=431, iteration="antenna", ' \
                            'plotsymbol=".", markersize=1.0, fontsize=5.0, showgui=False, figfile="' + \
                            self.get_fluxcal_path().rstrip('.MS') + '.G1ap_amp.png")'
        lib.run_casa([cc_plot_gains_amp], timeout=10000)
        return self.get_fluxcal_path().rstrip('.MS') + '.G1ap_amp.png'

    def plot_gains_ph(self):
        """
        Creates a plot of the amplitude calibrator gains
        """
        if os.path.isfile(
                self.get_fluxcal_path().rstrip('.MS') + '.G1ap_ph.png'):
            subs_managefiles.director(self, 'rm',
                                      self.get_fluxcal_path().rstrip(
                                          '.MS') + '.G1ap_ph.png')
        cc_plot_gains_ph = 'plotcal(caltable = "' + self.get_fluxcal_path().rstrip(
            '.MS') + '.G1ap", xaxis = "time", yaxis="phase", subplot=431, iteration="antenna", plotrange=[-1,-1,-180,180], plotsymbol=".", markersize=1.0, fontsize=5.0, showgui=False, figfile="' + self.get_fluxcal_path().rstrip(
            '.MS') + '.G1ap_ph.png")'
        lib.run_casa([cc_plot_gains_ph], timeout=10000)
        return self.get_fluxcal_path().rstrip('.MS') + '.G1ap_ph.png'

    def plot_globaldelay(self):
        """
        Creates a plot of the global delay corrections
        """
        if os.path.isfile(self.get_fluxcal_path().rstrip('.MS') + '.K.png'):
            subs_managefiles.director(self, 'rm',
                                      self.get_fluxcal_path().rstrip(
                                          '.MS') + '.K.png')
        cc_plot_globaldelay = 'plotcal(caltable = "' + self.get_fluxcal_path().rstrip(
            '.MS') + '.K", xaxis = "antenna", yaxis="delay", plotsymbol="o", markersize=4.0, fontsize=10.0, showgui=False, figfile="' + self.get_fluxcal_path().rstrip(
            '.MS') + '.K.png")'
        lib.run_casa([cc_plot_globaldelay], timeout=10000)
        return self.get_fluxcal_path().rstrip('.MS') + '.K.png'

    def plot_crosshanddelay(self):
        """
        Creates a plot of the crosshand delay corrections
        """
        if os.path.isfile(self.get_polcal_path().rstrip('.MS') + '.Kcross.png'):
            subs_managefiles.director(self, 'rm', self.get_polcal_path().rstrip(
                '.MS') + '.Kcross.png')
        cc_plot_crosshanddelay = 'plotcal(caltable = "' + self.get_polcal_path().rstrip(
            '.MS') + '.Kcross", xaxis = "antenna", yaxis="delay", plotsymbol="o", markersize=4.0, fontsize=10.0, showgui=False, figfile="' + self.get_polcal_path().rstrip(
            '.MS') + '.Kcross.png")'
        lib.run_casa([cc_plot_crosshanddelay], timeout=10000)
        return self.get_polcal_path().rstrip('.MS') + '.Kcross.png'

    def plot_leakage_amp(self):
        """
        Creates a plot of the amplitude leakage corrections for each antenna
        """
        if os.path.isfile(
                self.get_fluxcal_path().rstrip('.MS') + '.Df_amp.png'):
            subs_managefiles.director(self, 'rm',
                                      self.get_fluxcal_path().rstrip(
                                          '.MS') + '.Df_amp.png')
        cc_plot_leakage_amp = 'plotcal(caltable = "' + self.get_fluxcal_path().rstrip(
            '.MS') + '.Df", xaxis = "freq", yaxis="amp", subplot=431, iteration="antenna", plotsymbol=".", markersize=1.0, fontsize=5.0, showgui=False, figfile="' + self.get_fluxcal_path().rstrip(
            '.MS') + '.Df_amp.png")'
        lib.run_casa([cc_plot_leakage_amp], timeout=10000)
        return self.get_fluxcal_path().rstrip('.MS') + '.Df_amp.png'

    def plot_leakage_ph(self):
        """
        Creates a plot of the phase leakage corrections for each antenna
        """
        if os.path.isfile(self.get_fluxcal_path().rstrip('.MS') + '.Df_ph.png'):
            subs_managefiles.director(self, 'rm',
                                      self.get_fluxcal_path().rstrip(
                                          '.MS') + '.Df_ph.png')
        cc_plot_leakage_ph = 'plotcal(caltable = "' + self.get_fluxcal_path().rstrip(
            '.MS') + '.Df", xaxis = "freq", yaxis="phase", subplot=431, iteration="antenna", plotrange=[-1,-1,-180,180], plotsymbol=".", markersize=1.0, fontsize=5.0, showgui=False, figfile="' + self.get_fluxcal_path().rstrip(
            '.MS') + '.Df_ph.png")'
        lib.run_casa([cc_plot_leakage_ph], timeout=10000)
        return self.get_fluxcal_path().rstrip('.MS') + '.Df_ph.png'

    def plot_polarisationangle(self):
        """
        Creates a plot of the polarisation angle corrections
        """
        if os.path.isfile(self.get_polcal_path().rstrip('.MS') + '.Xf.png'):
            subs_managefiles.director(self, 'rm', self.get_polcal_path().rstrip(
                '.MS') + '.Xf.png')
        cc_plot_polarisationangle = 'plotcal(caltable = "' + self.get_polcal_path().rstrip(
            '.MS') + '.Xf", xaxis = "freq", yaxis="phase", subplot=431, iteration="antenna", plotrange=[-1,-1,-180,180], plotsymbol=".", markersize=1.0, fontsize=5.0, showgui=False, figfile="' + self.get_polcal_path().rstrip(
            '.MS') + '.Xf.png")'
        lib.run_casa([cc_plot_polarisationangle], timeout=10000)
        return self.get_polcal_path().rstrip('.MS') + '.Xf.png'

    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during CROSSCAL. No detailed
        summary is available for CROSSCAL.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in
        the notebook
        """

        # Load the parameters from the parameter file

        FTEC = subs_param.get_param(self, 'ccal_fluxcal_TEC')
        PTEC = subs_param.get_param(self, 'ccal_polcal_TEC')
        TTEC = subs_param.get_param(self, 'ccal_targetbeams_TEC')
        FBP = subs_param.get_param(self, 'ccal_fluxcal_bandpass')
        FMOD = subs_param.get_param(self, 'ccal_fluxcal_model')
        FG = subs_param.get_param(self, 'ccal_fluxcal_apgains')
        FGD = subs_param.get_param(self, 'ccal_fluxcal_globaldelay')
        PMOD = subs_param.get_param(self, 'ccal_polcal_model')
        PCD = subs_param.get_param(self, 'ccal_polcal_crosshanddelay')
        FL = subs_param.get_param(self, 'ccal_fluxcal_leakage')
        PPA = subs_param.get_param(self, 'ccal_polcal_polarisationangle')
        FT = subs_param.get_param(self, 'ccal_fluxcal_transfer')
        PT = subs_param.get_param(self, 'ccal_polcal_transfer')
        TT = subs_param.get_param(self, 'ccal_targetbeams_transfer')

        # Create the data frame

        beam_range = range(self.NBEAMS)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = ['Flux calibrator (' + self.fluxcal[:-3] + ')',
                           'Polarised calibrator (' + self.polcal[:-3] + ')'] + dataset_beams

        all_TEC = np.full(39, False)
        all_TEC[0] = FTEC
        all_TEC[1] = PTEC
        all_TEC[2:] = TTEC

        all_BP = np.full(39, '   NA')
        all_BP[0] = str(FBP)

        all_MOD = np.full(39, '   NA')
        all_MOD[0] = str(FMOD)
        all_MOD[1] = str(PMOD)

        all_G = np.full(39, '   NA')
        all_G[0] = str(FG)

        all_GD = np.full(39, '   NA')
        all_GD[0] = str(FGD)

        all_CD = np.full(39, '   NA')
        all_CD[1] = str(PCD)

        all_L = np.full(39, '   NA')
        all_L[0] = str(FL)

        all_PA = np.full(39, '   NA')
        all_PA[1] = str(PPA)

        all_T = np.full(39, False)
        all_T[0] = FT
        all_T[1] = PT
        all_T[2:] = TT

        df_tec = pd.DataFrame(np.ndarray.flatten(all_TEC), index=dataset_indices, columns=['TEC'])
        df_bp = pd.DataFrame(np.ndarray.flatten(all_BP), index=dataset_indices, columns=['Bandpass'])
        df_mod = pd.DataFrame(np.ndarray.flatten(all_MOD), index=dataset_indices, columns=['Model'])
        df_g = pd.DataFrame(np.ndarray.flatten(all_G), index=dataset_indices, columns=['Gains'])
        df_gd = pd.DataFrame(np.ndarray.flatten(all_GD), index=dataset_indices, columns=['Global Delay'])
        df_cd = pd.DataFrame(np.ndarray.flatten(all_CD), index=dataset_indices, columns=['Cross Hand Delay'])
        df_l = pd.DataFrame(np.ndarray.flatten(all_L), index=dataset_indices, columns=['Leakage'])
        df_pa = pd.DataFrame(np.ndarray.flatten(all_PA), index=dataset_indices, columns=['Polarisation Angle'])
        df_t = pd.DataFrame(np.ndarray.flatten(all_T), index=dataset_indices, columns=['Transfer'])

        df = pd.concat([df_tec, df_bp, df_mod, df_g, df_gd, df_cd, df_l, df_pa, df_t], axis=1)

        return df

    def reset(self):
        """
        Function to reset the current step and clear all calibration from datasets as well as all calibration tables.
        """
        subs_setinit.setinitdirs(self)
        logger.warning('Resetting flags and data values to before cross-calibration step')
        # Remove the calibration tables
        # for all beams and calibrators
        subs_managefiles.director(self, 'rm', self.get_rawsubdir_path() + '/*.tecim',
                                  ignore_nonexistent=True)
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
        # Run a clearcal on all datasets and revert to the last flagversion
        targetdatasets = glob.glob(self.get_target_path('[0-9][0-9]'))
        targetdatasets.append(self.get_fluxcal_path())
        targetdatasets.append(self.get_polcal_path())
        datasets_toclear = sorted(targetdatasets)
        for dataset in datasets_toclear:
            try:
                cc_dataset_clear = 'clearcal(vis = "' + dataset + '")'
                cc_dataset_resetflags = 'flagmanager(vis = "' + dataset + '", mode = "restore", versionname = "ccal")'
                cc_dataset_removeflagtable = 'flagmanager(vis = "' + dataset + '", mode = "delete", versionname = "ccal")'
                lib.run_casa([cc_dataset_clear, cc_dataset_resetflags, cc_dataset_removeflagtable], timeout=10000)
            except Exception:
                logger.error('Calibration could not completely be removed from ' + dataset + '. Flags might also not have be properly reset!')
        # Remove the keywords in the parameter file
        logger.warning('Deleting all parameter file entries for CROSSCAL module')
        subs_param.del_param(self, 'ccal_fluxcal_TEC')
        subs_param.del_param(self, 'ccal_polcal_TEC')
        subs_param.del_param(self, 'ccal_targetbeams_TEC')
        subs_param.del_param(self, 'ccal_fluxcal_phgains')
        subs_param.del_param(self, 'ccal_fluxcal_bandpass')
        subs_param.del_param(self, 'ccal_fluxcal_model')
        subs_param.del_param(self, 'ccal_fluxcal_apgains')
        subs_param.del_param(self, 'ccal_fluxcal_globaldelay')
        subs_param.del_param(self, 'ccal_polcal_model')
        subs_param.del_param(self, 'ccal_polcal_crosshanddelay')
        subs_param.del_param(self, 'ccal_fluxcal_leakage')
        subs_param.del_param(self, 'ccal_polcal_polarisationangle')
        subs_param.del_param(self, 'ccal_fluxcal_transfer')
        subs_param.del_param(self, 'ccal_polcal_transfer')
        subs_param.del_param(self, 'ccal_targetbeams_transfer')
