import logging

import aipy
import numpy as np
import pandas as pd
import os

from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles

from apercal.libs.calculations import calc_scal_interval

from apercal.libs import lib
from apercal.subs import lsm
from apercal.subs import imstats
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.subs import masking
from apercal.subs import qa

from apercal.exceptions import ApercalException

logger = logging.getLogger(__name__)


class scal(BaseModule):
    """
    Selfcal class to do the self-calibration on a dataset.
    """
    module_name = 'SCAL'

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

    selfcal_image_imsize = None
    selfcal_image_cellsize = None
    selfcal_refant = None
    selfcal_average = None
    selfcal_flagline = None
    selfcal_flagline_sigma = None
    selfcal_parametric = None
    selfcal_parametric_skymodel_radius = None
    selfcal_parametric_skymodel_cutoff = None
    selfcal_parametric_skymodel_distance = None
    selfcal_parametric_solint = None
    selfcal_parametric_uvmin = None
    selfcal_parametric_uvmax = None
    selfcal_parametric_amp = None
    selfcal_parametric_nfbin = None
    selfcal_phase = None
    selfcal_phase_majorcycle = None
    selfcal_phase_majorcycle_function = None
    selfcal_phase_minorcycle = None
    selfcal_phase_minorcycle_function = None
    selfcal_phase_c0 = None
    selfcal_phase_c1 = None
    selfcal_phase_minorcycle0_dr = None
    selfcal_phase_drinit = None
    selfcal_phase_dr0 = None
    selfcal_phase_mindr = None
    selfcal_phase_nsigma = None
    selfcal_phase_uvmin = None
    selfcal_phase_uvmax = None
    selfcal_phase_solint = None
    selfcal_phase_nfbin = None
    selfcal_phase_gaussianity = None
    selfcal_amp = None
    selfcal_amp_auto_limit = None
    selfcal_amp_nfbin = None

    selfcaldir = None
    crosscaldir = None
    linedir = None

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)


    def go(self):
        """
        Executes the whole self-calibration process in the following order:
        averagedata
        flagline
        parametric
        phase
        amp
        """
        logger.info("Starting SELF CALIBRATION")
        self.averagedata()
        self.flagline()
        self.parametric()
        self.phase()
        self.amp()
        logger.info("SELF CALIBRATION done")


    def averagedata(self):
        """
        Averages the data to one channel per subband for self-calibration
        """
        subs_setinit.setinitdirs(self)

        beam = 'selfcal_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the averaging

        # Status of the averaging
        selfcaltargetbeamsaverage = get_param_def(self, beam + '_targetbeams_average', False)

        if self.selfcal_average:
            if not selfcaltargetbeamsaverage:
                subs_setinit.setinitdirs(self)
                subs_setinit.setdatasetnamestomiriad(self)
                subs_managefiles.director(self, 'ch', self.selfcaldir)
                logger.info('Beam ' + self.beam + ': Averaging data to one channel per subband for self-calibration')
                if os.path.isdir(self.crosscaldir + '/' + self.target):
                    uv = aipy.miriad.UV(self.crosscaldir + '/' + self.target) # Get the number of channels for the original dataset
                    numchan = uv['nschan']
                    if os.path.isdir(self.selfcaldir + '/' + self.target):
                        selfcaltargetbeamsaverage = True
                        logger.info('Beam ' + self.beam + ': Averaged dataset already available')
                    else:
                        uvaver = lib.miriad('uvaver')
                        uvaver.vis = self.crosscaldir + '/' + self.target
                        uvaver.line = "'" + 'channel,' + str(numchan/64) + ',1,64,64' + "'"
                        uvaver.out = self.selfcaldir + '/' + self.target
                        uvaver.go()
                        if os.path.isdir(self.selfcaldir + '/' + self.target): # Check if file was produced
                            selfcaltargetbeamsaverage = True
                        else:
                            selfcaltargetbeamsaverage = False
                            logger.error('Beam ' + self.beam + ': Averaging of data not successful')
                else:
                    selfcaltargetbeamsaverage = False
                    logger.error('Beam ' + self.beam + ': Converted dataset not available')
            else:
                logger.info('Beam ' + self.beam + ': Dataset was already averaged')
                selfcaltargetbeamsaverage = True

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, beam + '_targetbeams_average', selfcaltargetbeamsaverage)


    def flagline(self):
        """
        Creates an image cube of the averaged datasets and measures the rms in each channel. All channels with an rms
        outside of a given sigma interval are flagged in the self-calibration, continuum and polarisation imagaing, but are still used for line imaging.
        """
        subs_setinit.setinitdirs(self)

        beam = 'selfcal_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the flagging of residual RFI/HI

        # Status of the flagging of RFI/HI
        selfcaltargetbeamsflagline = get_param_def(self, beam  + '_targetbeams_flagline', False)
        selfcaltargetbeamsflaglinechannels = get_param_def(self, beam + '_targetbeams_flagline_channels', np.full(1, 'S50'))

        if self.selfcal_flagline:
            if not selfcaltargetbeamsflagline:
                subs_setinit.setinitdirs(self)
                subs_setinit.setdatasetnamestomiriad(self)
                subs_managefiles.director(self, 'ch', self.selfcaldir)
                logger.info('Beam ' + self.beam + ': Automatically flagging HI-line/RFI')
                invert = lib.miriad('invert')
                invert.vis = self.target
                invert.map = 'map'
                invert.beam = 'beam'
                invert.imsize = 1024
                invert.cell = 5
                invert.stokes = 'i'
                invert.slop = 1
                invert.go()
                if os.path.exists('map'):
                    min, max, std = imstats.getcubestats(self, 'map')
                    median = np.median(std)
                    stdall = np.nanstd(std)
                    diff = std - median
                    detections = np.where(np.abs(self.selfcal_flagline_sigma * diff) > stdall)[0]
                    selfcaltargetbeamsflaglinechannels[0] = np.array2string(detections, separator=',')
                    if len(detections) > 0:
                        logger.info('Beam ' + self.beam + ': Flagging high noise in channel(s) ' + str(detections).lstrip('[').rstrip(']'))
                        for d in detections:
                            uvflag = lib.miriad('uvflag')
                            uvflag.vis = self.target
                            uvflag.flagval = 'flag'
                            uvflag.line = "'" + 'channel,1,' + str(d) + "'"
                            uvflag.go()
                    else:
                        logger.debug('Beam ' + self.beam + ': No HI-line/RFI found!')
                    selfcaltargetbeamsflagline = True
                    subs_managefiles.director(self, 'rm', self.selfcaldir + '/' + 'map')
                    subs_managefiles.director(self, 'rm', self.selfcaldir + '/' + 'beam')
                else:
                    selfcaltargetbeamsflagline = False
                    logger.error('Beam ' + self.beam + ': Averaged line cube could not be created! Skipping flagging of HI-line/RFI!')
            else:
                logger.info('Beam ' + self.beam + ': Automatic flagging of HI-line/RFI was already executed!')
        else:
            logger.warning('Beam ' + self.beam + ': Automatic HI-line/RFI flagging disabled!')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, beam + '_targetbeams_flagline', selfcaltargetbeamsflagline)
        subs_param.add_param(self, beam + '_targetbeams_flagline_channels', selfcaltargetbeamsflaglinechannels)


    def parametric(self):
        """
        Parametric self calibration using an NVSS/FIRST skymodel and calculating spectral indices by source matching with WENSS.
        """
        subs_setinit.setinitdirs(self)

        beam = 'selfcal_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the parametric self-calibration

        selfcaltargetbeamsparametric = get_param_def(self, beam + '_targetbeams_parametric', False)

        if self.selfcal_parametric:
            if not selfcaltargetbeamsparametric:
                subs_setinit.setinitdirs(self)
                subs_setinit.setdatasetnamestomiriad(self)
                subs_managefiles.director(self, 'ch', self.selfcaldir)
                logger.info('Beam ' + self.beam + ': Parametric self calibration')
                subs_managefiles.director(self, 'mk', self.selfcaldir + '/pm')
                parametric_textfile = lsm.lsm_model(self.target, self.selfcal_parametric_skymodel_radius, self.selfcal_parametric_skymodel_cutoff, self.selfcal_parametric_skymodel_distance)
                lsm.write_model(self.selfcaldir + '/pm/model.txt', parametric_textfile)
                logger.debug('Beam ' + self.beam + ': Creating model from textfile model.txt')
                uv = aipy.miriad.UV(self.selfcaldir + '/' + self.target)
                freq = uv['sfreq']
                uvmodel = lib.miriad('uvmodel')
                uvmodel.vis = self.target
                parametric_modelfile = open(self.selfcaldir + '/pm/model.txt', 'r')
                for n, source in enumerate(parametric_modelfile.readlines()):
                    if n == 0:
                        uvmodel.options = 'replace,mfs'
                    else:
                        uvmodel.options = 'add,mfs'
                    uvmodel.offset = source.split(',')[0] + ',' + source.split(',')[1]
                    uvmodel.flux = source.split(',')[2] + ',i,' + str(freq) + ',' + source.split(',')[4].rstrip('\n') + ',0,0'
                    uvmodel.out = 'pm/tmp' + str(n)
                    uvmodel.go()
                    uvmodel.vis = uvmodel.out
                subs_managefiles.director(self, 'rn', 'pm/model.mir', uvmodel.out)  # Rename the last modelfile to model
                subs_managefiles.director(self, 'rm', 'pm/tmp*')  # Remove all the obsolete modelfiles
                logger.debug('Beam ' + self.beam + ': Parametric self-calibration with solution interval {} min and uvrange limits of {}~{} klambda #'.format(self.selfcal_parametric_solint, self.selfcal_parametric_uvmin, self.selfcal_parametric_uvmax))
                selfcal = lib.miriad('selfcal')
                selfcal.vis = self.target
                selfcal.model = 'pm/model.mir'
                if self.selfcal_parametric_solint == 'auto':
                    parmodelarray = np.loadtxt('pm/model.txt', delimiter=',')
                    parflux = np.sum(parmodelarray[:,2])
                    gaussianity, TN = masking.get_theoretical_noise(self, self.target)  # Gaussianity test and theoretical noise calculation using Stokes V image
                    if self.selfcal_parametric_amp:
                        selfcal.interval = calc_scal_interval(parflux, TN, 720, 66, self.selfcal_parametric_nfbin, 2, 10.0, 1)
                    else:
                        selfcal.interval = calc_scal_interval(parflux, TN, 720, 66, self.selfcal_parametric_nfbin, 2, 3.0, 1)
                else:
                    selfcal.interval = self.selfcal_parametric_solint
                selfcal.select = "'" + 'uvrange(' + str(self.selfcal_parametric_uvmin) + ',' + str(self.selfcal_parametric_uvmax) + ')' + "'"
                selfcal.nfbin = self.selfcal_parametric_nfbin
                # Choose reference antenna if given
                if self.selfcal_refant == '':
                    pass
                else:
                    selfcal.refant = self.selfcal_refant
                # Do amplitude calibration if wanted
                if self.selfcal_parametric_amp:
                    selfcal.options = 'mfs,amp'
                    logger.warning('Beam ' + self.beam + ': Doing parametric amplitude calibration. Your fluxes might be wrong!')
                else:
                    selfcal.options = 'mfs'
                selfcal.go()
                selfcaltargetbeamsparametric = True
                logger.debug('Beam ' + self.beam + ': Parametric self calibration done!')
            else:
                selfcaltargetbeamsparametric = True
                logger.info('Beam ' + self.beam + ': Data was already calibrated with parametric model!')
        else:
            selfcaltargetbeamsparametric = False
            logger.info('Beam ' + self.beam + ': Parametric self calibration disabled!')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, beam + '_targetbeams_parametric', selfcaltargetbeamsparametric)


    def phase(self):
        """
        Executes the phase self-calibration with the given parameters
        """
        subs_setinit.setinitdirs(self)

        beam = 'selfcal_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the iterative phase self-calibration

        selfcaltargetbeamsphasestatus = get_param_def(self, beam + '_targetbeams_phase_status', False)
        selfcaltargetbeamsphasemapstatus = get_param_def(self, beam + '_targetbeams_phase_mapstatus', np.full((self.selfcal_phase_majorcycle), False))
        selfcaltargetbeamsphasemapstats = get_param_def(self, beam  + '_targetbeams_phase_mapstats', np.full((self.selfcal_phase_majorcycle, 3), np.nan))
        selfcaltargetbeamsphasebeamstatus = get_param_def(self, beam + '_targetbeams_phase_beamstatus', np.full((self.selfcal_phase_majorcycle), False))
        selfcaltargetbeamsphasemaskstatus = get_param_def(self, beam + '_targetbeams_phase_maskstatus', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle), False))
        selfcaltargetbeamsphasemaskstats = get_param_def(self, beam + '_targetbeams_phase_maskstats', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle, 2), np.nan))
        selfcaltargetbeamsphasemodelstatus = get_param_def(self, beam + '_targetbeams_phase_modelstatus', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle), False))
        selfcaltargetbeamsphasemodelstats = get_param_def(self, beam + '_targetbeams_phase_modelstats', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle, 2), np.nan))
        selfcaltargetbeamsphaseimagestatus = get_param_def(self, beam + '_targetbeams_phase_imagestatus', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle), False))
        selfcaltargetbeamsphaseimagestats = get_param_def(self, beam + '_targetbeams_phase_imagestats', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle, 3), np.nan))
        selfcaltargetbeamsphaseresidualstatus = get_param_def(self, beam + '_targetbeams_phase_residualstatus', False)
        selfcaltargetbeamsphaseresidualstats = get_param_def(self, beam + '_targetbeams_phase_residualstats', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle, 3), np.nan))
        selfcaltargetbeamsphasemaskthreshold = get_param_def(self, beam + '_targetbeams_phase_maskthreshold', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle), np.nan))
        selfcaltargetbeamsphasecleanthreshold = get_param_def(self, beam + '_targetbeams_phase_cleanthreshold', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle), np.nan))
        selfcaltargetbeamsphasethresholdtype = get_param_def(self, beam + '_targetbeams_phase_thresholdtype', np.full((self.selfcal_phase_majorcycle, self.selfcal_phase_minorcycle), 'NA'))
        selfcaltargetbeamsphasefinalmajor = get_param_def(self, beam + '_targetbeams_phase_final_majorcycle', np.full((1), 0))
        selfcaltargetbeamsphasefinalminor = get_param_def(self, beam + '_targetbeams_phase_final_minorcycle', np.full((1), 0))

        if self.selfcal_phase:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.selfcaldir)
            logger.info('Beam ' + self.beam + ': Iterative phase self calibration')
            majdr_list = masking.calc_dr_maj(self.selfcal_phase_drinit, self.selfcal_phase_dr0, self.selfcal_phase_majorcycle, self.selfcal_phase_majorcycle_function) # List with dynamic range dynamic range for major cycle
            TNreached = False # Stop self-calibration if theoretical noise is reached
            stop = False # Variable to stop self-calibration, if something goes wrong
            for majc in range(self.selfcal_phase_majorcycle):
                if stop:
                    break
                else:
                    if not TNreached:
                        if majc == 0: # Calculate theoretical noise at the beginning of the first major cycle
                            gaussianity, TN = masking.get_theoretical_noise(self, self.target)  # Gaussianity test and theoretical noise calculation using Stokes V image
                            if gaussianity:
                                pass
                            else:
                                logger.warning('Beam ' + self.beam + ': Stokes V image shows non-gaussian distribution. Your theoretical noise value might be off!')
                            logger.info('Beam ' + self.beam + ': Theoretical noise is ' + '%.6f' % TN + ' Jy')
                        else:
                            pass
                        subs_managefiles.director(self, 'mk', self.selfcaldir + '/' + str(majc).zfill(2))
                        mindr_list = masking.calc_dr_min(majdr_list, majc, self.selfcal_phase_minorcycle, self.selfcal_phase_mindr, self.selfcal_phase_minorcycle_function) # List with dynamic range dynamic range for minor cycles
                        for minc in range(self.selfcal_phase_minorcycle):
                            if not TNreached:
                                if minc == 0: # Create a new dirty image after self-calibration
                                    invert = lib.miriad('invert')  # Create the dirty image
                                    invert.vis = self.target
                                    invert.map = str(majc).zfill(2) + '/map_00'
                                    invert.beam = str(majc).zfill(2) + '/beam_00'
                                    invert.imsize = self.selfcal_image_imsize
                                    invert.cell = self.selfcal_image_cellsize
                                    invert.stokes = 'i'
                                    invert.options = 'mfs,sdb,double'
                                    invert.slop = 1
                                    invert.robust = -2
                                    invert.go()
                                    # Check if dirty image and beam is there and ok
                                    if os.path.isdir(str(majc).zfill(2) + '/map_00') and os.path.isdir(str(majc).zfill(2) + '/beam_00'):
                                        selfcaltargetbeamsphasebeamstatus[majc] = True
                                        selfcaltargetbeamsphasemapstats[majc,:] = imstats.getimagestats(self, str(majc).zfill(2) + '/map_00')
                                        if qa.checkdirtyimage(self, str(majc).zfill(2) + '/map_00'):
                                            selfcaltargetbeamsphasemapstatus[majc] = True
                                        else:
                                            selfcaltargetbeamsphasemapstatus[majc] = False
                                            selfcaltargetbeamsphasestatus = False
                                            logger.error('Beam ' + self.beam + ': Dirty image for major cycle ' + str(majc) + ' is invalid. Stopping self calibration!')
                                            stop = True
                                            selfcaltargetbeamsphasefinalmajor = majc
                                            selfcaltargetbeamsphasefinalminor = minc
                                            break
                                    else:
                                        selfcaltargetbeamsphasebeamstatus[majc] = False
                                        selfcaltargetbeamsphasestatus = False
                                        logger.error('Beam ' + self.beam + ': Dirty image or beam for major cycle ' + str(majc) + ' not found. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsphasefinalmajor = majc
                                        selfcaltargetbeamsphasefinalminor = minc
                                        break
                                    dirtystats = imstats.getimagestats(self, str(majc).zfill(2) + '/map_00') # Min, max, rms of the dirty image
                                    TNdr = masking.calc_theoretical_noise_dr(dirtystats[1], TN, self.selfcal_phase_nsigma) # Theoretical noise dynamic range
                                    DRdr = masking.calc_dynamic_range_dr(mindr_list, minc, self.selfcal_phase_mindr) # Dynamic range dynamic range
                                    Ndr = masking.calc_noise_dr(minc, majc, self.selfcal_phase_c0) # Noise dynamic range
                                    TNth = masking.calc_theoretical_noise_threshold(dirtystats[1], TNdr) # Theoretical noise threshold
                                    DRth = masking.calc_dynamic_range_threshold(dirtystats[1], DRdr) # Dynamic range threshold
                                    Nth = masking.calc_noise_threshold(dirtystats[1], Ndr) # Noise threshold
                                    Mth = masking.calc_mask_threshold(TNth, Nth, DRth) # Masking threshold
                                    Cc = masking.calc_clean_cutoff(Mth[0], self.selfcal_phase_c1) # Clean cutoff
                                    selfcaltargetbeamsphasemaskthreshold[majc, minc] = Mth[0]
                                    selfcaltargetbeamsphasethresholdtype[majc, minc] = Mth[1]
                                    selfcaltargetbeamsphasecleanthreshold[majc, minc] = Cc
                                    if majc == 0: # Create mask from dirty image in the first major cycle
                                        beampars = masking.get_beam(self, invert.map, invert.beam)
                                        masking.create_mask(self, str(majc).zfill(2) + '/map_00', str(majc).zfill(2) + '/mask_00', Mth[0], TN, beampars=beampars)
                                    else: # Otherwise copy the mask from the last minor cycle of the previous major iteration
                                        subs_managefiles.director(self, 'cp', str(majc).zfill(2) + '/mask_00', file_=str(majc-1).zfill(2) + '/mask_' + str(self.selfcal_phase_minorcycle-1).zfill(2))
                                    # Check if mask is there and ok
                                    if os.path.isdir(str(majc).zfill(2) + '/mask_00'):
                                        selfcaltargetbeamsphasemaskstats[majc, minc, :] = imstats.getmaskstats(self, str(majc).zfill(2) + '/mask_00', self.selfcal_image_imsize)
                                        if qa.checkmaskimage(self, str(majc).zfill(2) + '/mask_00'):
                                            selfcaltargetbeamsphasemaskstatus[majc, minc] = True
                                        else:
                                            selfcaltargetbeamsphasemaskstatus[majc, minc] = False
                                            selfcaltargetbeamsphasestatus = False
                                            logger.error('Beam ' + self.beam + ': Mask image for cycle ' + str(majc) + '/' + str(minc) + ' is invalid. Stopping self-calibration!')
                                            stop = True
                                            selfcaltargetbeamsphasefinalmajor = majc
                                            selfcaltargetbeamsphasefinalminor = minc
                                            break
                                    else:
                                        selfcaltargetbeamsphasemaskstatus[majc, minc] = False
                                        selfcaltargetbeamsphasestatus = False
                                        logger.error('Beam ' + self.beam + ': Mask image for cycle ' + str(majc) + '/' + str(minc) + ' not found. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsphasefinalmajor = majc
                                        selfcaltargetbeamsphasefinalminor = minc
                                        break
                                    mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                                    mfclean.map = str(majc).zfill(2) + '/map_00'
                                    mfclean.beam = str(majc).zfill(2) + '/beam_00'
                                    mfclean.out = str(majc).zfill(2) + '/model_00'
                                    mfclean.cutoff = Cc
                                    mfclean.niters = 1000000
                                    mfclean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_00)' + '"'
                                    mfclean.go()
                                    # Check if clean component image is there and ok
                                    if os.path.isdir(str(majc).zfill(2) + '/model_00'):
                                        selfcaltargetbeamsphasemodelstats[majc, minc, :] = imstats.getmodelstats(self, str(majc).zfill(2) + '/model_00')
                                        if qa.checkmodelimage(self, str(majc).zfill(2) + '/model_00'):
                                            selfcaltargetbeamsphasemodelstatus[majc, minc] = True
                                        else:
                                            selfcaltargetbeamsphasemodelstatus[majc, minc] = False
                                            selfcaltargetbeamsphasestatus = False
                                            logger.error('Beam ' + self.beam + ': Clean component image for cycle ' + str(majc) + '/' + str(minc) + ' is invalid. Stopping self-calibration!')
                                            stop = True
                                            selfcaltargetbeamsphasefinalmajor = majc
                                            selfcaltargetbeamsphasefinalminor = minc
                                            break
                                    else:
                                        selfcaltargetbeamsphasemodelstatus[majc, minc] = False
                                        selfcaltargetbeamsphasestatus = False
                                        logger.error('Beam ' + self.beam + ': Clean component image for cycle ' + str(majc) + '/' + str(minc) + ' not found. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsphasefinalmajor = majc
                                        selfcaltargetbeamsphasefinalminor = minc
                                        break
                                    restor = lib.miriad('restor') # Create the restored image
                                    restor.model = str(majc).zfill(2) + '/model_00'
                                    restor.beam = str(majc).zfill(2) + '/beam_00'
                                    restor.map = str(majc).zfill(2) + '/map_00'
                                    restor.out = str(majc).zfill(2) + '/image_00'
                                    restor.mode = 'clean'
                                    restor.go()
                                    # Check if restored image is there and ok
                                    if os.path.isdir(str(majc).zfill(2) + '/image_00'):
                                        selfcaltargetbeamsphaseimagestats[majc, minc, :] = imstats.getimagestats(self, str(majc).zfill(2) + '/image_00')
                                        if qa.checkrestoredimage(self, str(majc).zfill(2) + '/image_00'):
                                            selfcaltargetbeamsphaseimagestatus[majc, minc] = True
                                        else:
                                            selfcaltargetbeamsphaseimagestatus[majc, minc] = False
                                            selfcaltargetbeamsphasestatus = False
                                            logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(majc) + '/' + str(minc) + ' is invalid. Stopping self-calibration!')
                                            stop = True
                                            selfcaltargetbeamsphasefinalmajor = majc
                                            selfcaltargetbeamsphasefinalminor = minc
                                            break
                                    else:
                                        selfcaltargetbeamsphaseimagestatus[majc, minc] = False
                                        selfcaltargetbeamsphasestatus = False
                                        logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(majc) + '/' + str(minc) + ' not found. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsphasefinalmajor = majc
                                        selfcaltargetbeamsphasefinalminor = minc
                                        break
                                    restor.mode = 'residual' # Create the residual image
                                    restor.out = str(majc).zfill(2) + '/residual_00'
                                    restor.go()
                                    residualstats = imstats.getimagestats(self, str(majc).zfill(2) + '/residual_00') # Min, max, rms of the residual image
                                    selfcaltargetbeamsphaseresidualstats[majc, minc, :] = residualstats
                                    currdr = dirtystats[1]/residualstats[1]
                                    logger.info('Beam ' + self.beam + ': Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(majc) + '/' + str(minc))
                                    selfcaltargetbeamsphasefinalminor = minc
                                    if Mth[1] == 'TN':
                                        TNreached = True
                                        logger.info('Beam ' + self.beam + ': Theoretical noise threshold reached. Using last model for final self-calibration!')
                                    else:
                                        TNreached = False
                                else: # Use the first clean model to continue cleaning
                                    TNdr = masking.calc_theoretical_noise_dr(dirtystats[1], TN, self.selfcal_phase_nsigma) # Theoretical noise dynamic range
                                    DRdr = masking.calc_dynamic_range_dr(mindr_list, minc, self.selfcal_phase_mindr) # Dynamic range dynamic range
                                    Ndr = masking.calc_noise_dr(minc, majc, self.selfcal_phase_c0) # Noise dynamic range
                                    TNth = masking.calc_theoretical_noise_threshold(dirtystats[1], TNdr) # Theoretical noise threshold
                                    DRth = masking.calc_dynamic_range_threshold(dirtystats[1], DRdr) # Dynamic range threshold
                                    Nth = masking.calc_noise_threshold(dirtystats[1], Ndr) # Noise threshold
                                    Mth = masking.calc_mask_threshold(TNth, Nth, DRth) # Masking threshold
                                    Cc = masking.calc_clean_cutoff(Mth[0], self.selfcal_phase_c1) # Clean cutoff
                                    selfcaltargetbeamsphasemaskthreshold[majc, minc] = Mth[0]
                                    selfcaltargetbeamsphasethresholdtype[majc, minc] = Mth[1]
                                    selfcaltargetbeamsphasecleanthreshold[majc, minc] = Cc
                                    masking.create_mask(self, str(majc).zfill(2) + '/image_' + str(minc-1).zfill(2), str(majc).zfill(2) + '/mask_' + str(minc).zfill(2), Mth[0], TN, beampars=None)
                                    # Check if mask is there and ok
                                    if os.path.isdir(str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)):
                                        selfcaltargetbeamsphasemaskstats[majc, minc, :] = imstats.getmaskstats(self, str(majc).zfill(2) + '/mask_' + str(minc).zfill(2), self.selfcal_image_imsize)
                                        if qa.checkmaskimage(self, str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)):
                                            selfcaltargetbeamsphasemaskstatus[majc, minc] = True
                                        else:
                                            selfcaltargetbeamsphasemaskstatus[majc, minc] = False
                                            selfcaltargetbeamsphasestatus = False
                                            msg = 'Beam ' + self.beam + ': Mask image for cycle ' + str(majc) + '/' + str(minc) + ' is invalid. Stopping self-calibration!'
                                            logger.error(msg)
                                            raise ApercalException(msg)
                                            stop = True
                                            selfcaltargetbeamsphasefinalmajor = majc
                                            selfcaltargetbeamsphasefinalminor = minc
                                            break
                                    else:
                                        selfcaltargetbeamsphasemaskstatus[majc, minc] = False
                                        selfcaltargetbeamsphasestatus = False
                                        msg = 'Beam ' + self.beam + ': Mask image for cycle ' + str(majc) + '/' + str(minc) + ' not found. Stopping self-calibration!'
                                        logger.error(msg)
                                        raise ApercalException(msg)
                                        stop = True
                                        selfcaltargetbeamsphasefinalmajor = majc
                                        selfcaltargetbeamsphasefinalminor = minc
                                        break
                                    mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                                    mfclean.map = str(majc).zfill(2) + '/map_00'
                                    mfclean.beam = str(majc).zfill(2) + '/beam_00'
                                    mfclean.model = str(majc).zfill(2) + '/model_' + str(minc-1).zfill(2)
                                    mfclean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                                    mfclean.cutoff = Cc
                                    mfclean.niters = 1000000
                                    mfclean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(minc).zfill(2) + ')' + '"'
                                    mfclean.go()
                                    # Check if clean component image is there and ok
                                    if os.path.isdir(str(majc).zfill(2) + '/model_' + str(minc).zfill(2)):
                                        selfcaltargetbeamsphasemodelstats[majc, minc, :] = imstats.getmodelstats(self, str(majc).zfill(2) + '/model_' + str(minc).zfill(2))
                                        if qa.checkmodelimage(self, str(majc).zfill(2) + '/model_' + str(minc).zfill(2)):
                                            selfcaltargetbeamsphasemodelstatus[majc, minc] = True
                                        else:
                                            selfcaltargetbeamsphasemodelstatus[majc, minc] = False
                                            selfcaltargetbeamsphasestatus = False
                                            msg = 'Beam ' + self.beam + ': Clean component image for cycle ' + str(majc) + '/' + str(minc) + ' is invalid. Stopping self-calibration!'
                                            logger.error(msg)
                                            raise ApercalException(msg)
                                            stop = True
                                            selfcaltargetbeamsphasefinalmajor = majc
                                            selfcaltargetbeamsphasefinalminor = minc
                                            break
                                    else:
                                        selfcaltargetbeamsphasemodelstatus[majc, minc] = False
                                        selfcaltargetbeamsphasestatus = False
                                        msg = 'Beam ' + self.beam + ': Clean component image for cycle ' + str(majc) + '/' + str(minc) + ' not found. Stopping self-calibration!'
                                        logger.error(msg)
                                        raise ApercalException(msg)
                                        stop = True
                                        selfcaltargetbeamsphasefinalmajor = majc
                                        selfcaltargetbeamsphasefinalminor = minc
                                        break
                                    restor = lib.miriad('restor') # Create the restored image
                                    restor.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                                    restor.beam = str(majc).zfill(2) + '/beam_00'
                                    restor.map = str(majc).zfill(2) + '/map_00'
                                    restor.out = str(majc).zfill(2) + '/image_' + str(minc).zfill(2)
                                    restor.mode = 'clean'
                                    restor.go()
                                    # Check if restored image is there and ok
                                    if os.path.isdir(str(majc).zfill(2) + '/image_' + str(minc).zfill(2)):
                                        selfcaltargetbeamsphaseimagestats[majc, minc, :] = imstats.getimagestats(self, str(majc).zfill(2) + '/image_00')
                                        if qa.checkrestoredimage(self, str(majc).zfill(2) + '/image_' + str(minc).zfill(2)):
                                            selfcaltargetbeamsphaseimagestatus[majc, minc] = True
                                        else:
                                            selfcaltargetbeamsphaseimagestatus[majc, minc] = False
                                            selfcaltargetbeamsphasestatus = False
                                            logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(majc) + '/' + str(minc) + ' is invalid. Stopping self-calibration!')
                                            stop = True
                                            selfcaltargetbeamsphasefinalmajor = majc
                                            selfcaltargetbeamsphasefinalminor = minc
                                            break
                                    else:
                                        selfcaltargetbeamsphaseimagestatus[majc, minc] = False
                                        selfcaltargetbeamsphasestatus = False
                                        logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(majc) + '/' + str(minc) + ' not found. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsphasefinalmajor = majc
                                        selfcaltargetbeamsphasefinalminor = minc
                                        break
                                    restor.mode = 'residual' # Create the residual image
                                    restor.out = str(majc).zfill(2) + '/residual_' + str(minc).zfill(2)
                                    restor.go()
                                    residualstats = imstats.getimagestats(self, str(majc).zfill(2) + '/residual_' + str(minc).zfill(2)) # Min, max, rms of the residual image
                                    selfcaltargetbeamsphaseresidualstats[majc, minc, :] = residualstats
                                    currdr = dirtystats[1]/residualstats[1]
                                    logger.info('Beam ' + self.beam + ': Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(majc) + '/' + str(minc))
                                    selfcaltargetbeamsphasefinalminor = minc
                                    if Mth[1] == 'TN':
                                        TNreached = True
                                        logger.info('Beam ' + self.beam + ': Theoretical noise threshold reached. Using last model for final self-calibration!')
                                    else:
                                        TNreached = False
                            else:
                                pass
                        # Do the self calibration in the normal cycle
                        selfcaltargetbeamsphasefinalmajor = majc
                        selfcaltargetbeamsphasefinalminor = minc
                        selfcal = lib.miriad('selfcal')
                        selfcal.vis = self.target
                        selfcal.select = '"' + 'uvrange(' + str(self.selfcal_phase_uvmin[majc]) + ',' + str(self.selfcal_phase_uvmax[majc]) + ')"'
                        selfcal.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                        if self.selfcal_phase_solint == 'auto':
                            selfcal.interval = calc_scal_interval(selfcaltargetbeamsphasemodelstats[majc, minc, 1], TN, 720, 66, self.selfcal_phase_nfbin, 2, 3.0, majc+1)
                        else:
                            selfcal.interval = self.selfcal_phase_solint[majc]
                        if self.selfcal_refant == '': # Choose reference antenna if given
                            pass
                        else:
                            selfcal.refant = self.selfcal_refant
                        selfcal.options = 'phase,mfs'
                        selfcal.nfbin = self.selfcal_phase_nfbin
                        selfcal.go()
                    else:
                        # When theoretical noise is reached, do a last self-calibration round
                        selfcal = lib.miriad('selfcal')
                        selfcal.vis = self.target
                        selfcal.select = '"' + 'uvrange(' + str(self.selfcal_phase_uvmin[-1]) + ',' + str(self.selfcal_phase_uvmax[-1]) + ')"'
                        selfcal.model = str(selfcaltargetbeamsphasefinalmajor).zfill(2) + '/model_' + str(selfcaltargetbeamsphasefinalminor).zfill(2) # Update model via param file
                        if self.selfcal_phase_solint == 'auto':
                            selfcal.interval = calc_scal_interval(selfcaltargetbeamsphasemodelstats[selfcaltargetbeamsphasefinalmajor, selfcaltargetbeamsphasefinalminor, 1], TN, 720, 66, self.selfcal_phase_nfbin, 2, 3.0, majc+1)
                        else:
                            selfcal.interval = self.selfcal_phase_solint[-1]
                        if self.selfcal_refant == '': # Choose reference antenna if given
                            pass
                        else:
                            selfcal.refant = self.selfcal_refant
                        selfcal.options = 'phase,mfs'
                        selfcal.nfbin = self.selfcal_phase_nfbin
                        selfcal.go()
            # Check final residual image for gaussianity, we should add more metrics here to check selfcal
            if TNreached or (self.selfcal_phase_minorcycle == selfcaltargetbeamsphasefinalminor and self.selfcal_phase_majorcycle == selfcaltargetbeamsphasefinalmajor):
                if qa.checkimagegaussianity(self, str(selfcaltargetbeamsphasefinalmajor).zfill(2) + '/residual_' + str(selfcaltargetbeamsphasefinalminor).zfill(2), self.selfcal_phase_gaussianity):
                    selfcaltargetbeamsphaseresidualstatus = True
                    selfcaltargetbeamsphasestatus = True
                    logger.info('Beam ' + self.beam + ': Iterative phase self calibration successfully done!')
                else:
                    selfcaltargetbeamsphaseresidualstatus = False
                    selfcaltargetbeamsphasestatus = False
                    logger.warning('Beam ' + self.beam + ': Final residual image shows non-gaussian statistics. Phase self-calibration was not successful!')
            else:
                selfcaltargetbeamsphasestatus = False
                logger.warning('Beam ' + self.beam + ': Iterative phase self-calibration did not reach the final cycle or the theoretical noise. Calibration was not successful.')
        else:
            logger.warning('Beam ' + self.beam + ': Not doing iterative phase self-calibration!')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, beam + '_targetbeams_phase_status', selfcaltargetbeamsphasestatus)
        subs_param.add_param(self, beam + '_targetbeams_phase_mapstatus', selfcaltargetbeamsphasemapstatus)
        subs_param.add_param(self, beam + '_targetbeams_phase_mapstats', selfcaltargetbeamsphasemapstats)
        subs_param.add_param(self, beam + '_targetbeams_phase_beamstatus', selfcaltargetbeamsphasebeamstatus)
        subs_param.add_param(self, beam + '_targetbeams_phase_maskstatus', selfcaltargetbeamsphasemaskstatus)
        subs_param.add_param(self, beam + '_targetbeams_phase_maskstats', selfcaltargetbeamsphasemaskstats)
        subs_param.add_param(self, beam + '_targetbeams_phase_modelstatus', selfcaltargetbeamsphasemodelstatus)
        subs_param.add_param(self, beam + '_targetbeams_phase_modelstats', selfcaltargetbeamsphasemodelstats)
        subs_param.add_param(self, beam + '_targetbeams_phase_imagestatus', selfcaltargetbeamsphaseimagestatus)
        subs_param.add_param(self, beam + '_targetbeams_phase_imagestats', selfcaltargetbeamsphaseimagestats)
        subs_param.add_param(self, beam + '_targetbeams_phase_residualstatus', selfcaltargetbeamsphaseresidualstatus)
        subs_param.add_param(self, beam + '_targetbeams_phase_residualstats', selfcaltargetbeamsphaseresidualstats)
        subs_param.add_param(self, beam + '_targetbeams_phase_maskthreshold', selfcaltargetbeamsphasemaskthreshold)
        subs_param.add_param(self, beam + '_targetbeams_phase_cleanthreshold', selfcaltargetbeamsphasecleanthreshold)
        subs_param.add_param(self, beam + '_targetbeams_phase_thresholdtype', selfcaltargetbeamsphasethresholdtype)
        subs_param.add_param(self, beam + '_targetbeams_phase_final_majorcycle', selfcaltargetbeamsphasefinalmajor)
        subs_param.add_param(self, beam + '_targetbeams_phase_final_minorcycle', selfcaltargetbeamsphasefinalminor)


    def amp(self):
        """
        Executes amplitude self-calibration with the given parameters
        """
        subs_setinit.setinitdirs(self)

        beam = 'selfcal_B' + str(self.beam).zfill(2)

        # Create the parameters for the parameter file for the amplitude self-calibration

        selfcaltargetbeamsampstatus = get_param_def(self, beam + '_targetbeams_amp_status', False)
        selfcaltargetbeamsampapplystatus = get_param_def(self, beam + '_targetbeams_amp_applystatus', False)
        selfcaltargetbeamsampmapstatus = get_param_def(self, beam + '_targetbeams_amp_mapstatus', False)
        selfcaltargetbeamsampmapstats = get_param_def(self, beam + '_targetbeams_amp_mapstats', np.full((3), np.nan))
        selfcaltargetbeamsampbeamstatus = get_param_def(self, beam + '_targetbeams_amp_beamstatus', False)
        selfcaltargetbeamsampmaskstatus = get_param_def(self, beam + '_targetbeams_amp_maskstatus', np.full((self.selfcal_amp_minorcycle), False))
        selfcaltargetbeamsampmaskstats = get_param_def(self, beam + '_targetbeams_amp_maskstats', np.full((self.selfcal_amp_minorcycle, 2), np.nan))
        selfcaltargetbeamsampmodelstatus = get_param_def(self, beam + '_targetbeams_amp_modelstatus', np.full((self.selfcal_amp_minorcycle), False))
        selfcaltargetbeamsampmodelstats = get_param_def(self, beam + '_targetbeams_amp_modelstats', np.full((self.selfcal_amp_minorcycle, 2), np.nan))
        selfcaltargetbeamsampimagestatus = get_param_def(self, beam + '_targetbeams_phase_imagestatus', np.full((self.selfcal_amp_minorcycle), False))
        selfcaltargetbeamsampimagestats = get_param_def(self, beam + '_targetbeams_phase_imagestats', np.full((self.selfcal_amp_minorcycle, 3), np.nan))
        selfcaltargetbeamsampresidualstatus = get_param_def(self, beam + '_targetbeams_phase_residualstatus', False)
        selfcaltargetbeamsampresidualstats = get_param_def(self, beam + '_targetbeams_phase_residualstats', np.full((self.selfcal_amp_minorcycle, 3), np.nan))
        selfcaltargetbeamsampmaskthreshold = get_param_def(self, beam + '_targetbeams_phase_maskthreshold', np.full((self.selfcal_amp_minorcycle), np.nan))
        selfcaltargetbeamsampcleanthreshold = get_param_def(self, beam + '_targetbeams_phase_cleanthreshold', np.full((self.selfcal_amp_minorcycle), np.nan))
        selfcaltargetbeamsampthresholdtype = get_param_def(self, beam + '_targetbeams_phase_thresholdtype', np.full((self.selfcal_amp_minorcycle), 'NA'))
        selfcaltargetbeamsampfinalminor = get_param_def(self, beam + '_targetbeams_phase_final_minorcycle', np.full((1), 0))

        if self.selfcal_amp:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.selfcaldir)
            # Check if phase self-calibration was successful
            phasestatus = subs_param.get_param(self, beam + '_targetbeams_phase_status')
            if phasestatus:
                logger.info('Beam ' + self.beam + ': Amplitude self calibration')
                # Apply the phase self-calibration
                uvaver = lib.miriad('uvaver')
                uvaver.vis = self.target
                uvaver.out = self.target.rstrip('.mir') + '_amp.mir'
                uvaver.go()
                # Check if dataset was copied correctly
                if os.path.isdir(self.target.rstrip('.mir') + '_amp.mir'):
                    selfcaltargetbeamsampapplystatus = True
                    subs_managefiles.director(self, 'mk', self.selfcaldir + '/amp') # Create the amplitude self-calibration directory
                    phasemajor = subs_param.get_param(self, beam + '_targetbeams_phase_final_majorcycle') # Get the number of the last iteration during phase selfcal
                    phaseminor = subs_param.get_param(self, beam + '_targetbeams_phase_final_minorcycle')
                    lastphasemapmax = subs_param.get_param(self, beam + '_targetbeams_phase_mapstats')[phasemajor, 1]
                    lastphaseresidualmax = subs_param.get_param(self, beam + '_targetbeams_phase_residualstats')[phasemajor, phaseminor, 1]
                    lastphasedr = lastphasemapmax/lastphaseresidualmax
                    mindr_list = masking.calc_dr_amp(lastphasedr, self.selfcal_amp_dr0, self.selfcal_amp_minorcycle, self.selfcal_amp_minorcycle_function)  # List with dynamic range dynamic range for minor cycles
                    gaussianity, TN = masking.get_theoretical_noise(self, self.target.rstrip('.mir') + '_amp.mir')  # Gaussianity test and theoretical noise calculation using Stokes V image
                    if gaussianity:
                        pass
                    else:
                        logger.warning('Beam ' + self.beam + ': Stokes V image shows non-gaussian distribution. Your theoretical noise value might be off!')
                    logger.info('Beam ' + self.beam + ': Theoretical noise is ' + '%.6f' % TN + ' Jy')
                    TNreached = False  # Stop self-calibration if theoretical noise is reached
                    stop = False
                    for minc in range(self.selfcal_amp_minorcycle):
                        if not TNreached:
                            if minc == 0:  # Create a new dirty image after phase self-calibration
                                invert = lib.miriad('invert')  # Create the dirty image
                                invert.vis = self.target.rstrip('.mir') + '_amp.mir'
                                invert.map = 'amp/map_00'
                                invert.beam = 'amp/beam_00'
                                invert.imsize = self.selfcal_image_imsize
                                invert.cell = self.selfcal_image_cellsize
                                invert.stokes = 'i'
                                invert.options = 'mfs,sdb,double'
                                invert.slop = 1
                                invert.robust = -2
                                invert.go()
                                # Check if dirty image and beam is there and ok
                                if os.path.isdir('amp/map_00') and os.path.isdir('amp/beam_00'):
                                    selfcaltargetbeamsampbeamstatus = True
                                    selfcaltargetbeamsampmapstats[:] = imstats.getimagestats(self, 'amp/map_00')
                                    if qa.checkdirtyimage(self, 'amp/map_00'):
                                        selfcaltargetbeamsampmapstatus = True
                                    else:
                                        selfcaltargetbeamsampmapstatus = False
                                        selfcaltargetbeamsampstatus = False
                                        logger.error('Beam ' + self.beam + ': Dirty image for amplitude self-calibration is invalid. Stopping self calibration!')
                                        stop = True
                                        selfcaltargetbeamsampfinalminor = minc
                                        break
                                else:
                                    selfcaltargetbeamsampbeamstatus = False
                                    selfcaltargetbeamsampstatus = False
                                    logger.error('Beam ' + self.beam + ': Dirty image or beam for amplitude self-calibration not found. Stopping self-calibration!')
                                    stop = True
                                    selfcaltargetbeamsampfinalminor = minc
                                    break
                                dirtystats = imstats.getimagestats(self, 'amp/map_00')  # Min, max, rms of the dirty image
                                subs_managefiles.director(self, 'cp', self.selfcaldir + '/amp/' + 'mask_00', file_=self.selfcaldir + '/' + str(phasemajor).zfill(2) + '/mask_' + str(phaseminor).zfill(2))  # Copy the last mask from the phase selfcal over
                                # Check if mask is there and ok
                                if os.path.isdir('amp/mask_00'):
                                    selfcaltargetbeamsampmaskstats[minc, :] = imstats.getmaskstats(self, 'amp/mask_00', self.selfcal_image_imsize)
                                    if qa.checkmaskimage(self, 'amp/mask_00'):
                                        selfcaltargetbeamsampmaskstatus[minc] = True
                                    else:
                                        selfcaltargetbeamsampmaskstatus[minc] = False
                                        selfcaltargetbeamsampstatus = False
                                        logger.error('Beam ' + self.beam + ': Mask image for amplitude self-calibration is invalid. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsampfinalminor = minc
                                        break
                                else:
                                    selfcaltargetbeamsampmaskstatus[minc] = False
                                    selfcaltargetbeamsampstatus = False
                                    logger.error('Beam ' + self.beam + ': Mask image for amplitude self-calibration not found. Stopping self-calibration!')
                                    stop = True
                                    selfcaltargetbeamsampfinalminor = minc
                                    break
                                TNdr = masking.calc_theoretical_noise_dr(dirtystats[1], TN, self.selfcal_amp_nsigma)  # Theoretical noise dynamic range
                                DRdr = masking.calc_dynamic_range_dr(mindr_list, minc, self.selfcal_amp_mindr)  # Dynamic range dynamic range
                                Ndr = masking.calc_noise_dr(minc, phasemajor+1, self.selfcal_amp_c0)  # Noise dynamic range
                                TNth = masking.calc_theoretical_noise_threshold(dirtystats[1], TNdr)  # Theoretical noise threshold
                                DRth = masking.calc_dynamic_range_threshold(dirtystats[1], DRdr)  # Dynamic range threshold
                                Nth = masking.calc_noise_threshold(dirtystats[1], Ndr)  # Noise threshold
                                Mth = masking.calc_mask_threshold(TNth, Nth, DRth)  # Masking threshold
                                Cc = masking.calc_clean_cutoff(Mth[0], self.selfcal_phase_c1)  # Clean cutoff
                                selfcaltargetbeamsampmaskthreshold[minc] = Mth[0]
                                selfcaltargetbeamsampthresholdtype[minc] = Mth[1]
                                selfcaltargetbeamsampcleanthreshold[minc] = Cc
                                mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                                mfclean.map = 'amp/map_00'
                                mfclean.beam = 'amp/beam_00'
                                mfclean.out = 'amp/model_00'
                                mfclean.cutoff = Cc
                                mfclean.niters = 1000000
                                mfclean.region = '"' + 'mask(amp/mask_00)' + '"'
                                mfclean.go()
                                # Check if clean component image is there and ok
                                if os.path.isdir('amp/model_00'):
                                    selfcaltargetbeamsampmodelstats[minc, :] = imstats.getmodelstats(self, 'amp/model_00')
                                    if qa.checkmodelimage(self, 'amp/model_00'):
                                        selfcaltargetbeamsampmodelstatus[minc] = True
                                    else:
                                        selfcaltargetbeamsampmodelstatus[minc] = False
                                        selfcaltargetbeamsampstatus = False
                                        logger.error('Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' is invalid. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsampfinalminor = minc
                                        break
                                else:
                                    selfcaltargetbeamsampmodelstatus[minc] = False
                                    selfcaltargetbeamsampstatus = False
                                    logger.error('Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' not found. Stopping self-calibration!')
                                    stop = True
                                    selfcaltargetbeamsampfinalminor = minc
                                    break
                                restor = lib.miriad('restor')  # Create the restored image
                                restor.model = 'amp/model_00'
                                restor.beam = 'amp/beam_00'
                                restor.map = 'amp/map_00'
                                restor.out = 'amp/image_00'
                                restor.mode = 'clean'
                                restor.go()
                                # Check if restored image is there and ok
                                if os.path.isdir('amp/image_00'):
                                    selfcaltargetbeamsampimagestats[minc, :] = imstats.getimagestats(self, 'amp/image_00')
                                    if qa.checkrestoredimage(self, 'amp/image_00'):
                                        selfcaltargetbeamsampimagestatus[minc] = True
                                    else:
                                        selfcaltargetbeamsampimagestatus[minc] = False
                                        selfcaltargetbeamsampstatus = False
                                        logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(minc) + ' is invalid. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsampfinalminor = minc
                                        break
                                else:
                                    selfcaltargetbeamsampimagestatus[minc] = False
                                    selfcaltargetbeamsampstatus = False
                                    logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(minc) + ' not found. Stopping self-calibration!')
                                    stop = True
                                    selfcaltargetbeamsampfinalminor = minc
                                    break
                                restor.mode = 'residual'  # Create the residual image
                                restor.out = 'amp/residual_00'
                                restor.go()
                                residualstats = imstats.getimagestats(self, 'amp/residual_00')  # Min, max, rms of the residual image
                                selfcaltargetbeamsampresidualstats[minc, :] = residualstats
                                currdr = dirtystats[1] / residualstats[1]
                                logger.info('Beam ' + self.beam + ': Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(minc))
                                selfcaltargetbeamsampfinalminor = minc
                                if Mth[1] == 'TN':
                                    TNreached = True
                                    logger.info('Beam ' + self.beam + ': Theoretical noise threshold reached. Using last model for final self-calibration!')
                                else:
                                    TNreached = False
                            else:
                                TNdr = masking.calc_theoretical_noise_dr(dirtystats[1], TN, self.selfcal_amp_nsigma)  # Theoretical noise dynamic range
                                DRdr = masking.calc_dynamic_range_dr(mindr_list, minc, self.selfcal_amp_mindr)  # Dynamic range dynamic range
                                Ndr = masking.calc_noise_dr(minc, phasemajor+1, self.selfcal_amp_c0)  # Noise dynamic range
                                TNth = masking.calc_theoretical_noise_threshold(dirtystats[1], TNdr)  # Theoretical noise threshold
                                DRth = masking.calc_dynamic_range_threshold(dirtystats[1], DRdr)  # Dynamic range threshold
                                Nth = masking.calc_noise_threshold(dirtystats[1], Ndr)  # Noise threshold
                                Mth = masking.calc_mask_threshold(TNth, Nth, DRth)  # Masking threshold
                                Cc = masking.calc_clean_cutoff(Mth[0], self.selfcal_phase_c1)  # Clean cutoff
                                selfcaltargetbeamsampmaskthreshold[minc] = Mth[0]
                                selfcaltargetbeamsampthresholdtype[minc] = Mth[1]
                                selfcaltargetbeamsampcleanthreshold[minc] = Cc
                                masking.create_mask(self, 'amp/image_' + str(minc - 1).zfill(2), 'amp/mask_' + str(minc).zfill(2), Mth[0], TN, beampars=None)
                                # Check if mask is there and ok
                                if os.path.isdir('amp/mask_' + str(minc).zfill(2)):
                                    selfcaltargetbeamsampmaskstats[minc, :] = imstats.getmaskstats(self, 'amp/mask_' + str(minc).zfill(2), self.selfcal_image_imsize)
                                    if qa.checkmaskimage(self, 'amp/mask_' + str(minc).zfill(2)):
                                        selfcaltargetbeamsampmaskstatus[minc] = True
                                    else:
                                        selfcaltargetbeamsampmaskstatus[minc] = False
                                        selfcaltargetbeamsampstatus = False
                                        logger.error('Beam ' + self.beam + ': Mask image for cycle ' + str(minc) + ' is invalid. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsampfinalminor = minc
                                        break
                                else:
                                    selfcaltargetbeamsampmaskstatus[minc] = False
                                    selfcaltargetbeamsampstatus = False
                                    logger.error('Beam ' + self.beam + ': Mask image for cycle ' + str(minc) + ' not found. Stopping self-calibration!')
                                    stop = True
                                    selfcaltargetbeamsampfinalminor = minc
                                    break
                                mfclean = lib.miriad('mfclean')  # Clean the image down to the calculated threshold
                                mfclean.map = 'amp/map_00'
                                mfclean.beam = 'amp/beam_00'
                                mfclean.model = 'amp/model_' + str(minc - 1).zfill(2)
                                mfclean.out = 'amp/model_' + str(minc).zfill(2)
                                mfclean.cutoff = Cc
                                mfclean.niters = 1000000
                                mfclean.region = '"' + 'mask(amp/mask_' + str(minc).zfill(2) + ')' + '"'
                                mfclean.go()
                                # Check if clean component image is there and ok
                                if os.path.isdir('amp/model_' + str(minc).zfill(2)):
                                    selfcaltargetbeamsampmodelstats[minc, :] = imstats.getmodelstats(self, 'amp/model_' + str(minc).zfill(2))
                                    if qa.checkmodelimage(self, 'amp/model_' + str(minc).zfill(2)):
                                        selfcaltargetbeamsampmodelstatus[minc] = True
                                    else:
                                        selfcaltargetbeamsampmodelstatus[minc] = False
                                        selfcaltargetbeamsampstatus = False
                                        logger.error('Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' is invalid. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsampfinalminor = minc
                                        break
                                else:
                                    selfcaltargetbeamsampmodelstatus[minc] = False
                                    selfcaltargetbeamsampstatus = False
                                    logger.error('Beam ' + self.beam + ': Clean component image for cycle ' + str(minc) + ' not found. Stopping self-calibration!')
                                    stop = True
                                    selfcaltargetbeamsampfinalminor = minc
                                    break
                                restor = lib.miriad('restor')  # Create the restored image
                                restor.model = 'amp/model_' + str(minc).zfill(2)
                                restor.beam = 'amp/beam_00'
                                restor.map = 'amp/map_00'
                                restor.out = 'amp/image_' + str(minc).zfill(2)
                                restor.mode = 'clean'
                                restor.go()
                                # Check if restored image is there and ok
                                if os.path.isdir('amp/image_' + str(minc).zfill(2)):
                                    selfcaltargetbeamsampimagestats[minc, :] = imstats.getimagestats(self, 'amp/image_00')
                                    if qa.checkrestoredimage(self, 'amp/image_' + str(minc).zfill(2)):
                                        selfcaltargetbeamsampimagestatus[minc] = True
                                    else:
                                        selfcaltargetbeamsampimagestatus[minc] = False
                                        selfcaltargetbeamsampstatus = False
                                        logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(minc) + ' is invalid. Stopping self-calibration!')
                                        stop = True
                                        selfcaltargetbeamsampfinalminor = minc
                                        break
                                else:
                                    selfcaltargetbeamsampimagestatus[minc] = False
                                    selfcaltargetbeamsampstatus = False
                                    logger.error('Beam ' + self.beam + ': Restored image for cycle ' + str(minc) + ' not found. Stopping self-calibration!')
                                    stop = True
                                    selfcaltargetbeamsampfinalminor = minc
                                    break
                                restor.mode = 'residual'  # Create the residual image
                                restor.out = 'amp/residual_' + str(minc).zfill(2)
                                restor.go()
                                residualstats = imstats.getimagestats(self, 'amp/residual_' + str(minc).zfill(2))  # Min, max, rms of the residual image
                                selfcaltargetbeamsampresidualstats[minc, :] = residualstats
                                currdr = dirtystats[1] / residualstats[1]
                                logger.info('Beam ' + self.beam + ': Dynamic range is ' + '%.3f' % currdr + ' for cycle ' + str(minc))
                                selfcaltargetbeamsampfinalminor = minc
                                if Mth[1] == 'TN':
                                    TNreached = True
                                    logger.info('Beam ' + self.beam + ': Theoretical noise threshold reached. Using last model for final self-calibration!')
                                else:
                                    TNreached = False
                        else: # If theoretical noise has been reached
                            break
                    if not stop:
                        if not TNreached:
                            logger.warning('Beam ' + self.beam + ': Theoretical noise limit not reached for final amplitude self-calibration model! Your model might be incomplete!')
                        else:
                            pass
                        # Do the amplitude self calibration if everything worked ok
                        selfcal = lib.miriad('selfcal')
                        selfcal.vis = self.target.rstrip('.mir') + '_amp.mir'
                        selfcal.select = '"' + 'uvrange(' + str(self.selfcal_amp_uvmin) + ',' + str(self.selfcal_amp_uvmax) + ')"'
                        selfcal.model = 'amp/model_' + str(selfcaltargetbeamsampfinalminor).zfill(2)
                        if self.selfcal_amp_solint == 'auto':
                            selfcal.interval = calc_scal_interval(selfcaltargetbeamsampmodelstats[selfcaltargetbeamsampfinalminor, 1], TN, 720, 66, self.selfcal_amp_nfbin, 2, 10.0, phasemajor + 1)
                        else:
                            selfcal.interval = self.selfcal_amp_solint
                        if self.selfcal_refant == '':  # Choose reference antenna if given
                            pass
                        else:
                            selfcal.refant = self.selfcal_refant
                        selfcal.options = 'amp,mfs'
                        selfcal.nfbin = self.selfcal_amp_nfbin
                        selfcal.go()
                        if qa.checkimagegaussianity(self, 'amp/residual_' + str(selfcaltargetbeamsampfinalminor).zfill(2), self.selfcal_amp_gaussianity):
                            selfcaltargetbeamsampresidualstatus = True
                        else:
                            selfcaltargetbeamsampresidualstatus = False
                            logger.error('Beam ' + self.beam + ': Final residual image shows non-gaussian statistics. Amplitude self-calibration was not successful!')
                        invert = lib.miriad('invert')  # Create a dirty image after final calibration and compare statistics to original one for qualtiy assurance
                        invert.vis = self.target.rstrip('.mir') + '_amp.mir'
                        invert.map = 'amp/check_map'
                        invert.beam = 'amp/check_beam'
                        invert.imsize = self.selfcal_image_imsize
                        invert.cell = self.selfcal_image_cellsize
                        invert.stokes = 'i'
                        invert.options = 'mfs,sdb,double'
                        invert.slop = 1
                        invert.robust = -2
                        invert.go()
                        checkstats = imstats.getimagestats(self, 'amp/check_map')
                        subs_managefiles.director(self, 'rm', 'amp/check_map')
                        subs_managefiles.director(self, 'rm', 'amp/check_beam')
                        if np.abs(checkstats[0])/np.abs(dirtystats[0]) >= self.selfcal_amp_ratio or np.abs(dirtystats[0])/np.abs(checkstats[0]) >= self.selfcal_amp_ratio:
                            minok = False
                            logger.error('Beam ' + self.beam + ': Discrepeancy between minimum flux of dirty image before and after selfcal!')
                        else:
                            minok = True
                        if np.abs(checkstats[1])/np.abs(dirtystats[1]) >= self.selfcal_amp_ratio or np.abs(dirtystats[1])/np.abs(checkstats[1]) >= self.selfcal_amp_ratio:
                            maxok = False
                            logger.error('Beam ' + self.beam + ': Discrepeancy between maximum flux of dirty image before and after selfcal!')
                        else:
                            maxok = True
                        if np.abs(checkstats[2])/np.abs(dirtystats[2]) >= self.selfcal_amp_ratio or np.abs(dirtystats[2])/np.abs(checkstats[2]) >= self.selfcal_amp_ratio:
                            stdok = False
                            logger.error('Beam ' + self.beam + ': Discrepeancy between standard deviation of dirty image before and after selfcal!')
                        else:
                            stdok = True
                        if minok == False or maxok == False or stdok == False:
                            selfcaltargetbeamsampstatus = False
                            logger.error('Beam ' + self.beam + ': Amplitude self-calibration was not successful!')
                        else:
                            selfcaltargetbeamsampstatus = True
                            logger.info('Beam ' + self.beam + ': Amplitude self-calibration was successful!')
                    else:
                        selfcaltargetbeamsampstatus = False
                        logger.error('Beam ' + self.beam + ': Amplitude self-calibration was not successful!')
                else:
                    selfcaltargetbeamsampapplystatus = False
                    selfcaltargetbeamsampstatus = False
                    logger.error('Beam ' + self.beam + ': Phase self-calibration gains were not applied successfully! Stopping amplitude self-calibration!')
            else:
                selfcaltargetbeamsampstatus = False
                logger.error('Beam ' + self.beam + ': Phase self-calibration was not successful! Cannot do amplitude self-calibration!')

        # Save the derived parameters to the parameter file

        subs_param.add_param(self, beam + '_targetbeams_amp_status', selfcaltargetbeamsampstatus)
        subs_param.add_param(self, beam + '_targetbeams_amp_applystatus', selfcaltargetbeamsampapplystatus)
        subs_param.add_param(self, beam + '_targetbeams_amp_mapstatus', selfcaltargetbeamsampmapstatus)
        subs_param.add_param(self, beam + '_targetbeams_amp_mapstats', selfcaltargetbeamsampmapstats)
        subs_param.add_param(self, beam + '_targetbeams_amp_beamstatus', selfcaltargetbeamsampbeamstatus)
        subs_param.add_param(self, beam + '_targetbeams_amp_maskstatus', selfcaltargetbeamsampmaskstatus)
        subs_param.add_param(self, beam + '_targetbeams_amp_maskstats', selfcaltargetbeamsampmaskstats)
        subs_param.add_param(self, beam + '_targetbeams_amp_modelstatus', selfcaltargetbeamsampmodelstatus)
        subs_param.add_param(self, beam + '_targetbeams_amp_modelstats', selfcaltargetbeamsampmodelstats)
        subs_param.add_param(self, beam + '_targetbeams_amp_imagestatus', selfcaltargetbeamsampimagestatus)
        subs_param.add_param(self, beam + '_targetbeams_amp_imagestats', selfcaltargetbeamsampimagestats)
        subs_param.add_param(self, beam + '_targetbeams_amp_residualstatus', selfcaltargetbeamsampresidualstatus)
        subs_param.add_param(self, beam + '_targetbeams_amp_residualstats', selfcaltargetbeamsampresidualstats)
        subs_param.add_param(self, beam + '_targetbeams_amp_maskthreshold', selfcaltargetbeamsampmaskthreshold)
        subs_param.add_param(self, beam + '_targetbeams_amp_cleanthreshold', selfcaltargetbeamsampcleanthreshold)
        subs_param.add_param(self, beam + '_targetbeams_amp_thresholdtype', selfcaltargetbeamsampthresholdtype)
        subs_param.add_param(self, beam + '_targetbeams_amp_final_minorcycle', selfcaltargetbeamsampfinalminor)


    def show(self, showall=False):
        lib.show(self, 'SELFCAL', showall)


    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during SELFCAL. No detailed summary
        is available for SELFCAL up to now.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        """

        # Load the parameters from the parameter file

        AV = np.full((self.NBEAMS), False)
        FL = np.full((self.NBEAMS), False)
        PA = np.full((self.NBEAMS), False)
        PH = np.full((self.NBEAMS), False)
        AM = np.full((self.NBEAMS), False)

        for beam in range(self.NBEAMS):
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            beam = 'selfcal_B' + str(self.beam).zfill(2)
            AV[beam] = subs_param.get_param(self, beam + '_targetbeams_average')
            FL[beam] = subs_param.get_param(self, beam + '_targetbeams_flagline')
            PA[beam] = subs_param.get_param(self, beam + '_targetbeams_parametric')
            PH[beam] = subs_param.get_param(self, beam + '_targetbeams_phase_status')
            AM[beam] = subs_param.get_param(self, beam + '_targetbeams_amp_status')

        # Create the data frame

        beam_range = range(self.NBEAMS)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = dataset_beams

        df_average = pd.DataFrame(np.ndarray.flatten(AV), index=dataset_indices, columns=['Average data'])
        df_flagline = pd.DataFrame(np.ndarray.flatten(FL), index=dataset_indices, columns=['Flag RFI/line'])
        df_parametric = pd.DataFrame(np.ndarray.flatten(PA), index=dataset_indices, columns=['Parametric calibration'])
        df_phase = pd.DataFrame(np.ndarray.flatten(PH), index=dataset_indices, columns=['Phase calibration'])
        df_amp = pd.DataFrame(np.ndarray.flatten(AM), index=dataset_indices, columns=['Amplitude calibration'])

        df = pd.concat([df_average, df_flagline, df_parametric, df_phase, df_amp], axis=1)

        return df


    def reset(self):
        """
        Function to reset the current step and remove all generated selfcal data for the current beam. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        beam = 'selfcal_B' + str(self.beam).zfill(2)
        logger.warning('Beam ' + self.beam + ': Deleting all self-calibrated data.')
        subs_managefiles.director(self, 'rm', self.selfcaldir)
        subs_param.del_param(self, beam + '_targetbeams_average')
        subs_param.del_param(self, beam + '_targetbeams_flagline')
        subs_param.del_param(self, beam + '_targetbeams_flagline_channels')
        subs_param.del_param(self, beam + '_targetbeams_parametric')
        subs_param.del_param(self, beam + '_targetbeams_phase_status')
        subs_param.del_param(self, beam + '_targetbeams_phase_mapstatus')
        subs_param.del_param(self, beam + '_targetbeams_phase_mapstats')
        subs_param.del_param(self, beam + '_targetbeams_phase_beamstatus')
        subs_param.del_param(self, beam + '_targetbeams_phase_maskstatus')
        subs_param.del_param(self, beam + '_targetbeams_phase_maskstats')
        subs_param.del_param(self, beam + '_targetbeams_phase_modelstatus')
        subs_param.del_param(self, beam + '_targetbeams_phase_modelstats')
        subs_param.del_param(self, beam + '_targetbeams_phase_imagestatus')
        subs_param.del_param(self, beam + '_targetbeams_phase_imagestats')
        subs_param.del_param(self, beam + '_targetbeams_phase_residualstatus')
        subs_param.del_param(self, beam + '_targetbeams_phase_residualstats')
        subs_param.del_param(self, beam + '_targetbeams_phase_maskthreshold')
        subs_param.del_param(self, beam + '_targetbeams_phase_cleanthreshold')
        subs_param.del_param(self, beam + '_targetbeams_phase_thresholdtype')
        subs_param.del_param(self, beam + '_targetbeams_phase_final_majorcycle')
        subs_param.del_param(self, beam + '_targetbeams_phase_final_minorcycle')
        subs_param.del_param(self, beam + '_targetbeams_amp_status')
        subs_param.del_param(self, beam + '_targetbeams_amp_applystatus')
        subs_param.del_param(self, beam + '_targetbeams_amp_mapstatus')
        subs_param.del_param(self, beam + '_targetbeams_amp_mapstats')
        subs_param.del_param(self, beam + '_targetbeams_amp_beamstatus')
        subs_param.del_param(self, beam + '_targetbeams_amp_maskstatus')
        subs_param.del_param(self, beam + '_targetbeams_amp_maskstats')
        subs_param.del_param(self, beam + '_targetbeams_amp_modelstatus')
        subs_param.del_param(self, beam + '_targetbeams_amp_modelstats')
        subs_param.del_param(self, beam + '_targetbeams_amp_imagestatus')
        subs_param.del_param(self, beam + '_targetbeams_amp_imagestats')
        subs_param.del_param(self, beam + '_targetbeams_amp_residualstatus')
        subs_param.del_param(self, beam + '_targetbeams_amp_residualstats')
        subs_param.del_param(self, beam + '_targetbeams_amp_maskthreshold')
        subs_param.del_param(self, beam + '_targetbeams_amp_cleanthreshold')
        subs_param.del_param(self, beam + '_targetbeams_amp_thresholdtype')
        subs_param.del_param(self, beam + '_targetbeams_amp_final_minorcycle')


    def reset_all(self):
        """
        Function to reset the current step and remove all generated selfcal data for the all beams. Be careful! Deletes all data generated in
        this step!
        """
        for beam in range(self.NBEAMS):
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            beam = 'selfcal_B' + str(self.beam).zfill(2)
            logger.warning('Beam ' + self.beam + ': Deleting all self-calibrated data.')
            subs_managefiles.director(self, 'rm', self.selfcaldir)
            subs_param.del_param(self, beam + '_targetbeams_average')
            subs_param.del_param(self, beam + '_targetbeams_flagline')
            subs_param.del_param(self, beam + '_targetbeams_flagline_channels')
            subs_param.del_param(self, beam + '_targetbeams_parametric')
            subs_param.del_param(self, beam + '_targetbeams_phase_status')
            subs_param.del_param(self, beam + '_targetbeams_phase_mapstatus')
            subs_param.del_param(self, beam + '_targetbeams_phase_mapstats')
            subs_param.del_param(self, beam + '_targetbeams_phase_beamstatus')
            subs_param.del_param(self, beam + '_targetbeams_phase_maskstatus')
            subs_param.del_param(self, beam + '_targetbeams_phase_maskstats')
            subs_param.del_param(self, beam + '_targetbeams_phase_modelstatus')
            subs_param.del_param(self, beam + '_targetbeams_phase_modelstats')
            subs_param.del_param(self, beam + '_targetbeams_phase_imagestatus')
            subs_param.del_param(self, beam + '_targetbeams_phase_imagestats')
            subs_param.del_param(self, beam + '_targetbeams_phase_residualstatus')
            subs_param.del_param(self, beam + '_targetbeams_phase_residualstats')
            subs_param.del_param(self, beam + '_targetbeams_phase_maskthreshold')
            subs_param.del_param(self, beam + '_targetbeams_phase_cleanthreshold')
            subs_param.del_param(self, beam + '_targetbeams_phase_thresholdtype')
            subs_param.del_param(self, beam + '_targetbeams_phase_final_majorcycle')
            subs_param.del_param(self, beam + '_targetbeams_phase_final_minorcycle')
            subs_param.del_param(self, beam + '_targetbeams_amp_status')
            subs_param.del_param(self, beam + '_targetbeams_amp_applystatus')
            subs_param.del_param(self, beam + '_targetbeams_amp_mapstatus')
            subs_param.del_param(self, beam + '_targetbeams_amp_mapstats')
            subs_param.del_param(self, beam + '_targetbeams_amp_beamstatus')
            subs_param.del_param(self, beam + '_targetbeams_amp_maskstatus')
            subs_param.del_param(self, beam + '_targetbeams_amp_maskstats')
            subs_param.del_param(self, beam + '_targetbeams_amp_modelstatus')
            subs_param.del_param(self, beam + '_targetbeams_amp_modelstats')
            subs_param.del_param(self, beam + '_targetbeams_amp_imagestatus')
            subs_param.del_param(self, beam + '_targetbeams_amp_imagestats')
            subs_param.del_param(self, beam + '_targetbeams_amp_residualstatus')
            subs_param.del_param(self, beam + '_targetbeams_amp_residualstats')
            subs_param.del_param(self, beam + '_targetbeams_amp_maskthreshold')
            subs_param.del_param(self, beam + '_targetbeams_amp_cleanthreshold')
            subs_param.del_param(self, beam + '_targetbeams_amp_thresholdtype')
            subs_param.del_param(self, beam + '_targetbeams_amp_final_minorcycle')
