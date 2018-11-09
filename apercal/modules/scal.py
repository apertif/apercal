import logging

import aipy
import astropy.io.fits as pyfits
import numpy as np
import os

from apercal.libs.calculations import calc_dr_maj, calc_theoretical_noise, calc_dynamic_range_threshold, \
    calc_mask_threshold
from apercal.modules.base import BaseModule
from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles

from apercal.libs import lib
from apercal.subs import lsm

from apercal.exceptions import ApercalException

logger = logging.getLogger(__name__)


class scal(BaseModule):
    """
    Selfcal class to do the self-calibration on a dataset. Can be done with several different algorithms.
    """
    module_name = 'SELFCAL'

    selfcal_image_imsize = None
    selfcal_image_cellsize = None
    selfcal_refant = None
    selfcal_splitdata = None
    selfcal_splitdata_chunkbandwidth = None
    selfcal_splitdata_channelbandwidth = None
    selfcal_flagantenna = None
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
    selfcal_standard_majorcycle = None
    selfcal_standard_majorcycle_function = None
    selfcal_standard_minorcycle = None
    selfcal_standard_minorcycle_function = None
    selfcal_standard_c0 = None
    selfcal_standard_c1 = None
    selfcal_standard_minorcycle0_dr = None
    selfcal_standard_drinit = None
    selfcal_standard_dr0 = None
    selfcal_standard_nsigma = None
    selfcal_standard_uvmin = None
    selfcal_standard_uvmax = None
    selfcal_standard_solint = None
    selfcal_standard_amp = None
    selfcal_standard_amp_auto_limit = None
    selfcal_standard_nfbin = None

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
        splitdata
        flagline
        parametric
        selfcal_standard
        """
        logger.info("Starting SELF CALIBRATION ")
        self.splitdata()
        self.flagline()
        self.parametric()
        self.selfcal_standard()
        logger.info("SELF CALIBRATION done ")

    def splitdata(self):
        """
        Applies calibrator corrections to data, splits the data into chunks in frequency and bins it to the given
        frequency resolution for the self-calibration
        """
        if self.splitdata:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            subs_managefiles.director(self, 'ch', self.selfcaldir)
            logger.info(' Splitting of target data into individual frequency chunks started')
            if os.path.isfile(self.selfcaldir + '/' + self.target):
                logger.info('Calibrator corrections already seem to have been applied #')
            else:
                logger.info('Applying calibrator solutions to target data before averaging #')
                uvaver = lib.miriad('uvaver')
                uvaver.vis = self.crosscaldir + '/' + self.target
                uvaver.out = self.selfcaldir + '/' + self.target
                uvaver.go()
                logger.info('Calibrator solutions to target data applied #')
            if self.selfcal_flagantenna != '':
                uvflag = lib.miriad('uvflag')
                uvflag.vis = self.selfcaldir + '/' + self.target
                uvflag.flagval = 'flag'
                uvflag.select = 'antenna(' + str(self.selfcal_flagantenna) + ')'
                uvflag.go()
            else:
                pass
            try:
                uv = aipy.miriad.UV(self.selfcaldir + '/' + self.target)
            except RuntimeError:
                raise ApercalException(' No data in your crosscal directory!')

            try:
                nsubband = len(uv['nschan'])  # Number of subbands in data
            except TypeError:
                nsubband = 1  # Only one subband in data since exception was triggered
            logger.info('Found ' + str(nsubband) + ' subband(s) in target data #')
            counter = 0  # Counter for naming the chunks and directories
            for subband in range(nsubband):
                logger.info('Started splitting of subband ' + str(subband) + ' #')
                if nsubband == 1:
                    numchan = uv['nschan']
                    finc = np.fabs(uv['sdf'])
                else:
                    numchan = uv['nschan'][subband]  # Number of channels per subband
                    finc = np.fabs(uv['sdf'][subband])  # Frequency increment for each channel
                subband_bw = numchan * finc  # Bandwidth of one subband
                subband_chunks = round(subband_bw / self.selfcal_splitdata_chunkbandwidth)
                # Round to the closest power of 2 for frequency chunks with the same bandwidth over the frequency
                # range of a subband
                subband_chunks = int(np.power(2, np.ceil(np.log(subband_chunks) / np.log(2))))
                if subband_chunks == 0:
                    subband_chunks = 1
                chunkbandwidth = (numchan / subband_chunks) * finc
                logger.info('Adjusting chunk size to ' + str(
                    chunkbandwidth) + ' GHz for regular gridding of the data chunks over frequency #')
                for chunk in range(subband_chunks):
                    logger.info(
                        'Starting splitting of data chunk ' + str(chunk) + ' for subband ' + str(subband) + ' #')
                    binchan = round(
                        self.selfcal_splitdata_channelbandwidth / finc)  # Number of channels per frequency bin
                    chan_per_chunk = numchan / subband_chunks
                    if chan_per_chunk % binchan == 0:  # Check if the freqeuncy bin exactly fits
                        logger.info('Using frequency binning of ' + str(
                            self.selfcal_splitdata_channelbandwidth) + ' for all subbands #')
                    else:
                        # Increase the frequency bin to keep a regular grid for the chunks
                        while chan_per_chunk % binchan != 0:
                            binchan = binchan + 1
                        else:
                            # Check if the calculated bin is not larger than the subband channel number
                            if chan_per_chunk >= binchan:
                                pass
                            else:
                                # Set the frequency bin to the number of channels in the chunk of the subband
                                binchan = chan_per_chunk
                        logger.info('Increasing frequency bin of data chunk ' + str(
                            chunk) + ' to keep bandwidth of chunks equal over the whole bandwidth #')
                        logger.info('New frequency bin is ' + str(binchan * finc) + ' GHz #')
                    nchan = int(chan_per_chunk / binchan)  # Total number of output channels per chunk
                    start = 1 + chunk * chan_per_chunk
                    width = int(binchan)
                    step = int(width)
                    subs_managefiles.director(self, 'mk', self.selfcaldir + '/' + str(counter).zfill(2))
                    uvaver = lib.miriad('uvaver')
                    uvaver.vis = self.selfcaldir + '/' + self.target
                    uvaver.out = self.selfcaldir + '/' + str(counter).zfill(2) + '/' + str(counter).zfill(2) + '.mir'
                    uvaver.select = "'" + 'window(' + str(subband + 1) + ')' + "'"
                    uvaver.line = "'" + 'channel,' + str(nchan) + ',' + str(start) + ',' + str(width) + ',' + str(
                        step) + "'"
                    uvaver.go()
                    counter = counter + 1
                    logger.info('Splitting of data chunk ' + str(chunk) + ' for subband ' + str(subband) + ' done #')
                logger.info('Splitting of data for subband ' + str(subband) + ' done #')
            logger.info(' Splitting of target data into individual frequency chunks done')

    def flagline(self):
        """
        Creates an image cube of the different chunks and measures the rms in each channel. All channels with an rms
        outside of a given sigma interval are flagged in the continuum calibration, but are still used for line imaging.
        """
        if self.selfcal_flagline:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            logger.info(' Automatic flagging of HI-line/RFI started')
            subs_managefiles.director(self, 'ch', self.selfcaldir)
            for chunk in self.list_chunks():
                subs_managefiles.director(self, 'ch', self.selfcaldir + '/' + str(chunk))
                logger.info('Looking through data chunk ' + str(chunk) + ' #')
                invert = lib.miriad('invert')
                invert.vis = chunk + '.mir'
                invert.map = 'map'
                invert.beam = 'beam'
                invert.imsize = self.selfcal_image_imsize
                invert.cell = self.selfcal_image_cellsize
                invert.stokes = 'ii'
                invert.slop = 1
                invert.go()
                if os.path.exists('map'):
                    fits = lib.miriad('fits')
                    fits.in_ = 'map'
                    fits.op = 'xyout'
                    fits.out = 'map.fits'
                    fits.go()
                    cube = pyfits.open('map.fits')
                    data = cube[0].data
                    std = np.nanstd(data, axis=(0, 2, 3))
                    median = np.median(std)
                    stdall = np.nanstd(std)
                    diff = std - median
                    detections = np.where(np.abs(self.selfcal_flagline_sigma * diff) > stdall)[0]
                    if len(detections) > 0:
                        logger.info('Found high noise in channel(s) ' + str(detections).lstrip('[').rstrip(']') + ' #')
                        for d in detections:
                            uvflag = lib.miriad('uvflag')
                            uvflag.vis = chunk + '.mir'
                            uvflag.flagval = 'flag'
                            uvflag.line = "'" + 'channel,1,' + str(d + 1) + "'"
                            uvflag.go()
                        logger.info(
                            'Flagged channel(s) ' + str(detections).lstrip('[').rstrip(']') + ' in data chunk ' + str(
                                chunk) + ' #')
                    else:
                        logger.info('No high noise found in data chunk ' + str(chunk) + ' #')
                    subs_managefiles.director(self, 'rm', self.selfcaldir + '/' + str(chunk) + '/' + 'map')
                    subs_managefiles.director(self, 'rm', self.selfcaldir + '/' + str(chunk) + '/' + 'map.fits')
                    subs_managefiles.director(self, 'rm', self.selfcaldir + '/' + str(chunk) + '/' + 'beam')
                else:
                    logger.info(' No data in chunk ' + str(chunk) + '!')
            logger.info(' Automatic flagging of HI-line/RFI done')

    def parametric(self):
        """
        Parametric self calibration using an NVSS/FIRST skymodel and calculating spectral indices by source matching
        with WENSS.
        """
        if self.selfcal_parametric:
            subs_setinit.setinitdirs(self)
            subs_setinit.setdatasetnamestomiriad(self)
            logger.info(' Doing parametric self calibration')
            subs_managefiles.director(self, 'ch', self.selfcaldir)
            for chunk in self.list_chunks():
                logger.info('Starting parametric self calibration routine on chunk ' + chunk + ' #')
                subs_managefiles.director(self, 'ch', self.selfcaldir + '/' + chunk)
                subs_managefiles.director(self, 'mk', self.selfcaldir + '/' + chunk + '/' + 'pm')
                parametric_textfile = lsm.lsm_model(chunk + '.mir', self.selfcal_parametric_skymodel_radius,
                                                    self.selfcal_parametric_skymodel_cutoff,
                                                    self.selfcal_parametric_skymodel_distance)
                lsm.write_model(self.selfcaldir + '/' + chunk + '/' + 'pm' + '/model.txt', parametric_textfile)
                logger.info('Creating model from textfile model.txt for chunk ' + chunk + ' #')
                uv = aipy.miriad.UV(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
                freq = uv['sfreq']
                uvmodel = lib.miriad('uvmodel')
                uvmodel.vis = chunk + '.mir'
                parametric_modelfile = open(self.selfcaldir + '/' + str(chunk) + '/' + 'pm' + '/model.txt', 'r')
                for n, source in enumerate(parametric_modelfile.readlines()):
                    if n == 0:
                        uvmodel.options = 'replace,mfs'
                    else:
                        uvmodel.options = 'add,mfs'
                    uvmodel.offset = source.split(',')[0] + ',' + source.split(',')[1]
                    uvmodel.flux = source.split(',')[2] + ',i,' + str(freq) + ',' + source.split(',')[4].rstrip(
                        '\n') + ',0,0'
                    uvmodel.out = 'pm/tmp' + str(n)
                    uvmodel.go()
                    uvmodel.vis = uvmodel.out
                subs_managefiles.director(self, 'rn', 'pm/model', uvmodel.out)  # Rename the last modelfile to model
                subs_managefiles.director(self, 'rm', 'pm/tmp*')  # Remove all the obsolete modelfiles

                logger.info('Doing parametric self-calibration on chunk {} with solution interval {} min'
                            'and uvrange limits of {}~{} klambda #'.format(chunk, self.selfcal_parametric_solint,
                                                                           self.selfcal_parametric_uvmin,
                                                                           self.selfcal_parametric_uvmax))

                selfcal = lib.miriad('selfcal')
                selfcal.vis = chunk + '.mir'
                selfcal.model = 'pm/model'
                selfcal.interval = self.selfcal_parametric_solint
                selfcal.select = "'" + 'uvrange(' + str(self.selfcal_parametric_uvmin) + ',' + str(
                    self.selfcal_parametric_uvmax) + ')' + "'"
                # Choose reference antenna if given
                if self.selfcal_refant == '':
                    pass
                else:
                    selfcal.refant = self.selfcal_refant
                # Do amplitude calibration if wanted
                if self.selfcal_parametric_amp:
                    selfcal.options = 'mfs,amp'
                else:
                    selfcal.options = 'mfs'
                selfcal.go()
                logger.info('Parametric self calibration routine on chunk ' + chunk + ' done! #')
            logger.info(' Parametric self calibration done')
        else:
            logger.info(' Parametric self calibration disabled')

    def selfcal_standard(self):
        """
        Executes the standard method of self-calibration with the given parameters
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        logger.info(' Starting standard self calibration routine')
        subs_managefiles.director(self, 'ch', self.selfcaldir)
        for chunk in self.list_chunks():
            logger.info('Starting standard self-calibration routine on frequency chunk ' + chunk + ' #')
            subs_managefiles.director(self, 'ch', self.selfcaldir + '/' + chunk)
            if os.path.isfile(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir/visdata'):
                theoretical_noise = calc_theoretical_noise(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
                logger.info('Theoretical noise for chunk ' + chunk + ' is ' + str(theoretical_noise) + ' Jy/beam #')
                theoretical_noise_threshold = self.calc_theoretical_noise_threshold(theoretical_noise)
                logger.info('Your theoretical noise threshold will be ' + str(
                    self.selfcal_standard_nsigma) + ' times the theoretical noise corresponding to ' + str(
                    theoretical_noise_threshold) + ' Jy/beam #')
                dr_list = calc_dr_maj(self.selfcal_standard_drinit, self.selfcal_standard_dr0,
                                           self.selfcal_standard_majorcycle, self.selfcal_standard_majorcycle_function)
                logger.info(
                    'Your dynamic range limits are set to ' + str(dr_list) + ' for the major self-calibration cycles #')
                for majc in range(self.selfcal_standard_majorcycle):
                    logger.info(
                        'Major self-calibration cycle ' + str(majc) + ' for frequency chunk ' + chunk + ' started #')
                    subs_managefiles.director(self, 'mk', self.selfcaldir + '/' + str(chunk) + '/' + str(majc).zfill(2))
                    # Calculate the dynamic ranges during minor cycles
                    dr_minlist = self.calc_dr_min(dr_list, majc, self.selfcal_standard_minorcycle,
                                                  self.selfcal_standard_minorcycle_function)
                    logger.info('The minor cycle dynamic range limits for major cycle ' + str(majc) + ' are ' + str(
                        dr_minlist) + ' #')
                    for minc in range(self.selfcal_standard_minorcycle):
                        try:
                            self.run_continuum_minoriteration(chunk, majc, minc, dr_minlist[minc],
                                                              theoretical_noise_threshold)
                        except Exception:
                            logger.warning('Chunk ' + chunk + ' does not seem to contain data to image #')
                            break
                    try:
                        logger.info('Doing self-calibration with uvmin=' + str(
                            self.selfcal_standard_uvmin[majc]) + ', uvmax=' + str(
                            self.selfcal_standard_uvmax[majc]) + ', solution interval=' + str(
                            self.selfcal_standard_solint[majc]) + ' minutes for major cycle ' + str(majc).zfill(
                            2) + ' #')
                        selfcal = lib.miriad('selfcal')
                        selfcal.vis = chunk + '.mir'
                        selfcal.select = '"' + 'uvrange(' + str(self.selfcal_standard_uvmin[majc]) + ',' + str(
                            self.selfcal_standard_uvmax[majc]) + ')"'
                        selfcal.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                        selfcal.interval = self.selfcal_standard_solint[majc]
                        # Choose reference antenna if given
                        if self.selfcal_refant == '':
                            pass
                        else:
                            selfcal.refant = self.selfcal_refant
                        # Enable amplitude calibration if triggered
                        if not self.selfcal_standard_amp:  # See if we want to do amplitude calibration
                            selfcal.options = 'mfs,phase'
                        elif self.selfcal_standard_amp:
                            selfcal.options = 'mfs,amp'
                        elif self.selfcal_standard_amp == 'auto':
                            modelflux = self.calc_isum(str(majc).zfill(2) + '/model_' + str(minc).zfill(2))
                            if modelflux >= self.selfcal_standard_amp_auto_limit:
                                logger.info(
                                    'Flux of clean model is ' + str(modelflux) + ' Jy. Doing amplitude calibration. #')
                                selfcal.options = 'mfs,amp'
                            else:
                                selfcal.options = 'mfs,phase'
                        if self.selfcal_standard_nfbin >= 1:
                            selfcal.nfbin = self.selfcal_standard_nfbin
                        selfcal.go()
                        logger.info('Major self-calibration cycle ' + str(
                            majc) + ' for frequency chunk ' + chunk + ' finished #')
                    except Exception:
                        logger.warning(
                            'Model for self-calibration not found. No further calibration on this chunk possible!')
                        break
                logger.info('Standard self-calibration routine for chunk ' + chunk + ' finished #')
            else:
                logger.warning('No data in chunk ' + chunk + '. Maybe all data is flagged? #')
        logger.info(' Standard self calibration routine finished')

    def run_continuum_minoriteration(self, chunk, majc, minc, drmin, theoretical_noise_threshold):
        """
        Does a selfcal minor iteration for the standard mode
        chunk: The frequency chunk to image and calibrate
        maj: Current major iteration
        min: Current minor iteration
        drmin: maximum dynamic range for minor iteration
        theoretical_noise_threshold: calculated theoretical noise threshold
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        logger.info('Minor self-calibration cycle ' + str(minc) + ' for frequency chunk ' + chunk + ' started #')
        if minc == 0:
            invert = lib.miriad('invert')  # Create the dirty image
            invert.vis = chunk + '.mir'
            invert.map = str(majc).zfill(2) + '/map_' + str(minc).zfill(2)
            invert.beam = str(majc).zfill(2) + '/beam_' + str(minc).zfill(2)
            invert.imsize = self.selfcal_image_imsize
            invert.cell = self.selfcal_image_cellsize
            invert.stokes = 'ii'
            invert.options = 'mfs,double'
            invert.slop = 1
            invert.robust = -2
            invert.go()
            imax = self.calc_imax(str(majc).zfill(2) + '/map_' + str(minc).zfill(2))
            noise_threshold = self.calc_noise_threshold(imax, minc, majc)
            dynamic_range_threshold = calc_dynamic_range_threshold(imax, drmin,
                                                                        self.selfcal_standard_minorcycle0_dr)
            mask_threshold, mask_threshold_type = calc_mask_threshold(theoretical_noise_threshold, noise_threshold,
                                                                           dynamic_range_threshold)
            logger.info('Mask threshold for major/minor cycle ' + str(majc) + '/' + str(minc) + ' set to ' + str(
                mask_threshold) + ' Jy/beam #')
            logger.info('Mask threshold set by ' + str(mask_threshold_type) + ' #')
            if majc == 0:
                maths = lib.miriad('maths')
                maths.out = str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)
                maths.exp = '"<' + str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '>"'
                maths.mask = '"<' + str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '>.gt.' + str(
                    mask_threshold) + '"'
                maths.go()
                logger.info('Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
            else:
                subs_managefiles.director(self, 'cp', str(majc).zfill(2) + '/mask_' + str(minc).zfill(2),
                                          file_=str(majc - 1).zfill(2) + '/mask_' + str(
                                              self.selfcal_standard_minorcycle - 1).zfill(2))
                logger.info('Mask from last minor iteration of last major cycle copied #')
            clean_cutoff = self.calc_clean_cutoff(mask_threshold)
            logger.info('Clean threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' was set to ' + str(
                clean_cutoff) + ' Jy/beam #')
            clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
            clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
            clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
            clean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
            clean.cutoff = clean_cutoff
            clean.niters = 1000000
            clean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(minc).zfill(2) + ')' + '"'
            clean.go()
            logger.info('Major/minor cycle ' + str(majc) + '/' + str(minc) + ' cleaning done #')
            restor = lib.miriad('restor')
            restor.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
            restor.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
            restor.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
            restor.out = str(majc).zfill(2) + '/image_' + str(minc).zfill(2)
            restor.mode = 'clean'
            restor.go()  # Create the cleaned image
            logger.info('Cleaned image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
            restor.mode = 'residual'
            restor.out = str(majc).zfill(2) + '/residual_' + str(minc).zfill(2)
            restor.go()
            logger.info('Residual image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
            logger.info('Peak of the residual image is ' + str(
                self.calc_imax(str(majc).zfill(2) + '/residual_' + str(minc).zfill(2))) + ' Jy/beam #')
            logger.info('RMS of the residual image is ' + str(
                self.calc_irms(str(majc).zfill(2) + '/residual_' + str(minc).zfill(2))) + ' Jy/beam #')
        else:
            imax = self.calc_imax(str(majc).zfill(2) + '/map_' + str(0).zfill(2))
            noise_threshold = self.calc_noise_threshold(imax, minc, majc)
            dynamic_range_threshold = calc_dynamic_range_threshold(imax, drmin,
                                                                        self.selfcal_standard_minorcycle0_dr)
            mask_threshold, mask_threshold_type = calc_mask_threshold(theoretical_noise_threshold, noise_threshold,
                                                                           dynamic_range_threshold)
            logger.info('Mask threshold for major/minor cycle ' + str(majc) + '/' + str(minc) + ' set to ' + str(
                mask_threshold) + ' Jy/beam #')
            logger.info('Mask threshold set by ' + str(mask_threshold_type) + ' #')
            maths = lib.miriad('maths')
            maths.out = str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)
            maths.exp = '"<' + str(majc).zfill(2) + '/image_' + str(minc - 1).zfill(2) + '>"'
            maths.mask = '"<' + str(majc).zfill(2) + '/image_' + str(minc - 1).zfill(2) + '>.gt.' + str(
                mask_threshold) + '"'
            maths.go()
            logger.info('Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
            clean_cutoff = self.calc_clean_cutoff(mask_threshold)
            logger.info('Clean threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' was set to ' + str(
                clean_cutoff) + ' Jy/beam #')
            clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
            clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
            clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
            clean.model = str(majc).zfill(2) + '/model_' + str(minc - 1).zfill(2)
            clean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
            clean.cutoff = clean_cutoff
            clean.niters = 1000000
            clean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(minc).zfill(2) + ')' + '"'
            clean.go()
            logger.info('Major/minor cycle ' + str(majc) + '/' + str(minc) + ' cleaning done #')
            restor = lib.miriad('restor')
            restor.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
            restor.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
            restor.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
            restor.out = str(majc).zfill(2) + '/image_' + str(minc).zfill(2)
            restor.mode = 'clean'
            restor.go()  # Create the cleaned image
            logger.info('Cleaned image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
            restor.mode = 'residual'
            restor.out = str(majc).zfill(2) + '/residual_' + str(minc).zfill(2)
            restor.go()
            logger.info('Residual image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
            logger.info('Peak of the residual image is ' + str(
                self.calc_imax(str(majc).zfill(2) + '/residual_' + str(minc).zfill(2))) + ' Jy/beam #')
            logger.info('RMS of the residual image is ' + str(
                self.calc_irms(str(majc).zfill(2) + '/residual_' + str(minc).zfill(2))) + ' Jy/beam #')
        logger.info('Minor self-calibration cycle ' + str(minc) + ' for frequency chunk ' + chunk + ' finished #')

    def create_parametric_mask(self, dataset, radius, cutoff, cat, outputdir):
        """
        Creates a parametric mask using a model from an input catalogue.
        dataset (string): The dataset to get the coordiantes for the model from.
        radius (float): The radius around the pointing centre of the input dataset to consider sources in in deg.
        cutoff (float): The apparent flux percentage to consider sources from 0.0 accounts for no sources, 1.0 for all
                        sources in the catalogue within the search radius of the target field.
        cat (string): The catalogue to search sources in. Possible options are 'NVSS', 'FIRST', and 'WENSS'.
        outputdir (string): The output directory to create the MIRIAD mask file in. The file is named mask.
        """
        lsm.write_mask(outputdir + '/mask.txt', lsm.lsm_mask(dataset, radius, cutoff, cat))
        mskfile = open(outputdir + '/mask.txt', 'r')
        object_ = mskfile.readline().rstrip('\n')
        spar = mskfile.readline()
        mskfile.close()
        imgen = lib.miriad('imgen')
        imgen.imsize = self.selfcal_image_imsize
        imgen.cell = self.selfcal_image_cellsize
        imgen.object = object_
        imgen.spar = spar
        imgen.out = outputdir + '/imgen'
        imgen.go()
        maths = lib.miriad('maths')
        maths.exp = '"<' + outputdir + '/imgen' + '>"'
        maths.mask = '"<' + outputdir + '/imgen>.gt.1e-6' + '"'
        maths.out = outputdir + '/mask'
        maths.go()
        subs_managefiles.director(self, 'rm', outputdir + '/imgen')
        subs_managefiles.director(self, 'rm', outputdir + '/mask.txt')

    def calc_irms(self, image):
        """
        Function to calculate the maximum of an image
        image (string): The name of the image file. Must be in MIRIAD-format
        returns (float): the maximum in the image
        """
        fits = lib.miriad('fits')
        fits.op = 'xyout'
        fits.in_ = image
        fits.out = image + '.fits'
        fits.go()
        image_data = pyfits.open(image + '.fits')  # Open the image
        data = image_data[0].data
        imax = np.nanstd(data)  # Get the standard deviation
        image_data.close()  # Close the image
        subs_managefiles.director(self, 'rm', image + '.fits')
        return imax

    def calc_imax(self, image):
        """
        Function to calculate the maximum of an image
        image (string): The name of the image file. Must be in MIRIAD-format
        returns (float): the maximum in the image
        """
        fits = lib.miriad('fits')
        fits.op = 'xyout'
        fits.in_ = image
        fits.out = image + '.fits'
        fits.go()
        image_data = pyfits.open(image + '.fits')  # Open the image
        data = image_data[0].data
        imax = np.nanmax(data)  # Get the maximum
        image_data.close()  # Close the image
        subs_managefiles.director(self, 'rm', image + '.fits')
        return imax

    def calc_isum(self, image):
        """
        Function to calculate the sum of the values of the pixels in an image
        image (string): The name of the image file. Must be in MIRIAD-format
        returns (float): the sum of the pxiels in the image
                """
        fits = lib.miriad('fits')
        fits.op = 'xyout'
        fits.in_ = image
        fits.out = image + '.fits'
        fits.go()
        image_data = pyfits.open(image + '.fits')  # Open the image
        data = image_data[0].data
        isum = np.nansum(data)  # Get the maximum
        image_data.close()  # Close the image
        subs_managefiles.director(self, 'rm', image + '.fits')
        return isum

    def calc_dr_min(self, dr_maj, majc, minorcycles, function_):
        """
        Function to calculate the dynamic range limits during minor cycles
        dr_maj (list of floats): List with dynamic range limits for major cycles. Usually from calc_dr_maj
        majc (int): The major cycles you want to calculate the minor cycle dynamic ranges for
        minorcycles (int): The number of minor cycles to use
        function_ (string): The function to follow for increasing the dynamic ranges. Currently 'square', 'power', and
                           'linear' is supported.
        returns (list of floats): A list of floats for the dynamic range limits within the minor cycles.
        """
        if majc == 0:  # Take care about the first major cycle
            prevdr = 0
        else:
            prevdr = dr_maj[majc - 1]
        # The different options to increase the minor cycle threshold
        if function_ == 'square':
            dr_min = [prevdr + ((dr_maj[majc] - prevdr) * (n ** 2.0)) / ((minorcycles - 1) ** 2.0) for n in
                      range(minorcycles)]
        elif function_ == 'power':
            dr_min = [prevdr + np.power((dr_maj[majc] - prevdr), (1.0 / n)) for n in range(minorcycles)][
                     ::-1]  # Not exactly need to work on this, but close
        elif function_ == 'linear':
            dr_min = [(prevdr + ((dr_maj[majc] - prevdr) / (minorcycles - 1)) * n) for n in range(minorcycles)]
        else:
            raise ApercalException(' Function for minor cycles not supported! Exiting!')
        if dr_min[0] == 0:
            dr_min[0] = self.selfcal_standard_minorcycle0_dr
        else:
            pass
        return dr_min

    def calc_noise_threshold(self, imax, minor_cycle, major_cycle):
        """
        Calculates the noise threshold
        imax (float): the maximum in the input image
        minor_cycle (int): the current minor cycle the self-calibration is in
        major_cycle (int): the current major cycle the self-calibration is in
        returns (float): the noise threshold
        """
        noise_threshold = imax / (
                (self.selfcal_standard_c0 + minor_cycle * self.selfcal_standard_c0) * (major_cycle + 1))
        return noise_threshold

    def calc_clean_cutoff(self, mask_threshold):
        """
        Calculates the cutoff for the cleaning
        mask_threshold (float): the mask threshold to calculate the clean cutoff from
        returns (float): the clean cutoff
        """
        clean_cutoff = mask_threshold / self.selfcal_standard_c1
        return clean_cutoff

    def calc_theoretical_noise_threshold(self, theoretical_noise):
        """
        Calculates the theoretical noise threshold from the theoretical noise
        theoretical_noise (float): the theoretical noise of the observation
        returns (float): the theoretical noise threshold
        """
        theoretical_noise_threshold = (self.selfcal_standard_nsigma * theoretical_noise)
        return theoretical_noise_threshold

    def list_chunks(self):
        """
        Checks how many chunk directories exist and returns a list of them.
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        for n in range(100):
            if os.path.exists(self.selfcaldir + '/' + str(n).zfill(2)):
                pass
            else:
                break  # Stop the counting loop at the directory you cannot find anymore
        chunks = range(n)
        chunkstr = [str(i).zfill(2) for i in chunks]
        return chunkstr

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        logger.warning(' Deleting all self-calibrated data.')
        subs_managefiles.director(self, 'ch', self.selfcaldir)
        subs_managefiles.director(self, 'rm', self.selfcaldir + '/*')
