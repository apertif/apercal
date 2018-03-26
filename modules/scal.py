__author__ = "Bradley Frank, Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "frank@astron.nl, adebahr@astron.nl"

import ConfigParser
import logging
import sys

import aipy
import astropy.io.fits as pyfits
import numpy as np
import os

import subs.setinit
import subs.managefiles

from libs import lib
from subs import lsm


####################################################################################################

class scal:
    '''
    Selfcal class to do the self-calibration on a dataset. Can be done with several different algorithms.
    '''
    def __init__(self, file=None, **kwargs):
#        logging.basicConfig(level=20)
        self.logger = logging.getLogger('SELFCAL')
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        self.default = config # Save the loaded config file as defaults for later usage
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)

    ############################################################
    ##### Function to execute the self-calibration process #####
    ############################################################

    def go(self):
        '''
        Executes the whole self-calibration process in the following order:
        splitdata
        flagline
        parametric
        selfcal_standard
        '''
        self.logger.info("########## Starting SELF CALIBRATION ##########")
        self.splitdata()
        self.flagline()
        self.parametric()
        self.selfcal_standard()
        self.logger.info("########## SELF CALIBRATION done ##########")

    def splitdata(self):
        '''
        Applies calibrator corrections to data, splits the data into chunks in frequency and bins it to the given frequency resolution for the self-calibration
        '''
        if self.splitdata:
            subs.setinit.setinitdirs(self)
            subs.setinit.setdatasetnamestomiriad(self)
            subs.managefiles.director(self, 'ch', self.selfcaldir)
            self.logger.info('### Splitting of target data into individual frequency chunks started ###')
            if os.path.isfile(self.selfcaldir + '/' + self.target):
                self.logger.info('# Calibrator corrections already seem to have been applied #')
            else:
                self.logger.info('# Applying calibrator solutions to target data before averaging #')
                uvaver = lib.miriad('uvaver')
                uvaver.vis = self.crosscaldir + '/' + self.target
                uvaver.out = self.selfcaldir + '/' + self.target
                uvaver.go()
                self.logger.info('# Calibrator solutions to target data applied #')
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
                self.logger.error('### No data in your crosscal directory! Exiting pipeline! ###')
                sys.exit(1)
            try:
                nsubband = len(uv['nschan']) # Number of subbands in data
            except TypeError:
                nsubband = 1 # Only one subband in data since exception was triggered
            self.logger.info('# Found ' + str(nsubband) + ' subband(s) in target data #')
            counter = 0 # Counter for naming the chunks and directories
            for subband in range(nsubband):
                self.logger.info('# Started splitting of subband ' + str(subband) + ' #')
                if nsubband == 1:
                    numchan = uv['nschan']
                    finc = np.fabs(uv['sdf'])
                else:
                    numchan = uv['nschan'][subband] # Number of channels per subband
                    finc = np.fabs(uv['sdf'][subband])  # Frequency increment for each channel
                subband_bw = numchan * finc # Bandwidth of one subband
                subband_chunks = round(subband_bw / self.selfcal_splitdata_chunkbandwidth)
                subband_chunks = int(np.power(2, np.ceil(np.log(subband_chunks) / np.log(2)))) # Round to the closest power of 2 for frequency chunks with the same bandwidth over the frequency range of a subband
                if subband_chunks == 0:
                    subband_chunks = 1
                chunkbandwidth = (numchan/subband_chunks)*finc
                self.logger.info('# Adjusting chunk size to ' + str(chunkbandwidth) + ' GHz for regular gridding of the data chunks over frequency #')
                for chunk in range(subband_chunks):
                    self.logger.info('# Starting splitting of data chunk ' + str(chunk) + ' for subband ' + str(subband) + ' #')
                    binchan = round(self.selfcal_splitdata_channelbandwidth / finc)  # Number of channels per frequency bin
                    chan_per_chunk = numchan / subband_chunks
                    if chan_per_chunk % binchan == 0: # Check if the freqeuncy bin exactly fits
                        self.logger.info('# Using frequency binning of ' + str(self.selfcal_splitdata_channelbandwidth) + ' for all subbands #')
                    else:
                        while chan_per_chunk % binchan != 0: # Increase the frequency bin to keep a regular grid for the chunks
                            binchan = binchan + 1
                        else:
                            if chan_per_chunk >= binchan: # Check if the calculated bin is not larger than the subband channel number
                                pass
                            else:
                                binchan = chan_per_chunk # Set the frequency bin to the number of channels in the chunk of the subband
                        self.logger.info('# Increasing frequency bin of data chunk ' + str(chunk) + ' to keep bandwidth of chunks equal over the whole bandwidth #')
                        self.logger.info('# New frequency bin is ' + str(binchan * finc) + ' GHz #')
                    nchan = int(chan_per_chunk/binchan) # Total number of output channels per chunk
                    start = 1 + chunk * chan_per_chunk
                    width = int(binchan)
                    step = int(width)
                    subs.managefiles.director(self, 'mk', self.selfcaldir + '/' + str(counter).zfill(2))
                    uvaver = lib.miriad('uvaver')
                    uvaver.vis = self.selfcaldir + '/' + self.target
                    uvaver.out = self.selfcaldir + '/' + str(counter).zfill(2) + '/' + str(counter).zfill(2) + '.mir'
                    uvaver.select = "'" + 'window(' + str(subband+1) + ')' + "'"
                    uvaver.line = "'" + 'channel,' + str(nchan) + ',' + str(start) + ',' + str(width) + ',' + str(step) + "'"
                    uvaver.go()
                    counter = counter + 1
                    self.logger.info('# Splitting of data chunk ' + str(chunk) + ' for subband ' + str(subband) + ' done #')
                self.logger.info('# Splitting of data for subband ' + str(subband) + ' done #')
            self.logger.info('### Splitting of target data into individual frequency chunks done ###')

    def flagline(self):
        '''
        Creates an image cube of the different chunks and measures the rms in each channel. All channels with an rms outside of a given sigma interval are flagged in the continuum calibration, but are still used for line imaging.
        '''
        if self.selfcal_flagline:
            subs.setinit.setinitdirs(self)
            subs.setinit.setdatasetnamestomiriad(self)
            self.logger.info('### Automatic flagging of HI-line/RFI started ###')
            subs.managefiles.director(self, 'ch', self.selfcaldir)
            for chunk in self.list_chunks():
                subs.managefiles.director(self, 'ch', self.selfcaldir + '/' + str(chunk))
                self.logger.info('# Looking through data chunk ' + str(chunk) + ' #')
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
                    std = np.nanstd(data, axis=(0,2,3))
                    median = np.median(std)
                    stdall = np.nanstd(std)
                    diff = std-median
                    detections = np.where(np.abs(self.selfcal_flagline_sigma * diff) > stdall)[0]
                    if len(detections) > 0:
                        self.logger.info('# Found high noise in channel(s) ' + str(detections).lstrip('[').rstrip(']') + ' #')
                        for d in detections:
                            uvflag = lib.miriad('uvflag')
                            uvflag.vis = chunk + '.mir'
                            uvflag.flagval = 'flag'
                            uvflag.line = "'" + 'channel,1,' + str(d+1) + "'"
                            uvflag.go()
                        self.logger.info('# Flagged channel(s) ' + str(detections).lstrip('[').rstrip(']') + ' in data chunk ' + str(chunk) + ' #')
                    else:
                        self.logger.info('# No high noise found in data chunk ' + str(chunk) + ' #')
                    subs.managefiles.director(self, 'rm', self.selfcaldir + '/' + str(chunk) + '/' + 'map')
                    subs.managefiles.director(self, 'rm', self.selfcaldir + '/' + str(chunk) + '/' + 'map.fits')
                    subs.managefiles.director(self, 'rm', self.selfcaldir + '/' + str(chunk) + '/' + 'beam')
                else:
                    self.logger.info('### No data in chunk ' + str(chunk) + '! ###')
            self.logger.info('### Automatic flagging of HI-line/RFI done ###')

    def parametric(self):
        '''
        Parametric self calibration using an NVSS/FIRST skymodel and calculating spectral indices by source matching with WENSS.
        '''
        if self.selfcal_parametric:
            subs.setinit.setinitdirs(self)
            subs.setinit.setdatasetnamestomiriad(self)
            self.logger.info('### Doing parametric self calibration ###')
            subs.managefiles.director(self, 'ch', self.selfcaldir)
            for chunk in self.list_chunks():
                self.logger.info('# Starting parametric self calibration routine on chunk ' + chunk + ' #')
                subs.managefiles.director(self, 'ch', self.selfcaldir + '/' + chunk)
                subs.managefiles.director(self, 'mk', self.selfcaldir + '/' + chunk + '/' + 'pm')
                parametric_textfile = lsm.lsm_model(chunk + '.mir', self.selfcal_parametric_skymodel_radius, self.selfcal_parametric_skymodel_cutoff, self.selfcal_parametric_skymodel_distance)
                lsm.write_model(self.selfcaldir + '/' + chunk + '/' + 'pm' + '/model.txt', parametric_textfile)
                self.logger.info('# Creating model from textfile model.txt for chunk ' + chunk + ' #')
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
                    uvmodel.flux = source.split(',')[2] + ',i,' + str(freq) + ',' + source.split(',')[4].rstrip('\n') + ',0,0'
                    uvmodel.out = 'pm/tmp' + str(n)
                    uvmodel.go()
                    uvmodel.vis = uvmodel.out
                subs.managefiles.director(self, 'rn', 'pm/model', uvmodel.out) # Rename the last modelfile to model
                subs.managefiles.director(self, 'rm', 'pm/tmp*') # Remove all the obsolete modelfiles
                self.logger.info('# Doing parametric self-calibration on chunk ' + chunk + ' with solution interval ' + str(self.selfcal_parametric_solint) + ' min and uvrange limits of ' + str(self.selfcal_parametric_uvmin) + '~' + str(self.selfcal_parametric_uvmax) + ' klambda #')
                selfcal = lib.miriad('selfcal')
                selfcal.vis = chunk + '.mir'
                selfcal.model = 'pm/model'
                selfcal.interval = self.selfcal_parametric_solint
                selfcal.select = "'" + 'uvrange(' + str(self.selfcal_parametric_uvmin) + ',' + str(self.selfcal_parametric_uvmax) + ')' + "'"
                if self.selfcal_parametric_amp:
                    selfcal.options = 'mfs,amp'
                else:
                    selfcal.options = 'mfs'
                selfcal.go()
                self.logger.info('# Parametric self calibration routine on chunk ' + chunk + ' done! #')
            self.logger.info('### Parametric self calibration done ###')
        else:
            self.logger.info('### Parametric self calibration disabled ###')

    def selfcal_standard(self):
        '''
        Executes the standard method of self-calibration with the given parameters
        '''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        self.logger.info('### Starting standard self calibration routine ###')
        subs.managefiles.director(self, 'ch', self.selfcaldir)
        for chunk in self.list_chunks():
            self.logger.info('# Starting standard self-calibration routine on frequency chunk ' + chunk + ' #')
            subs.managefiles.director(self, 'ch', self.selfcaldir + '/' + chunk)
            if os.path.isfile(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir/visdata'):
                theoretical_noise = self.calc_theoretical_noise(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
                self.logger.info('# Theoretical noise for chunk ' + chunk + ' is ' + str(theoretical_noise) + ' Jy/beam #')
                theoretical_noise_threshold = self.calc_theoretical_noise_threshold(theoretical_noise)
                self.logger.info('# Your theoretical noise threshold will be ' + str(self.selfcal_standard_nsigma) + ' times the theoretical noise corresponding to ' + str(theoretical_noise_threshold) + ' Jy/beam #')
                dr_list = self.calc_dr_maj(self.selfcal_standard_drinit, self.selfcal_standard_dr0, self.selfcal_standard_majorcycle, self.selfcal_standard_majorcycle_function)
                self.logger.info('# Your dynamic range limits are set to ' + str(dr_list) + ' for the major self-calibration cycles #')
                for majc in range(self.selfcal_standard_majorcycle):
                    self.logger.info('# Major self-calibration cycle ' + str(majc) + ' for frequency chunk ' + chunk + ' started #')
                    subs.managefiles.director(self, 'mk', self.selfcaldir + '/' + str(chunk) + '/' + str(majc).zfill(2))
                    dr_minlist = self.calc_dr_min(dr_list, majc, self.selfcal_standard_minorcycle, self.selfcal_standard_minorcycle_function)  # Calculate the dynamic ranges during minor cycles
                    self.logger.info('# The minor cycle dynamic range limits for major cycle ' + str(majc) + ' are ' + str(dr_minlist) + ' #')
                    for minc in range(self.selfcal_standard_minorcycle):
                        try:
                            self.run_continuum_minoriteration(chunk, majc, minc, dr_minlist[minc], theoretical_noise_threshold)
                        except:
                            self.logger.warning('# Chunk ' + chunk + ' does not seem to contain data to image #')
                            break
                    try:
                        self.logger.info('# Doing self-calibration with uvmin=' + str(self.selfcal_standard_uvmin[majc]) + ', uvmax=' + str(self.selfcal_standard_uvmax[majc]) + ', solution interval=' + str(self.selfcal_standard_solint[majc]) + ' minutes for major cycle ' + str(majc).zfill(2) + ' #')
                        selfcal = lib.miriad('selfcal')
                        selfcal.vis = chunk + '.mir'
                        selfcal.select = '"' + 'uvrange(' + str(self.selfcal_standard_uvmin[majc]) + ',' + str(self.selfcal_standard_uvmax[majc]) + ')"'
                        selfcal.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                        selfcal.interval = self.selfcal_standard_solint[majc]
                        if self.selfcal_standard_amp == False: # See if we want to do amplitude calibration
                            selfcal.options = 'mfs,phase'
                        elif self.selfcal_standard_amp == True:
                            selfcal.options = 'mfs,amp'
                        elif self.selfcal_standard_amp == 'auto':
                            modelflux = self.calc_isum(str(majc).zfill(2) + '/model_' + str(minc).zfill(2))
                            if modelflux >= self.selfcal_standard_amp_auto_limit:
                                self.logger.info('# Flux of clean model is ' + str(modelflux) + ' Jy. Doing amplitude calibration. #')
                                selfcal.options = 'mfs,amp'
                            else:
                                selfcal.options = 'mfs,phase'
                        selfcal.refant = '5'
                        if self.selfcal_standard_nfbin >= 1:
                            selfcal.nfbin = self.selfcal_standard_nfbin
                        selfcal.go()
                        self.logger.info('# Major self-calibration cycle ' + str(majc) + ' for frequency chunk ' + chunk + ' finished #')
                    except:
                        self.logger.warning('# Model for self-calibration not found. No further calibration on this chunk possible!')
                        break
                self.logger.info('# Standard self-calibration routine for chunk ' + chunk + ' finished #')
            else:
                self.logger.warning('# No data in chunk ' + chunk + '. Maybe all data is flagged? #')
        self.logger.info('### Standard self calibration routine finished ###')

    ############################################################
    ### Subroutines for the different self calibration modes ###
    ############################################################

    def run_continuum_minoriteration(self, chunk, majc, minc, drmin, theoretical_noise_threshold):
        '''
        Does a selfcal minor iteration for the standard mode
        chunk: The frequency chunk to image and calibrate
        maj: Current major iteration
        min: Current minor iteration
        drmin: maximum dynamic range for minor iteration
        theoretical_noise_threshold: calculated theoretical noise threshold
        '''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        self.logger.info('# Minor self-calibration cycle ' + str(minc) + ' for frequency chunk ' + chunk + ' started #')
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
            dynamic_range_threshold = self.calc_dynamic_range_threshold(imax, drmin, self.selfcal_standard_minorcycle0_dr)
            mask_threshold, mask_threshold_type = self.calc_mask_threshold(theoretical_noise_threshold, noise_threshold, dynamic_range_threshold)
            self.logger.info('# Mask threshold for major/minor cycle ' + str(majc) + '/' + str(minc) + ' set to ' + str(mask_threshold) + ' Jy/beam #')
            self.logger.info('# Mask threshold set by ' + str(mask_threshold_type) + ' #')
            if majc == 0:
                maths = lib.miriad('maths')
                maths.out = str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)
                maths.exp = '"<' + str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '>"'
                maths.mask = '"<' + str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
                maths.go()
                self.logger.info('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
            else:
                subs.managefiles.director(self, 'cp', str(majc).zfill(2) + '/mask_' + str(minc).zfill(2), file=str(majc - 1).zfill(2) + '/mask_' + str(self.selfcal_standard_minorcycle - 1).zfill(2))
                self.logger.info('# Mask from last minor iteration of last major cycle copied #')
            clean_cutoff = self.calc_clean_cutoff(mask_threshold)
            self.logger.info('# Clean threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' was set to ' + str(clean_cutoff) + ' Jy/beam #')
            clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
            clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
            clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
            clean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
            clean.cutoff = clean_cutoff
            clean.niters = 1000000
            clean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(minc).zfill(2) + ')' + '"'
            clean.go()
            self.logger.info('# Major/minor cycle ' + str(majc) + '/' + str(minc) + ' cleaning done #')
            restor = lib.miriad('restor')
            restor.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
            restor.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
            restor.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
            restor.out = str(majc).zfill(2) + '/image_' + str(minc).zfill(2)
            restor.mode = 'clean'
            restor.go()  # Create the cleaned image
            self.logger.info('# Cleaned image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
            restor.mode = 'residual'
            restor.out = str(majc).zfill(2) + '/residual_' + str(minc).zfill(2)
            restor.go()
            self.logger.info('# Residual image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
            self.logger.info('# Peak of the residual image is ' + str(self.calc_imax(str(majc).zfill(2) + '/residual_' + str(minc).zfill(2))) + ' Jy/beam #')
            self.logger.info('# RMS of the residual image is ' + str(self.calc_irms(str(majc).zfill(2) + '/residual_' + str(minc).zfill(2))) + ' Jy/beam #')
        else:
            imax = self.calc_imax(str(majc).zfill(2) + '/map_' + str(0).zfill(2))
            noise_threshold = self.calc_noise_threshold(imax, minc, majc)
            dynamic_range_threshold = self.calc_dynamic_range_threshold(imax, drmin, self.selfcal_standard_minorcycle0_dr)
            mask_threshold, mask_threshold_type = self.calc_mask_threshold(theoretical_noise_threshold, noise_threshold, dynamic_range_threshold)
            self.logger.info('# Mask threshold for major/minor cycle ' + str(majc) + '/' + str(minc) + ' set to ' + str(mask_threshold) + ' Jy/beam #')
            self.logger.info('# Mask threshold set by ' + str(mask_threshold_type) + ' #')
            maths = lib.miriad('maths')
            maths.out = str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)
            maths.exp = '"<' + str(majc).zfill(2) + '/image_' + str(minc - 1).zfill(2) + '>"'
            maths.mask = '"<' + str(majc).zfill(2) + '/image_' + str(minc - 1).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
            maths.go()
            self.logger.info('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
            clean_cutoff = self.calc_clean_cutoff(mask_threshold)
            self.logger.info('# Clean threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' was set to ' + str(clean_cutoff) + ' Jy/beam #')
            clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
            clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
            clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
            clean.model = str(majc).zfill(2) + '/model_' + str(minc - 1).zfill(2)
            clean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
            clean.cutoff = clean_cutoff
            clean.niters = 1000000
            clean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(minc).zfill(2) + ')' + '"'
            clean.go()
            self.logger.info('# Major/minor cycle ' + str(majc) + '/' + str(minc) + ' cleaning done #')
            restor = lib.miriad('restor')
            restor.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
            restor.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
            restor.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
            restor.out = str(majc).zfill(2) + '/image_' + str(minc).zfill(2)
            restor.mode = 'clean'
            restor.go()  # Create the cleaned image
            self.logger.info('# Cleaned image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
            restor.mode = 'residual'
            restor.out = str(majc).zfill(2) + '/residual_' + str(minc).zfill(2)
            restor.go()
            self.logger.info('# Residual image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
            self.logger.info('# Peak of the residual image is ' + str(self.calc_imax(str(majc).zfill(2) + '/residual_' + str(minc).zfill(2))) + ' Jy/beam #')
            self.logger.info('# RMS of the residual image is ' + str(self.calc_irms(str(majc).zfill(2) + '/residual_' + str(minc).zfill(2))) + ' Jy/beam #')
        self.logger.info('# Minor self-calibration cycle ' + str(minc) + ' for frequency chunk ' + chunk + ' finished #')

    ###################################################################
    ### Subfunctions used in the different self calibration options ###
    ###################################################################

    def create_parametric_mask(self, dataset, radius, cutoff, cat, outputdir):
        '''
        Creates a parametric mask using a model from an input catalogue.
        dataset (string): The dataset to get the coordiantes for the model from.
        radius (float): The radius around the pointing centre of the input dataset to consider sources in in deg.
        cutoff (float): The apparent flux percentage to consider sources from 0.0 accounts for no sources, 1.0 for all sources in the catalogue within the search radius of the target field.
        cat (string): The catalogue to search sources in. Possible options are 'NVSS', 'FIRST', and 'WENSS'.
        outputdir (string): The output directory to create the MIRIAD mask file in. The file is named mask.
        '''
        lsm.write_mask(outputdir + '/mask.txt', lsm.lsm_mask(dataset, radius, cutoff, cat))
        mskfile = open(outputdir + '/mask.txt', 'r')
        object = mskfile.readline().rstrip('\n')
        spar = mskfile.readline()
        mskfile.close()
        imgen = lib.miriad('imgen')
        imgen.imsize = self.selfcal_image_imsize
        imgen.cell = self.selfcal_image_cellsize
        imgen.object = object
        imgen.spar = spar
        imgen.out = outputdir + '/imgen'
        imgen.go()
        maths = lib.miriad('maths')
        maths.exp = '"<' + outputdir + '/imgen' + '>"'
        maths.mask = '"<' + outputdir + '/imgen>.gt.1e-6' + '"'
        maths.out = outputdir + '/mask'
        maths.go()
        subs.managefiles.director(self, 'rm', outputdir + '/imgen')
        self.single_mskcutoff = 1e-6
        subs.managefiles.director(self, 'rm', outputdir + '/mask.txt')

    def calc_irms(self, image):
        '''
        Function to calculate the maximum of an image
        image (string): The name of the image file. Must be in MIRIAD-format
        returns (float): the maximum in the image
        '''
        fits = lib.miriad('fits')
        fits.op = 'xyout'
        fits.in_ = image
        fits.out = image + '.fits'
        fits.go()
        image_data = pyfits.open(image + '.fits')  # Open the image
        data = image_data[0].data
        imax = np.nanstd(data) # Get the standard deviation
        image_data.close() # Close the image
        subs.managefiles.director(self, 'rm', image + '.fits')
        return imax

    def calc_imax(self, image):
        '''
        Function to calculate the maximum of an image
        image (string): The name of the image file. Must be in MIRIAD-format
        returns (float): the maximum in the image
        '''
        fits = lib.miriad('fits')
        fits.op = 'xyout'
        fits.in_ = image
        fits.out = image + '.fits'
        fits.go()
        image_data = pyfits.open(image + '.fits')  # Open the image
        data = image_data[0].data
        imax = np.nanmax(data) # Get the maximum
        image_data.close() # Close the image
        subs.managefiles.director(self, 'rm', image + '.fits')
        return imax

    def calc_isum(self, image):
        '''
        Function to calculate the sum of the values of the pixels in an image
        image (string): The name of the image file. Must be in MIRIAD-format
        returns (float): the sum of the pxiels in the image
                '''
        fits = lib.miriad('fits')
        fits.op = 'xyout'
        fits.in_ = image
        fits.out = image + '.fits'
        fits.go()
        image_data = pyfits.open(image + '.fits')  # Open the image
        data = image_data[0].data
        isum = np.nansum(data)  # Get the maximum
        image_data.close()  # Close the image
        subs.managefiles.director(self, 'rm', image + '.fits')
        return isum

    def calc_dr_maj(self, drinit, dr0, majorcycles, function):
        '''
        Function to calculate the dynamic range limits during major cycles
        drinit (float): The initial dynamic range
        dr0 (float): Coefficient for increasing the dynamic range threshold at each major cycle
        majorcycles (int): The number of major cycles to execute
        function (string): The function to follow for increasing the dynamic ranges. Currently 'power' is supported.
        returns (list of floats): A list of floats for the dynamic range limits within the major cycles.
        '''
        if function == 'square':
            dr_maj = [drinit * np.power(dr0, m) for m in range(majorcycles)]
        else:
            self.logger.error('### Function for major cycles not supported! Exiting! ###')
            sys.exit(1)
        return dr_maj

    def calc_dr_min(self, dr_maj, majc, minorcycles, function):
        '''
        Function to calculate the dynamic range limits during minor cycles
        dr_maj (list of floats): List with dynamic range limits for major cycles. Usually from calc_dr_maj
        majc (int): The major cycles you want to calculate the minor cycle dynamic ranges for
        minorcycles (int): The number of minor cycles to use
        function (string): The function to follow for increasing the dynamic ranges. Currently 'square', 'power', and 'linear' is supported.
        returns (list of floats): A list of floats for the dynamic range limits within the minor cycles.
        '''
        if majc == 0: # Take care about the first major cycle
            prevdr = 0
        else:
            prevdr = dr_maj[majc-1]
        # The different options to increase the minor cycle threshold
        if function == 'square':
            dr_min = [prevdr + ((dr_maj[majc] - prevdr) * (n ** 2.0)) / ((minorcycles - 1) ** 2.0) for n in range(minorcycles)]
        elif function == 'power':
            dr_min = [prevdr + np.power((dr_maj[majc] - prevdr),(1.0/(n))) for n in range(minorcycles)][::-1] # Not exactly need to work on this, but close
        elif function == 'linear':
            dr_min = [(prevdr + ((dr_maj[majc] - prevdr) / (minorcycles-1)) * n) for n in range(minorcycles)]
        else:
            self.logger.error('### Function for minor cycles not supported! Exiting! ###')
            sys.exit(1)
        if dr_min[0] == 0:
            dr_min[0] = self.selfcal_standard_minorcycle0_dr
        else:
            pass
        return dr_min

    def calc_mask_threshold(self,theoretical_noise_threshold, noise_threshold, dynamic_range_threshold):
        '''
        Function to calculate the actual mask_threshold and the type of mask threshold from the theoretical noise threshold, noise threshold, and the dynamic range threshold
        theoretical_noise_threshold (float): The theoretical noise threshold calculated by calc_theoretical_noise_threshold
        noise_threshold (float): The noise threshold calculated by calc_noise_threshold
        dynamic_range_threshold (float): The dynamic range threshold calculated by calc_dynamic_range_threshold
        returns (float, string): The maximum of the three thresholds, the type of the maximum threshold
        '''
        # if np.isinf(dynamic_range_threshold) or np.isnan(dynamic_range_threshold):
        #     dynamic_range_threshold = noise_threshold
        mask_threshold = np.max([theoretical_noise_threshold, noise_threshold, dynamic_range_threshold])
        mask_argmax = np.argmax([theoretical_noise_threshold, noise_threshold, dynamic_range_threshold])
        if mask_argmax == 0:
            mask_threshold_type = 'Theoretical noise threshold'
        elif mask_argmax == 1:
            mask_threshold_type = 'Noise threshold'
        elif mask_argmax == 2:
            mask_threshold_type = 'Dynamic range threshold'
        return mask_threshold, mask_threshold_type

    def calc_noise_threshold(self, imax, minor_cycle, major_cycle):
        '''
        Calculates the noise threshold
        imax (float): the maximum in the input image
        minor_cycle (int): the current minor cycle the self-calibration is in
        major_cycle (int): the current major cycle the self-calibration is in
        returns (float): the noise threshold
        '''
        noise_threshold = imax / ((self.selfcal_standard_c0 + (minor_cycle) * self.selfcal_standard_c0) * (major_cycle + 1))
        return noise_threshold

    def calc_clean_cutoff(self, mask_threshold):
        '''
        Calculates the cutoff for the cleaning
        mask_threshold (float): the mask threshold to calculate the clean cutoff from
        returns (float): the clean cutoff
        '''
        clean_cutoff = mask_threshold / self.selfcal_standard_c1
        return clean_cutoff

    def calc_dynamic_range_threshold(self, imax, dynamic_range, dynamic_range_minimum):
        '''
        Calculates the dynamic range threshold
        imax (float): the maximum in the input image
        dynamic_range (float): the dynamic range you want to calculate the threshold for
        returns (float): the dynamic range threshold
        '''
        if dynamic_range == 0:
            dynamic_range = dynamic_range_minimum
        dynamic_range_threshold = imax / dynamic_range
        return dynamic_range_threshold

    def calc_theoretical_noise_threshold(self, theoretical_noise):
        '''
        Calculates the theoretical noise threshold from the theoretical noise
        theoretical_noise (float): the theoretical noise of the observation
        returns (float): the theoretical noise threshold
        '''
        theoretical_noise_threshold = (self.selfcal_standard_nsigma * theoretical_noise)
        return theoretical_noise_threshold

    def calc_theoretical_noise(self, dataset):
        '''
        Calculate the theoretical rms of a given dataset
        dataset (string): The input dataset to calculate the theoretical rms from
        returns (float): The theoretical rms of the input dataset as a float
        '''
        uv = aipy.miriad.UV(dataset)
        obsrms = lib.miriad('obsrms')
        try:
            tsys = np.median(uv['systemp'])
            if np.isnan(tsys):
                obsrms.tsys = 30.0
            else:
                obsrms.tsys = tsys
        except KeyError:
            obsrms.tsys = 30.0
        obsrms.jyperk = uv['jyperk']
        obsrms.antdiam = 25
        obsrms.freq = uv['sfreq']
        obsrms.theta = 15
        obsrms.nants = uv['nants']
        obsrms.bw = np.abs(uv['sdf']*uv['nschan']) * 1000.0
        obsrms.inttime = 12.0 * 60.0
        obsrms.coreta = 0.88
        theorms = float(obsrms.go()[-1].split()[3])/1000.0
        return theorms

    ######################################################################
    ##### Subfunctions for managing the location and naming of files #####
    ######################################################################

    def list_chunks(self):
        '''
        Checks how many chunk directories exist and returns a list of them.
        '''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        for n in range(100):
            if os.path.exists(self.selfcaldir + '/' + str(n).zfill(2)):
                pass
            else:
                break # Stop the counting loop at the directory you cannot find anymore
        chunks = range(n)
        chunkstr = [str(i).zfill(2) for i in chunks]
        return chunkstr

    #######################################################################
    ##### Manage the creation and moving of new directories and files #####
    #######################################################################

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
                if s == 'SELFCAL':
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
        subs.setinit.setdatasetnamestomiriad(self)
        self.logger.warning('### Deleting all self-calibrated data. ###')
        subs.managefiles.director(self, 'ch', self.selfcaldir)
        subs.managefiles.director(self, 'rm', self.selfcaldir + '/*')