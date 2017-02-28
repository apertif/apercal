__author__ = "Bradley Frank, Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "frank@astron.nl, adebahr@astron.nl"

import lib
import logging
import os,sys
import ConfigParser
import lsm
import aipy
import numpy as np
import astropy.io.fits as pyfits

####################################################################################################

class scal:
    '''
    Selfcal class to do the self-calibration on a dataset. Can be done with several different algorithms.
    '''
    def __init__(self, file=None, **kwargs):
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

        # Create the directory names
        self.rawdir = self.basedir + self.rawsubdir
        self.crosscaldir = self.basedir + self.crosscalsubdir
        self.selfcaldir = self.basedir + self.selfcalsubdir
        self.linedir = self.basedir + self.linesubdir
        self.finaldir = self.basedir + self.finalsubdir

        # Name the datasets
        self.fluxcal = self.fluxcal.rstrip('MS') + 'mir'
        self.polcal = self.polcal.rstrip('MS') + 'mir'
        self.target = self.target.rstrip('MS') + 'mir'

    ############################################################
    ##### Function to execute the self-calibration process #####
    ############################################################

    def go(self):
        '''
        Executes the whole self-calibration process in the following order:
        splitdata
        flagline
        parametric
        executeselfcal
        '''
        self.logger.info("########## Starting SELF CALIBRATION ##########")
        self.splitdata()
        self.flagline()
        self.parametric()
        self.execute_selfcal()
        self.logger.info("########## SELF CALIBRATION done ##########")

    def splitdata(self):
        '''
        Applies calibrator corrections to data, splits the data into chunks in frequency and bins it to the given frequency resolution for the self-calibration
        '''
        if self.splitdata:
            self.director('ch', self.selfcaldir)
            self.logger.info('### Splitting of target data into individual freqeuncy chunks started ###')
            if os.path.isfile(self.selfcaldir + '/' + self.target):
                self.logger.info('# Calibrator corrections already seem to have been applied #')
            else:
                self.logger.info('# Applying calibrator solutions to target data before averaging #')
                uvaver = lib.miriad('uvaver')
                uvaver.vis = self.crosscaldir + '/' + self.target
                uvaver.out = self.selfcaldir + '/' + self.target
                uvaver.go()
                self.logger.info('# Calibrator solutions to target data applied #')
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
                    self.director('mk', self.selfcaldir + '/' + str(counter).zfill(2))
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
            self.logger.info('### Automatic flagging of HI-line/RFI started ###')
            self.director('ch', self.selfcaldir)
            for chunk in self.list_chunks():
                self.director('ch', self.selfcaldir + '/' + str(chunk))
                self.logger.info('# Looking through data chunk ' + str(chunk) + ' #')
                invert = lib.miriad('invert')
                invert.vis = chunk + '.mir'
                invert.map = 'map'
                invert.beam = 'beam'
                invert.imsize = self.selfcal_image_imsize
                invert.cellsize = self.selfcal_image_cellsize
                invert.stokes = 'i'
                invert.slop = 1
                invert.go()
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
                detections = np.where(self.selfcal_flagline_sigma * diff > stdall)[0]
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
                self.director('rm', self.selfcaldir + '/' + str(chunk) + '/' + 'map')
                self.director('rm', self.selfcaldir + '/' + str(chunk) + '/' + 'map.fits')
                self.director('rm', self.selfcaldir + '/' + str(chunk) + '/' + 'beam')
            self.logger.info('### Automatic flagging of HI-line/RFI done ###')

    def parametric(self):
        '''
        Parametric self calibration using an NVSS/FIRST skymodel and calculating spectral indices by source matching with WENSS.
        '''
        if self.selfcal_parametric:
            self.logger.info('### Doing parametric self calibration ###')
            self.director('ch', self.selfcaldir)
            for chunk in self.list_chunks():
                self.logger.info('# Starting parametric self calibration routine on chunk ' + chunk + ' #')
                self.director('ch', self.selfcaldir + '/' + chunk)
                self.director('mk', self.selfcaldir + '/' + chunk + '/' + 'pm')
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
                self.director('rn', 'pm/model', uvmodel.out) # Rename the last modelfile to model
                self.director('rm', 'pm/tmp*') # Remove all the obsolete modelfiles
                self.logger.info('# Doing parametric self-calibration on chunk ' + chunk + ' with solution interval ' + str(self.selfcal_parametric_solint) + ' min and uvrange limits of ' + str(self.selfcal_parametric_uvmin) + '~' + str(self.selfcal_parametric_uvmax) + ' klambda #')
                selfcal = lib.miriad('selfcal')
                selfcal.vis = chunk + '.mir'
                selfcal.model = 'pm/model'
                selfcal.interval = self.selfcal_parametric_solint
                selfcal.select = "'" + 'uvrange(' + str(self.selfcal_parametric_uvmin) + ',' + str(self.selfcal_parametric_uvmax) + ')' + "'"
                selfcal.go()
                self.logger.info('# Parametric self calibration routine on chunk ' + chunk + ' done! #')
            self.logger.info('### Parametric self calibration done ###')
        else:
            self.logger.info('### Parametric self calibration disabled ###')

    def execute_selfcal(self):
        '''
        Executes the self calibration with the mode set.
        '''
        self.director('ch', self.selfcaldir)
        if self.selfcal_mode == 'standard':
            self.selfcal_standard()
        elif self.selfcal_mode == 'manual':
            self.selfcal_manual()
        elif self.selfcal_mode == 'adaptive':
            self.selfcal_adaptive()
        else:
            self.logger.error('# Self-calibration mode not known. Exiting! #')
            sys.exit(1)

    #########################################################
    ### Routines for the different self calibration modes ###
    #########################################################

    def selfcal_standard(self):
        '''
        Executes the standard method of self-calibration with the given parameters as implemented by Nicolas Vilchez.
        '''
        self.logger.info('### Starting standard self calibration routine ###')
        self.director('ch', self.selfcaldir)
        for chunk in self.list_chunks():
            self.logger.info('# Starting standard self-calibration routine on chunk ' + chunk + ' #')
            self.director('ch', self.selfcaldir + '/' + chunk)
            theoretical_noise = self.calc_theoretical_noise(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
            self.logger.info('# Theoretical noise for chunk ' + chunk + ' is ' + str(theoretical_noise/1000) + ' Jy/beam #')
            for majc in range(self.selfcal_mode_standard_majorcycle):
                self.logger.info('# Major self-calibration cycle ' + str(majc) + ' for chunk ' + chunk + ' started #')
                self.director('mk', self.selfcaldir + '/' + str(chunk) + '/' + str(majc).zfill(2))
                for minc in range(self.selfcal_mode_standard_minorcycle):
                    self.logger.info('# Minor self-calibration cycle ' + str(minc) + ' for chunk ' + chunk + ' started #')
                    if minc == 0:
                        try:
                            invert = lib.miriad('invert') # Create the dirty image
                            invert.vis = chunk + '.mir'
                            invert.map = str(majc).zfill(2) + '/map_' + str(minc).zfill(2)
                            invert.beam = str(majc).zfill(2) + '/beam_' + str(minc).zfill(2)
                            invert.imsize = self.selfcal_image_imsize
                            invert.cell = self.selfcal_image_cellsize
                            invert.stokes = 'i'
                            invert.options = 'mfs,double'
                            invert.slop = 1
                            invert.go()
                            imax = self.calc_imax(str(majc).zfill(2) + '/map_' + str(minc).zfill(2))
                            self.logger.info('# Maximum value in the image at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(imax) + ' Jy/beam #')
                            self.logger.info('# Maximum value in the image at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(imax) + ' Jy/beam #')
                            self.director('rm', str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '.fits') # Remove the obsolete fits file
                            mask_threshold = self.calc_mask_threshold(imax, minc, majc)
                            self.logger.info('# Mask threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(mask_threshold) + ' Jy/beam #')
                            maths = lib.miriad('maths')
                            maths.out = str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)
                            maths.exp = '"<' + str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '>"'
                            maths.mask = '"<' + str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
                            maths.go()
                            self.logger.info('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
                            clean_noise_threshold = self.calc_clean_noise_threshold(imax, minc, majc)
                            self.logger.info('# Clean noise threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(clean_noise_threshold) + ' Jy/beam #')
                            dynamic_range_threshold = self.calc_dynamic_range_threshold(imax, majc)
                            self.logger.info('# Dynamic range threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(dynamic_range_threshold) + ' Jy/beam #')
                            clean_threshold = np.max([clean_noise_threshold, dynamic_range_threshold, theoretical_noise])
                            self.logger.info('# Clean threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' was set to ' + str(clean_threshold) + ' Jy/beam #')
                            clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                            clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                            clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                            clean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                            clean.cutoff = clean_threshold
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
                            self.logger.info('# Minor self-calibration cycle ' + str(minc) + ' for chunk ' + chunk + ' finished #')
                        except:
                            self.logger.warning('# Chunk ' + chunk + ' does not seem to contain data to image #')
                            break
                    else:
                        try:
                            imax = self.calc_imax(str(majc).zfill(2) + '/map_' + str(minc).zfill(2))
                            self.logger.info('# Maximum value in the image at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(imax) + ' Jy/beam #')
                            self.director('rm', str(majc).zfill(2) + '/residual_' + str(minc-1).zfill(2) + '.fits') # Remove the obsolete fits file
                            mask_threshold = self.calc_mask_threshold(imax, minc, majc)
                            self.logger.info('# Mask threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(mask_threshold) + ' Jy/beam #')
                            maths = lib.miriad('maths')
                            maths.out = str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)
                            maths.exp = '"<' + str(majc).zfill(2) + '/residual_' + str(minc-1).zfill(2) + '>"'
                            maths.mask = '"<' + str(majc).zfill(2) + '/residual_' + str(minc-1).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
                            maths.go()
                            self.logger.info('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
                            clean_noise_threshold = self.calc_clean_noise_threshold(imax, minc, majc)
                            self.logger.info('# Clean noise threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(clean_noise_threshold) + ' Jy/beam #')
                            dynamic_range_threshold = self.calc_dynamic_range_threshold(imax, majc)
                            self.logger.info('# Dynamic range threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(dynamic_range_threshold) + ' Jy/beam #')
                            clean_threshold = np.max([clean_noise_threshold, dynamic_range_threshold, theoretical_noise])
                            self.logger.info('# Clean threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' was set to ' + str(clean_threshold) + ' Jy/beam #')
                            clean = lib.miriad('clean') # Clean the image down to the calculated threshold
                            clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                            clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                            clean.model = str(majc).zfill(2) + '/model_' + str(minc-1).zfill(2)
                            clean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                            clean.cutoff = clean_threshold
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
                            restor.go() # Create the cleaned image
                            self.logger.info('# Cleaned image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
                            restor.mode = 'residual'
                            restor.out = str(majc).zfill(2) + '/residual_' + str(minc).zfill(2)
                            restor.go()
                            self.logger.info('# Residual image for major/minor cycle ' + str(majc) + '/' + str(minc) + ' created #')
                            self.logger.info('# Minor self-calibration cycle ' + str(minc) + ' for chunk ' + chunk + ' finished #')
                        except:
                            break
                    selfcal = lib.miriad('selfcal')
                    selfcal.vis = chunk + '.mir'
                    selfcal.select = '"' + 'uvrange(' + str(self.selfcal_mode_standard_uvmin[majc]) + ',' + str(self.selfcal_mode_standard_uvmax[majc]) + ')"'
                    selfcal.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                    selfcal.interval = self.selfcal_mode_standard_solint[majc]
                    selfcal.options = 'mfs,phase'
                    selfcal.refant = '5'
                    selfcal.go()
                self.logger.info('# Major self-calibration cycle ' + str(majc) + ' for chunk ' + chunk + ' finished #')
            self.logger.info('# Standard self-calibration routine for chunk ' + chunk + ' finished #')
        self.logger.info('### Standard self calibration routine finished ###')

    def selfcal_manual(self):
        '''
        Does the manual self-calibration with the given parameters.
        '''
        self.logger.info('### Starting manual self calibration routine ###')
        self.director('ch', self.selfcaldir)
        for chunk in self.list_chunks():
            self.logger.info('# Starting manual self-calibration routine on chunk ' + chunk + ' #')
            self.director('ch', self.selfcaldir + '/' + chunk)
            for majc in range(self.selfcal_mode_manual_majorcycle):
                self.logger.info('# Major self-calibration cycle ' + str(majc) + ' for chunk ' + chunk + ' started #')
                self.director('mk', self.selfcaldir + '/' + str(chunk) + '/' + str(majc).zfill(2))
                for minc in range(self.selfcal_mode_manual_minorcycle[majc]):
                    self.logger.info('# Minor self-calibration cycle ' + str(minc) + ' for chunk ' + chunk + ' started #')
                    if minc == 0:
                        invert = lib.miriad('invert') # Create the dirty image
                        invert.vis = chunk + '.mir'
                        invert.map = str(majc).zfill(2) + '/map_' + str(minc).zfill(2)
                        invert.beam = str(majc).zfill(2) + '/beam_' + str(minc).zfill(2)
                        invert.imsize = self.selfcal_image_imsize
                        invert.cell = self.selfcal_image_cellsize
                        invert.stokes = 'i'
                        invert.options = 'mfs,double'
                        invert.slop = 1
                        invert.go()
                        mask_threshold = self.selfcal_mode_manual_mskcutoff[majc][minc]
                        self.logger.info('# Mask threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(mask_threshold) + ' Jy/beam #')
                        maths = lib.miriad('maths')
                        maths.out = str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)
                        maths.exp = '"<' + str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '>"'
                        maths.mask = '"<' + str(majc).zfill(2) + '/map_' + str(minc).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
                        maths.go()
                        self.logger.info('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
                        clean = lib.miriad('clean')  # Clean the image down to the given threshold
                        clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                        clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                        clean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                        clean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(minc).zfill(2) + ')' + '"'
                        if self.selfcal_mode_manual_cleanstopcriterium[majc][minc] == 'both':
                            self.logger.info('# Using number of clean iterations as well as clean cutoff rms as stop criterium for clean #')
                            clean.cutoff = self.selfcal_mode_manual_cleancutoff[majc][minc]
                            self.logger.info('# Clean cutoff set to ' + str(self.selfcal_mode_manual_cleancutoff[majc][minc]) + ' Jy/beam #')
                            clean.niters = self.selfcal_mode_manual_niters[majc][minc]
                            self.logger.info('# Maximum number of clean iterations set to ' + str(self.selfcal_mode_manual_niters[majc][minc]) + ' #')
                        elif self.selfcal_mode_manual_cleanstopcriterium[majc][minc] == 'rms':
                            self.logger.info('# Using only clean cutoff rms as stop criterium for clean #')
                            clean.cutoff = self.selfcal_mode_manual_cleancutoff[majc][minc]
                            self.logger.info('# Clean cutoff set to ' + str(self.selfcal_mode_manual_cleancutoff[majc][minc]) + ' Jy/beam #')
                        elif self.selfcal_mode_manual_cleanstopcriterium[majc][minc] == 'niters':
                            self.logger.info('# Using only number of clean iterations as stop criterium for clean #')
                            clean.niters = self.selfcal_mode_manual_niters[majc][minc]
                            self.logger.info('# Maximum number of clean iterations set to ' + str(self.selfcal_mode_manual_niters[majc][minc]) + ' #')
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
                        self.logger.info('# Minor self-calibration cycle ' + str(minc) + ' for chunk ' + chunk + ' finished #')
                    else:
                        mask_threshold = self.selfcal_mode_manual_mskcutoff[majc][minc]
                        self.logger.info('# Mask threshold at major/minor cycle ' + str(majc) + '/' + str(minc) + ' is ' + str(mask_threshold) + ' Jy/beam #')
                        maths = lib.miriad('maths')
                        maths.out = str(majc).zfill(2) + '/mask_' + str(minc).zfill(2)
                        maths.exp = '"<' + str(majc).zfill(2) + '/residual_' + str(minc - 1).zfill(2) + '>"'
                        maths.mask = '"<' + str(majc).zfill(2) + '/residual_' + str(minc - 1).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
                        maths.go()
                        self.logger.info('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
                        clean = lib.miriad('clean')  # Clean the image down to the given threshold
                        clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                        clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                        clean.model = str(majc).zfill(2) + '/model_' + str(minc - 1).zfill(2)
                        clean.out = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                        clean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(minc).zfill(2) + ')' + '"'
                        if self.selfcal_mode_manual_cleanstopcriterium[majc][minc] == 'both':
                            self.logger.info('# Using number of clean iterations as well as clean cutoff rms as stop criterium for clean #')
                            clean.cutoff = self.selfcal_mode_manual_cleancutoff[majc][minc]
                            self.logger.info('# Clean cutoff set to ' + str(self.selfcal_mode_manual_cleancutoff[majc][minc]) + ' Jy/beam #')
                            clean.niters = self.selfcal_mode_manual_niters[majc][minc]
                            self.logger.info('# Maximum number of clean iterations set to ' + str(self.selfcal_mode_manual_niters[majc][minc]) + ' #')
                        elif self.selfcal_mode_manual_cleanstopcriterium[majc][minc] == 'rms':
                            self.logger.info('# Using only clean cutoff rms as stop criterium for clean #')
                            clean.cutoff = self.selfcal_mode_manual_cleancutoff[majc][minc]
                            self.logger.info('# Clean cutoff set to ' + str(self.selfcal_mode_manual_cleancutoff[majc][minc]) + ' Jy/beam #')
                            clean.niters = 1000000
                        elif self.selfcal_mode_manual_cleanstopcriterium[majc][minc] == 'niters':
                            self.logger.info('# Using only number of clean iterations as stop criterium for clean #')
                            clean.niters = self.selfcal_mode_manual_niters[majc][minc]
                            self.logger.info('# Maximum number of clean iterations set to ' + str(self.selfcal_mode_manual_niters[majc][minc]) + ' #')
                            clean.cutoff = 0.00000001
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
                        self.logger.info('# Minor self-calibration cycle ' + str(minc) + ' for chunk ' + chunk + ' finished #')
                selfcal = lib.miriad('selfcal')
                selfcal.vis = chunk + '.mir'
                selfcal.select = '"' + 'uvrange(' + str(self.selfcal_mode_manual_uvmin[majc]) + ',' + str(self.selfcal_mode_manual_uvmax[majc]) + ')"'
                selfcal.model = str(majc).zfill(2) + '/model_' + str(minc).zfill(2)
                selfcal.interval = self.selfcal_mode_manual_solint[majc]
                selfcal.options = 'mfs'
                selfcal.refant = '5'
                selfcal.go()
                self.logger.info('# Major self-calibration cycle ' + str(majc) + ' for chunk ' + chunk + ' finished #')
            self.logger.info('# Standard self-calibration routine for chunk ' + chunk + ' finished #')
        self.logger.info('### Manual self calibration routine finished ###')

    def selfcal_adaptive(self):
        '''
        Does the adaptive self-calibration with the given parameters.
        '''
        self.logger.info('### Starting adaptive self calibration routine ###')
        self.director('ch', self.selfcaldir)
        for chunk in self.list_chunks():
            self.logger.info('# Starting adaptive self-calibration routine on chunk ' + chunk + ' #')
            self.director('ch', self.selfcaldir + '/' + chunk)
            theoretical_noise = self.calc_theoretical_noise(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
            self.logger.info('# Theoretical noise for chunk ' + chunk + ' is ' + str(theoretical_noise / 1000) + ' Jy/beam #')
            exit_trigger = False # Reset the exit trigger for the next frequency chunk
            majc = 0  # Set and reset the major cycle counter for the adaptive self-calibration
            try:
                while exit_trigger == False:
                    self.logger.info('# Major self-calibration cycle ' + str(majc) + ' for chunk ' + chunk + ' started #')
                    self.director('mk', str(majc).zfill(2))
                    invert = lib.miriad('invert')  # Create the dirty image
                    invert.vis = chunk + '.mir'
                    invert.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                    invert.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                    invert.imsize = self.selfcal_image_imsize
                    invert.cell = self.selfcal_image_cellsize
                    invert.stokes = 'i'
                    invert.options = 'mfs,double'
                    invert.slop = 1
                    invert.go()
                    imax = self.calc_imax(str(majc).zfill(2) + '/map_' + str(0).zfill(2)) # Maximum value in the image
                    if majc == 0:
                        maxdr = imax / theoretical_noise  # Calculate the maximum dynamic range
                        self.logger.info('# The maximum dynamic range for chunk ' + str(chunk) + ' is ' + str(maxdr) + ' #')
                        self.create_parametric_mask(chunk + '.mir', 0.5, 0.9, 'NVSS', str(majc).zfill(2))
                        self.director('rn', str(majc).zfill(2) + '/mask_' + str(0).zfill(2), str(majc).zfill(2) + '/mask')
                        self.logger.info('# Parametric mask for self-calibration cycle 0 created #')
                        clean = lib.miriad('clean')
                        clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                        clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                        clean.out = str(majc).zfill(2) + '/model_' + str(0).zfill(2)
                        clean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(0).zfill(2) + ')"'
                        clean.cutoff = 0.000000001  # Set the rms cutoff to a very low number since you want the niters criterium
                        clean.niters = self.selfcal_mode_adaptive_firstniter
                        clean.go()
                        self.logger.info('# Cleaned image from self-calibration cycle 0 with ' + str(self.selfcal_mode_adaptive_firstniter) + ' iterations #')
                        restor = lib.miriad('restor')
                        restor.model = str(majc).zfill(2) + '/model_' + str(0).zfill(2)
                        restor.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                        restor.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                        restor.out = str(majc).zfill(2) + '/image_' + str(0).zfill(2)
                        restor.mode = 'clean'
                        restor.go()
                        self.logger.info('# Created restored image from self-calibration cycle 0 #')
                        restor.mode = 'residual'
                        restor.out = str(majc).zfill(2) + '/residual_' + str(0).zfill(2)
                        restor.go()
                        self.logger.info('# Created residual image from self-calibration cycle 0 #')
                    else:
                        maths = lib.miriad('maths')
                        maths.exp = '"<' + str(majc-1).zfill(2) + '/image_' + str(0).zfill(2) + '>"' # Use the image from the previous iteration to create the clean mask
                        maths.out = str(majc).zfill(2) + '/mask_' + str(0).zfill(2) # Create the mask in the current cycle directory
                        if majc == 1:
                            resimax = self.calc_imax(str(majc-1).zfill(2) + '/residual_' + str(0).zfill(2))
                            mask_cutoff = resimax / self.selfcal_mode_adaptive_firstrmsfactor
                        else:
                            mask_cutoff = theoretical_noise * self.selfcal_mode_adaptive_rmsfactor * factor
                        maths.mask = '"<' + str(majc-1).zfill(2) + '/image_' + str(0).zfill(2) + '>.gt.' + str(mask_cutoff) + '"'
                        maths.go()
                        self.logger.info('# Created mask with cutoff ' + str(mask_cutoff) + ' for self-calibration cycle ' + str(majc) + ' from previous cycle image #')
                        resirms = self.calc_irms(str(majc-1).zfill(2) + '/residual_' + str(0).zfill(2))
                        clean = lib.miriad('clean')
                        clean.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                        clean.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                        clean.out = str(majc).zfill(2) + '/model_' + str(0).zfill(2)
                        clean.region = '"' + 'mask(' + str(majc).zfill(2) + '/mask_' + str(0).zfill(2) + ')"'
                        clean.cutoff = self.selfcal_mode_adaptive_resirmsfactor * resirms  # Set the rms cutoff to a very low number since you want the niters criterium
                        clean.niters = 1000000
                        clean.go()
                        self.logger.info('# Cutoff for cleaning set to ' + str(clean.cutoff) + ' Jy/beam #')
                        restor = lib.miriad('restor')
                        restor.model = str(majc).zfill(2) + '/model_' + str(0).zfill(2)
                        restor.beam = str(majc).zfill(2) + '/beam_' + str(0).zfill(2)
                        restor.map = str(majc).zfill(2) + '/map_' + str(0).zfill(2)
                        restor.out = str(majc).zfill(2) + '/image_' + str(0).zfill(2)
                        restor.mode = 'clean'
                        restor.go()
                        self.logger.info('# Created restored image from self-calibration cycle ' + str(majc) + ' #')
                        restor.mode = 'residual'
                        restor.out = str(majc).zfill(2) + '/residual_' + str(0).zfill(2)
                        restor.go()
                        self.logger.info('# Created residual image from self-calibration cycle ' + str(majc) + ' #')
                    resi_rms, resi_max, perfactorsolint, perfactoruvrange, factor, ratio = self.calc_adaptive_stats(str(majc).zfill(2) + '/map_' + str(0).zfill(2), str(majc).zfill(2) + '/residual_' + str(0).zfill(2), theoretical_noise)
                    if factor >= self.selfcal_mode_adaptive_drlim and majc <= (self.selfcal_mode_adaptive_maxcycle-1):
                        selfcal = lib.miriad('selfcal')
                        selfcal.vis = chunk + '.mir'
                        selfcal.minants = 5
                        selfcal.refant = '5'
                        selfcal.options = 'mfs,phase'
                        selfcal.model = str(majc).zfill(2) + '/model_' + str(0).zfill(2)
                        minuvrange = (factor - 1) * perfactoruvrange
                        solint = 1 + (factor -1) * perfactorsolint
                        selfcal.select = '"' + 'uvrange(' + str(minuvrange) + ',' + str(1000) + ')' + '"'
                        selfcal.interval = int(solint)
                        selfcal.go()
                        self.logger.info('### Self calibration reached a DR of ' + str(int(maxdr / factor)) + ' of the maximum of ' + str(int(maxdr)) + ' ###')
                        self.logger.info('### Stop criterium was set to ' + str(self.selfcal_mode_adaptive_drlim) + ' corresponding to a DR of ' + str(int(maxdr / self.selfcal_mode_adaptive_drlim)) + ' ###')
                        self.logger.info('### Continuing self calibration with next cycle... ###')
                    else:
                        exit_trigger = True
                        if factor <= self.selfcal_mode_adaptive_drlim:
                            self.logger.info('### Self calibration automatically stopped at the DR-limit! DR is ' + str(int(maxdr / self.selfcal_mode_adaptive_drlim)) + ' of the maximum of ' + str(int(maxdr)) + ' ###')
                        elif majc == (self.selfcal_mode_adaptive_maxcycle -1):
                            self.logger.info('### Reached the maximum number of ' + str(self.selfcal_mode_adaptive_maxcycle) + ' self-calibration cycles! The DR is ' + str(int(maxdr/factor)) + ' of the maximum of ' + str(int(maxdr)) + ' ###')
                    self.logger.info('# Major self-calibration cycle ' + str(majc) + ' for chunk ' + chunk + ' done #')
                    majc = majc + 1
            except IOError:
                pass
        self.logger.info('# Adaptive self-calibration routine for chunk ' + chunk + ' finished #')
        self.logger.info('### Adaptive self calibration routine finished ###')

    # def selfcal_cal(self):
    #     '''
    #     selfcal_cal: Does a self calibration inside a selfcal loop with the given parameters
    #     '''
    #     selfcal = lib.miriad('selfcal')
    #     selfcal.vis = self.vis
    #     selfcal.minants = 5
    #     selfcal.refant = '3'
    #     selfcal.options = 'mfs,phase'
    #     selfcal.model = self.name_model
    #     if self.mode == 'manual':
    #         selfcal.select = 'uvrange(' + str(self.manual_minuvrange[self.nsubband][self.cycle]) + ',' + str(self.manual_maxuvrange[self.nsubband][self.cycle]) + ')'
    #         selfcal.interval = self.manual_interval[self.nsubband][self.cycle]
    #     elif self.mode == 'adaptive':
    #         self.single_minuvrange = (self.factor-1)*self.perfactoruvrange # Save these three variables for passing them to the manual inputs with pass_parameters
    #         self.single_maxuvrange = 1000
    #         self.single_interval = 1 + (self.factor - 1) * self.perfactorinterval
    #         selfcal.select = 'uvrange(' + str(self.single_minuvrange) + ',' + str(self.single_maxuvrange) + ')'
    #         selfcal.interval = int(self.single_interval)
    #     selfcal.go()

    # self.resirms, self.resimax, self.perfactorinterval, self.perfactoruvrange, self.factor, self.ratio = self.adaptive_stats()

    #  def selfcal_image(self, residual = False, mode = 'rms'):
    #     '''
    #     selfcal_image: Does an automatic invert, clean, restor with the given iterations and cutoffs inside a selfcal loop. Uses clean minorcycles if enabled.
    #     '''
    #     invert = lib.miriad('invert')
    #     invert.vis = self.vis
    #     invert.map = self.name_map
    #     invert.beam = self.name_beam
    #     invert.slop = '1'
    #     invert.imsize = self.imsize
    #     invert.cell = self.cell
    #     invert.options = 'mfs,double'
    #     invert.select = 'NONE'
    #     invert.go()
    #     if self.clean_minorcycle == True:
    #         print('Not implemented yet!')
    #     else:
    #         clean = lib.miriad('clean')
    #         clean.map = self.name_map
    #         clean.beam = self.name_beam
    #         clean.out = self.name_model
    #         clean.region = 'mask(' + self.name_mask + ')'
    #         if mode == 'rms':
    #             if self.mode == 'adaptive':
    #                 clean.cutoff = 1.75 * self.resirms
    #                 clean.niters = 10000000
    #                 self.single_niters = clean.niters # Save these three variables for passing them to the manual inputs with pass_parameters
    #                 self.single_cleancutoff = clean.cutoff
    #                 self.single_cleanstop = 'rms'
    #             else:
    #                 clean.cutoff = self.manual_cleancutoff[self.nsubband][self.cycle]
    #                 clean.niters = 10000000 # Set the iterations to a high number since you want the rms cutoff criterium
    #             self.logger.info('### Clean cutoff criterium set: ' + str(clean.cutoff) + ' Jy/beam ###')
    #         elif mode == 'niters':
    #             clean.cutoff = 0.000000001 # Set the rms cutoff to a very low number since you want the niters criterium
    #             if self.mode == 'adaptive' and self.cycle == 1: # Handle the first iteration of the adaptive selfcal automatically
    #                 clean.niters = self.adaptive_firstniter[self.nsubband]
    #                 self.single_niters = clean.niters # Save these three variables for passing them to the manual inputs with pass_parameters
    #                 self.single_cleancutoff = clean.cutoff
    #                 self.single_cleanstop = 'niters'
    #             else:
    #                 clean.niters = self.manual_niters[self.nsubband][self.cycle]
    #             self.logger.info('### Clean niters criterium set: ' + str(clean.niters) + ' ###')
    #         elif mode == 'both':
    #             clean.cutoff = self.manual_cleancutoff[self.nsubband][self.cycle]
    #             clean.niters = self.manual_niters[self.nsubband][self.cycle]
    #             self.logger.info('### Clean cutoff criterium set: ' + str(clean.cutoff) + ' Jy/beam ###')
    #             self.logger.info('### Clean niters criterium set: ' + str(clean.niters) + ' ###')
    #         else:
    #             self.logger.error('### Clean criterium not supported! Exiting! ###')
    #             sys.exit(1)
    #         clean.go()
    #     restor = lib.miriad('restor')
    #     restor.model = self.name_model
    #     restor.beam = self.name_beam
    #     restor.map = self.name_map
    #     restor.out = self.name_image
    #     restor.mode = 'clean'
    #     restor.go()
    #     if residual == True:
    #         restor.mode = 'residual'
    #         restor.out = self.name_residual
    #         restor.go()

    #     for x,sb in enumerate(self.subbands):
    #         self.nsubband = x # Just short for self.nsubband to use for log output
    #         x = self.adaptive_nif[x] # This is defining the name of the subdirectory for the subband to calibrate
    #         self.logger.info('##### Starting adaptive self calibration of subband ' + str(x+1).zfill(2) + '! #####')
    #         self.director('ch', self.selfcaldir + '/' + str(x + 1).zfill(2))  # Move to the subband directory
    #         self.vis = self.cwd + '/' + str(sb)  # Name the split data chunk
    #         self.init_stats(str(sb)) # We need the stats for this kind of calibration
    #         self.exit_adaptive = False # Set and reset the self-calibration trigger for further subbands
    #         self.cycle = 0 # Reset the counter for the next subband
    #         while self.exit_adaptive == False:
    #             self.cycle = self.cycle + 1 # Increase the cycle number by 1
    #             self.logger.info('##### Starting self calibration cycle ' + str(self.cycle) + ' for subband ' + str(x+1).zfill(2) + ' #####')
    #             self.director('ch', self.selfcaldir + '/' + str(x+1).zfill(2) + '/' + str(self.cycle).zfill(2))  # Move to the next selfcal cycle directory
    #             if self.cycle == 1: # Create a mask from the catalogue if there is no other
    #                 if os.path.exists(self.selfcaldir + '/' + str(x+1).zfill(2) + '/' + str(self.cycle).zfill(2) + '/' + self.name_mask):
    #                     self.logger.info('### Using mask from earlier iterations for cleaning! ###')
    #                     continue
    #                 else:
    #                     self.logger.info('### No mask for cleaning available from earlier iterations! ###')
    #                     self.logger.info('### Querying NVSS catalogue for producing a mask! ###')
    #                     lsm.write_mask(self.selfcaldir + '/' + str(x+1).zfill(2) + '/' + str(self.cycle).zfill(2) + '/' + self.name_mask + '.txt', lsm.lsm_mask(self.vis, 0.5, 0.9, 'NVSS'))
    #                     self.create_parmsk(rmtxt=True)
    #                 self.selfcal_image(residual=True, mode='niters')
    #             else:
    #                 self.create_mask()
    #                 self.selfcal_image(residual=True, mode='rms')
    #             self.resirms, self.resimax, self.perfactorinterval, self.perfactoruvrange, self.factor, self.ratio = self.adaptive_stats()
    #             if self.factor >= self.adaptive_drlim[self.nsubband] and self.cycle <= (self.adaptive_maxcycle[self.nsubband] - 1):
    #                 self.selfcal_cal()
    #                 self.logger.info('### Self calibration reached a DR of ' + str(int(self.maxvdr / self.factor)) + ' of the maximum of ' + str(int(self.maxvdr)) + ' ###')
    #                 self.logger.info('### Stop criterium was set to ' + str(self.adaptive_drlim[self.nsubband]) + ' corresponding to a DR of ' + str(int(self.maxvdr / self.adaptive_drlim[self.nsubband])) + ' ###')
    #                 self.logger.info('### Continuing self calibration with next cycle... ###')
    #             else:
    #                 self.exit_adaptive = True
    #                 if self.factor <= self.adaptive_drlim[self.nsubband]:
    #                     self.logger.info('### Self calibration automatically stopped at the DR-limit! DR is ' + str(int(self.maxvdr / self.factor)) + ' of the maximum of ' + str(int(self.maxvdr)) + ' ###')
    #                 elif self.cycle == (self.adaptive_maxcycle[self.nsubband] - 1):
    #                     self.logger.info('### Reached the maximum number of ' + str(self.adaptive_maxcycle[self.nsubband]) + ' self-calibration cycles! The DR is ' + str(int(self.maxvdr/self.factor)) + ' of the maximum of ' + str(int(self.maxvdr)) + ' ###')
    #             self.pass_parameters('cycle') # Pass the parameters to the manual inputs after each calibration cycle
    #             self.logger.info('##### Adaptive self-calibration cycle ' + str(self.cycle) + ' of subband ' + str(x+1).zfill(2) + ' done! #####')
    #         self.pass_parameters('subband') # Pass the parameters to the manual inputs after each calibrated subband
    #         self.logger.info('##### Adaptive self calibration of subband ' + str(x+1).zfill(2) + ' done! #####')

    # def create_mask(self):
    #     '''
    #     create_mask: Creates a mask from an image during self calibration using a cutoff of the former cleaned stokes I image
    #     '''
    #     cwd = self.cwd
    #     self.director('ch', self.lwd, verbose=False)
    #     maths = lib.miriad('maths')
    #     maths.exp = self.name_image
    #     maths.out = self.name_mask + '_tmp'
    #     if self.mode == 'manual':
    #         self.single_mskcutoff = self.manual_mskcutoff[self.nsubband][self.cycle]
    #     elif self.mode == 'adaptive':
    #         self.single_mskcutoff = self.adaptive_mskcutoff()
    #     maths.mask = self.name_image + '.gt.' + str(self.single_mskcutoff)
    #     self.logger.info('### Mask cutoff: ' + str(self.single_mskcutoff) + ' Jy/beam ###')
    #     maths.go()
    #     self.director('ch', cwd, verbose=False)
    #     self.director('rn', self.cwd + '/' + self.name_mask, self.lwd + '/' + self.name_mask  + '_tmp')

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
        self.director('rm', outputdir + '/imgen')
        self.single_mskcutoff = 1e-6
        self.director('rm', outputdir + '/mask.txt')

    # def calc_stats(self, dataset, image):
    #     '''
    #     Calculates and updates statistics using the rms in Stokes V and the brightest pixel in Stokes I as well as calculating it from theoretical parameters
    #     dataset (string): The dataset to calculate the theoretical rms from
    #     image (string): The image to calculate the maximum pixel value and maximum dynamic range from
    #     returns (float, float, float): The theoretical rms of the dataset, the maximum pixel value in the inpiut image, and the maximum dynamic range reachable in the dataset based on the ratio of the maximum pixel value and the theoretical noise
    #     '''
    #     theorms = self.calc_theoretical_noise(dataset)
    #     imax = self.calc_imax(image)
    #     maxdr = imax/theorms
    #     return theorms, imax, maxdr

    def calc_adaptive_stats(self, dirtyimage, resiimage, theoretical_noise):
        '''
        Calculates the values needed for the major cycles in adaptive self-calibration mode
        dirtyimage (string): The dirty uncleaned image of the major cycle
        resiimage (string): The residual cleaned image of the major cycle
        theoretical_noise (float): The theoretical noise of the dataset
        returns (float, float, float, float, float): The needed stats for the adaptive self-calibration routine
        '''
        image_rms = self.calc_irms(dirtyimage)
        resi_max = self.calc_imax(resiimage)
        resi_rms = self.calc_irms(resiimage)
        maxfactor = image_rms / theoretical_noise
        perfactorsolint = self.selfcal_mode_adaptive_startsolint / maxfactor
        perfactoruvrange = self.selfcal_mode_adaptive_startuvrange / maxfactor
        factor = resi_rms / theoretical_noise
        ratio = factor / maxfactor
        return resi_rms, resi_max, perfactorsolint, perfactoruvrange, factor, ratio

    def calc_irms(self, image):
        '''
        Function to calculate the maximum of an image
        image (string): The name of the image file. Must be in FITS-format
        returns (float): the maximum in the image
        '''
        fits = lib.miriad('fits')
        fits.op = 'xyout'
        fits.in_ = image
        fits.out = image + '.fits'
        fits.go()
        image_data = pyfits.open(image + '.fits')  # Open the image
        data = image_data[0].data
        imax = np.std(data) # Get the standard deviation
        image_data.close() # Close the image
        self.director('rm', image + '.fits')
        return imax

    def calc_imax(self, image):
        '''
        Function to calculate the maximum of an image
        image (string): The name of the image file. Must be in FITS-format
        returns (float): the maximum in the image
        '''
        fits = lib.miriad('fits')
        fits.op = 'xyout'
        fits.in_ = image
        fits.out = image + '.fits'
        fits.go()
        image_data = pyfits.open(image + '.fits')  # Open the image
        data = image_data[0].data
        imax = np.max(data) # Get the maximum
        image_data.close() # Close the image
        self.director('rm', image + '.fits')
        return imax

    def calc_mask_threshold(self, imax, minor_cycle, major_cycle):
        '''
        Calculates the mask threshold
        imax (float): the maximum in the input image
        minor_cycle (int): the current minor cycle the self-calibration is in
        major_cycle (int): the current major cycle the self-calibration is in
        returns (float): the mask threshold
        '''
        mask_threshold = imax / ((self.selfcal_mode_standard_c0 + (minor_cycle) * self.selfcal_mode_standard_c0) * (major_cycle + 1))
        return mask_threshold

    def calc_clean_noise_threshold(self, imax, minor_cycle, major_cycle):
        '''
        Calculates the clean nosie threshold
        imax (float): the maximum in the input image
        minor_cycle (int): the current minor cycle the self-calibration is in
        major_cycle (int): the current major cycle the self-calibration is in
        returns (float): the clean noise threshold
        '''
        clean_noise_threshold = imax / (((self.selfcal_mode_standard_c0 + (minor_cycle) * self.selfcal_mode_standard_c0) * (major_cycle + 1)) * self.selfcal_mode_standard_c1)
        return clean_noise_threshold

    def calc_dynamic_range_threshold(self, imax, major_cycle):
        '''
        Calculates the dynamic range threshold
        imax (float): the maximum in the input image
        major_cycle (int): the current major cycle the self-calibration is in
        returns (float): the dynamic range threshold
        '''
        dynamic_range_threshold = imax / (((major_cycle) * self.selfcal_mode_standard_dr0 * self.selfcal_mode_standard_drinit) + self.selfcal_mode_standard_drinit)
        return dynamic_range_threshold

    def calc_theoretical_noise_threshold(self, theoretical_noise):
        '''
        Calculates the theoretical noise threshold from the theoretical noise
        theoretical_noise (float): the theoretical noise of the observation
        returns (float): the theoretical noise threshold
        '''
        theoretical_noise_threshold = (self.selfcal_mode_standard_nsigma * theoretical_noise)
        return theoretical_noise_threshold

    def calc_theoretical_noise(self, dataset):
        '''
        Calculate the theoretical rms of a given dataset
        dataset (string): The input dataset to calculate the theoretical rms from
        returns (float): The theoretical rms of the input dataset as a float
        '''
        uv = aipy.miriad.UV(dataset)
        obsrms = lib.miriad('obsrms')
        tsys = np.median(uv['systemp'])
        if np.isnan(tsys):
            obsrms.tsys = 30.0
        else:
            obsrms.tsys = tsys
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
        for n in range(100):
            if os.path.exists(self.selfcaldir + '/' + str(n).zfill(2)):
                pass
            else:
                break # Stop the counting loop at the directory you cannot find anymore
        chunks = range(n)
        chunkstr = [str(i).zfill(2) for i in chunks]
        return chunkstr

    # def go(self):
    #     '''
    #     go: Splits the dataset into subbands of equal size and runs the selfcal cycle with the chosen mode. Handles parametric and amplitude calibration as well as deep single subband imaging.
    #     '''
    #     self.logger.info("########## Starting SELF CALIBRATION ##########")
    #     if self.field == 'fluxcal':
    #         self.target = self.fluxcal.rstrip('MS') + 'mir'  # Rename self.target since MS has already been converted to MIRIAD file
    #     if self.field == 'polcal':
    #         self.target = self.polcal.rstrip('MS') + 'mir'  # Rename self.target since MS has already been converted to MIRIAD file
    #     elif self.field == 'target':
    #         self.target = self.target.rstrip('MS') + 'mir'  # Rename self.target since MS has already been converted to MIRIAD file
    #     self.apply_cal()
    #     # self.turbo_speed() # Use turbo mode if enabled. Switch is inside turbo_speed
    #     self.split_data() # Split the data. Also checks if the data has already been split
    #     if self.parametric:  # Do parametric self-calibration if enabled
    #         self.par_cal()
    #     if self.mode == 'adaptive':  # Do adaptive self-calibration
    #         self.adaptive()
    #     elif self.mode == 'manual':  # Do manual self-calibration
    #         self.manual()
    #     elif self.mode == 'none':
    #         self.logger.info('### No adaptive or manual self-calibration done! ###')
    #     else:
    #         self.logger.error('### Self Calibration mode not supported! Exiting programme! ###')
    #         sys.exit(1)
    #     # if self.amp == True: # Do amplitude calibration if enabled
    #     #     self.selfcal_amp()
    #     # if self.deep == True: # Make a deep image of each calibrated subband
    #     #     self.deep_image()
    #     self.logger.info("########## SELF CALIBRATION done ##########")

    # def adaptive(self):
    #     self.logger.info("########## Using adaptive mode for self calibration! ##########")
    #     self.handle_inputs('adaptive')
    #     self.subbands = self.get_uvfiles(self.selfcaldir) # Reset the self.subbands list
    #     self.subbands = [self.subbands[i] for i in self.adaptive_nif] # Filter which datasets you want to calibrate
    #     self.pass_parameters('init') # Initialise passing the parameters to the manual inputs
    #     for x,sb in enumerate(self.subbands):
    #         self.nsubband = x # Just short for self.nsubband to use for log output
    #         x = self.adaptive_nif[x] # This is defining the name of the subdirectory for the subband to calibrate
    #         self.logger.info('##### Starting adaptive self calibration of subband ' + str(x+1).zfill(2) + '! #####')
    #         self.director('ch', self.selfcaldir + '/' + str(x + 1).zfill(2))  # Move to the subband directory
    #         self.vis = self.cwd + '/' + str(sb)  # Name the split data chunk
    #         self.init_stats(str(sb)) # We need the stats for this kind of calibration
    #         self.exit_adaptive = False # Set and reset the self-calibration trigger for further subbands
    #         self.cycle = 0 # Reset the counter for the next subband
    #         while self.exit_adaptive == False:
    #             self.cycle = self.cycle + 1 # Increase the cycle number by 1
    #             self.logger.info('##### Starting self calibration cycle ' + str(self.cycle) + ' for subband ' + str(x+1).zfill(2) + ' #####')
    #             self.director('ch', self.selfcaldir + '/' + str(x+1).zfill(2) + '/' + str(self.cycle).zfill(2))  # Move to the next selfcal cycle directory
    #             if self.cycle == 1: # Create a mask from the catalogue if there is no other
    #                 if os.path.exists(self.selfcaldir + '/' + str(x+1).zfill(2) + '/' + str(self.cycle).zfill(2) + '/' + self.name_mask):
    #                     self.logger.info('### Using mask from earlier iterations for cleaning! ###')
    #                     continue
    #                 else:
    #                     self.logger.info('### No mask for cleaning available from earlier iterations! ###')
    #                     self.logger.info('### Querying NVSS catalogue for producing a mask! ###')
    #                     lsm.write_mask(self.selfcaldir + '/' + str(x+1).zfill(2) + '/' + str(self.cycle).zfill(2) + '/' + self.name_mask + '.txt', lsm.lsm_mask(self.vis, 0.5, 0.9, 'NVSS'))
    #                     self.create_parmsk(rmtxt=True)
    #                 self.selfcal_image(residual=True, mode='niters')
    #             else:
    #                 self.create_mask()
    #                 self.selfcal_image(residual=True, mode='rms')
    #             self.resirms, self.resimax, self.perfactorinterval, self.perfactoruvrange, self.factor, self.ratio = self.adaptive_stats()
    #             if self.factor >= self.adaptive_drlim[self.nsubband] and self.cycle <= (self.adaptive_maxcycle[self.nsubband] - 1):
    #                 self.selfcal_cal()
    #                 self.logger.info('### Self calibration reached a DR of ' + str(int(self.maxvdr / self.factor)) + ' of the maximum of ' + str(int(self.maxvdr)) + ' ###')
    #                 self.logger.info('### Stop criterium was set to ' + str(self.adaptive_drlim[self.nsubband]) + ' corresponding to a DR of ' + str(int(self.maxvdr / self.adaptive_drlim[self.nsubband])) + ' ###')
    #                 self.logger.info('### Continuing self calibration with next cycle... ###')
    #             else:
    #                 self.exit_adaptive = True
    #                 if self.factor <= self.adaptive_drlim[self.nsubband]:
    #                     self.logger.info('### Self calibration automatically stopped at the DR-limit! DR is ' + str(int(self.maxvdr / self.factor)) + ' of the maximum of ' + str(int(self.maxvdr)) + ' ###')
    #                 elif self.cycle == (self.adaptive_maxcycle[self.nsubband] - 1):
    #                     self.logger.info('### Reached the maximum number of ' + str(self.adaptive_maxcycle[self.nsubband]) + ' self-calibration cycles! The DR is ' + str(int(self.maxvdr/self.factor)) + ' of the maximum of ' + str(int(self.maxvdr)) + ' ###')
    #             self.pass_parameters('cycle') # Pass the parameters to the manual inputs after each calibration cycle
    #             self.logger.info('##### Adaptive self-calibration cycle ' + str(self.cycle) + ' of subband ' + str(x+1).zfill(2) + ' done! #####')
    #         self.pass_parameters('subband') # Pass the parameters to the manual inputs after each calibrated subband
    #         self.logger.info('##### Adaptive self calibration of subband ' + str(x+1).zfill(2) + ' done! #####')
    #     self.logger.info('### Passing parameters to manual inputs! ###')
    #     self.logger.info("########## Adaptive self calibration done! ##########")
    #
    # #######################################################
    # ##### Subfunctions to use during self-calibration #####
    # #######################################################
    #
    # def apply_cal(self):
    #     '''
    #     Applies the calibration from the cross-calibration since uvsplit does not have the option to do that
    #     '''
    #     self.director('ch', self.selfcaldir)
    #     uvcat = lib.miriad('uvcat')
    #     uvcat.vis = self.crosscaldir + '/' + self.target
    #     uvcat.out = self.selfcaldir + '/' + self.target
    #     uvcat.go()
    #     self.vis = self.target
#
    # def init_stats(self, dataset):
    #     '''
    #     init_stats: Calculates and updates statistics using the rms in Stokes V and the brightest pixel in Stokes I as well as calculating it from theoretical parameters
    #     dataset: The dataset to calculate the parameters for
    #     '''
    #     self.vmax, self.vrms = qa.imstats(str(dataset), 'v') # Measure the noise from the Stokes V image
    #     self.logger.info('### Measured noise from Stokes V image is ' + str(self.vrms) + ' Jy/beam ###')
    #     self.theorms = qa.theostats(str(dataset))
    #     self.logger.info('### Theoretical noise is ' + str(self.theorms) + ' Jy/beam ###')
    #     self.imax, self.irms = qa.imstats(str(dataset), 'i')
    #     self.logger.info('### Maximum in total power image is ' + str(self.imax) + ' Jy/beam ###')
    #     self.maxvdr = self.imax/self.vrms
    #     self.logger.info('### Maximum dynamic range calculated from Stokes V is ' + str(self.maxvdr) + ' ###')
    #     self.maxtheodr = self.imax/self.theorms
    #     self.logger.info('### Maximum dynamic range calculated from theoretical noise is ' + str(self.maxtheodr) + ' ###')

    # def adaptive_stats(self):
    #     '''
    #     adaptive_stats: Calculate the stats needed for each iteration of the adaptive selfcal cycle
    #     return: The residual rms, the maximum of the residual, the decreasing factor for the solution interval, the decreasing factor for the minimum uvrange, the factor, and the ratio of the dynamic range of the image
    #     '''
    #     resirms, resimax = qa.resistats(self.name_residual)
    #     maxfactor = self.irms/self.vrms
    #     perfactorinterval = (self.adaptive_startinterval[self.nsubband]-1)/maxfactor
    #     perfactoruvrange = self.adaptive_startuvrange[self.nsubband]/maxfactor
    #     factor = resirms/self.vrms
    #     ratio = factor/maxfactor
    #     return resirms, resimax, perfactorinterval, perfactoruvrange, factor, ratio
    #
    # def pass_parameters(self, mode):
    #     '''
    #     pass_parameters: Function to pass the automatically calculated parameters from the adaptive selfcal to the manual inputs. Can be shown with a wselfcal.show() after adaptive calibration
    #     param mode: Deal with the different depths of the selfcal calibration. init for initialising and resetting values, cycle for saving the parameters of the lst selfcal cycle, and subband to save the values of the last subband calibration and reset for the next subband calibration
    #     '''
    #     if mode == 'init':
    #         self.manual_if = self.adaptive_nif
    #         self.manual_cycles = []
    #         self.manual_minuvrange = []
    #         self.manual_maxuvrange = []
    #         self.manual_interval = []
    #         self.manual_niters = []
    #         self.manual_cleancutoff = []
    #         self.manual_mskcutoff = []
    #         self.manual_cleanstop = []
    #         self.minuvrange = []
    #         self.maxuvrange = []
    #         self.interval = []
    #         self.niters = []
    #         self.cleancutoff = []
    #         self.mskcutoff = []
    #         self.cleanstop = []
    #     elif mode == 'cycle':
    #         self.minuvrange.append(self.single_minuvrange)
    #         self.maxuvrange.append(self.single_maxuvrange)
    #         self.interval.append(self.single_interval)
    #         self.niters.append(self.single_niters)
    #         self.cleancutoff.append(self.single_cleancutoff)
    #         self.mskcutoff.append(self.single_mskcutoff)
    #         self.cleanstop.append(self.single_cleanstop)
    #     elif mode == 'subband':
    #         self.manual_cycles.append(self.cycle)
    #         self.manual_minuvrange.append(self.minuvrange)
    #         self.manual_maxuvrange.append(self.maxuvrange)
    #         self.manual_interval.append(self.interval)
    #         self.manual_niters.append(self.niters)
    #         self.manual_cleancutoff.append(self.cleancutoff)
    #         self.manual_mskcutoff.append(self.mskcutoff)
    #         self.manual_cleanstop.append(self.cleanstop)
    #         self.minuvrange = []
    #         self.maxuvrange = []
    #         self.interval = []
    #         self.niters = []
    #         self.cleancutoff = []
    #         self.mskcutoff = []
    #         self.cleanstop = []
    #     else:
    #         self.logger.error('### Mode not supported! Choose init, cycle, or subband! Exiting! ###')
    #         sys.exit(1)

    #
    # def create_mask(self):
    #     '''
    #     create_mask: Creates a mask from an image during self calibration using a cutoff of the former cleaned stokes I image
    #     '''
    #     cwd = self.cwd
    #     self.director('ch', self.lwd, verbose=False)
    #     maths = lib.miriad('maths')
    #     maths.exp = self.name_image
    #     maths.out = self.name_mask + '_tmp'
    #     if self.mode == 'manual':
    #         self.single_mskcutoff = self.manual_mskcutoff[self.nsubband][self.cycle]
    #     elif self.mode == 'adaptive':
    #         self.single_mskcutoff = self.adaptive_mskcutoff()
    #     maths.mask = self.name_image + '.gt.' + str(self.single_mskcutoff)
    #     self.logger.info('### Mask cutoff: ' + str(self.single_mskcutoff) + ' Jy/beam ###')
    #     maths.go()
    #     self.director('ch', cwd, verbose=False)
    #     self.director('rn', self.cwd + '/' + self.name_mask, self.lwd + '/' + self.name_mask  + '_tmp')
    #
    # def adaptive_mskcutoff(self):
    #     if self.cycle == 0 or self.cycle == 1:
    #         mask_cutoff = self.resimax / 10.0
    #     else:
    #         mask_cutoff = self.vrms * 4.0 * self.factor
    #     return mask_cutoff

    #
    # def selfcal_image(self, residual = False, mode = 'rms'):
    #     '''
    #     selfcal_image: Does an automatic invert, clean, restor with the given iterations and cutoffs inside a selfcal loop. Uses clean minorcycles if enabled.
    #     '''
    #     invert = lib.miriad('invert')
    #     invert.vis = self.vis
    #     invert.map = self.name_map
    #     invert.beam = self.name_beam
    #     invert.slop = '1'
    #     invert.imsize = self.imsize
    #     invert.cell = self.cell
    #     invert.options = 'mfs,double'
    #     invert.select = 'NONE'
    #     invert.go()
    #     if self.clean_minorcycle == True:
    #         print('Not implemented yet!')
    #     else:
    #         clean = lib.miriad('clean')
    #         clean.map = self.name_map
    #         clean.beam = self.name_beam
    #         clean.out = self.name_model
    #         clean.region = 'mask(' + self.name_mask + ')'
    #         if mode == 'rms':
    #             if self.mode == 'adaptive':
    #                 clean.cutoff = 1.75 * self.resirms
    #                 clean.niters = 10000000
    #                 self.single_niters = clean.niters # Save these three variables for passing them to the manual inputs with pass_parameters
    #                 self.single_cleancutoff = clean.cutoff
    #                 self.single_cleanstop = 'rms'
    #             else:
    #                 clean.cutoff = self.manual_cleancutoff[self.nsubband][self.cycle]
    #                 clean.niters = 10000000 # Set the iterations to a high number since you want the rms cutoff criterium
    #             self.logger.info('### Clean cutoff criterium set: ' + str(clean.cutoff) + ' Jy/beam ###')
    #         elif mode == 'niters':
    #             clean.cutoff = 0.000000001 # Set the rms cutoff to a very low number since you want the niters criterium
    #             if self.mode == 'adaptive' and self.cycle == 1: # Handle the first iteration of the adaptive selfcal automatically
    #                 clean.niters = self.adaptive_firstniter[self.nsubband]
    #                 self.single_niters = clean.niters # Save these three variables for passing them to the manual inputs with pass_parameters
    #                 self.single_cleancutoff = clean.cutoff
    #                 self.single_cleanstop = 'niters'
    #             else:
    #                 clean.niters = self.manual_niters[self.nsubband][self.cycle]
    #             self.logger.info('### Clean niters criterium set: ' + str(clean.niters) + ' ###')
    #         elif mode == 'both':
    #             clean.cutoff = self.manual_cleancutoff[self.nsubband][self.cycle]
    #             clean.niters = self.manual_niters[self.nsubband][self.cycle]
    #             self.logger.info('### Clean cutoff criterium set: ' + str(clean.cutoff) + ' Jy/beam ###')
    #             self.logger.info('### Clean niters criterium set: ' + str(clean.niters) + ' ###')
    #         else:
    #             self.logger.error('### Clean criterium not supported! Exiting! ###')
    #             sys.exit(1)
    #         clean.go()
    #     restor = lib.miriad('restor')
    #     restor.model = self.name_model
    #     restor.beam = self.name_beam
    #     restor.map = self.name_map
    #     restor.out = self.name_image
    #     restor.mode = 'clean'
    #     restor.go()
    #     if residual == True:
    #         restor.mode = 'residual'
    #         restor.out = self.name_residual
    #         restor.go()
    #
    # def selfcal_cal(self):
    #     '''
    #     selfcal_cal: Does a self calibration inside a selfcal loop with the given parameters
    #     '''
    #     selfcal = lib.miriad('selfcal')
    #     selfcal.vis = self.vis
    #     selfcal.minants = 5
    #     selfcal.refant = '3'
    #     selfcal.options = 'mfs,phase'
    #     selfcal.model = self.name_model
    #     if self.mode == 'manual':
    #         selfcal.select = 'uvrange(' + str(self.manual_minuvrange[self.nsubband][self.cycle]) + ',' + str(self.manual_maxuvrange[self.nsubband][self.cycle]) + ')'
    #         selfcal.interval = self.manual_interval[self.nsubband][self.cycle]
    #     elif self.mode == 'adaptive':
    #         self.single_minuvrange = (self.factor-1)*self.perfactoruvrange # Save these three variables for passing them to the manual inputs with pass_parameters
    #         self.single_maxuvrange = 1000
    #         self.single_interval = 1 + (self.factor - 1) * self.perfactorinterval
    #         selfcal.select = 'uvrange(' + str(self.single_minuvrange) + ',' + str(self.single_maxuvrange) + ')'
    #         selfcal.interval = int(self.single_interval)
    #     selfcal.go()
    #
    # def selfcal_amp(self):
    #     print('Not supported yet')
    #
    # def deep_image(self):
    #     #     logger.info('########## Creating final deep image for SB ' + str(x+1).zfill(2) + ' ##########')
    #     #     self.selfcal_deepimage(cycle)
    #     #     logger.info('########## Final deep image for SB ' + str(x + 1).zfill(2) + ' created successfully ##########')
    #     print('Doing deep imaging')
    #
    # # def selfcal_deepimage(self, cycle):
    # #     self.chdir('../' + str(cycle + 1).zfill(2))
    # #     invert.go()
    # #     clean.niters = 100000
    # #     clean.cutoff = self.factor * self.resirms
    # #     clean.go()
    # #     restor.mode = 'clean'
    # #     restor.out = 'image'
    # #     restor.go()
    # #     fits.in_ = restor.out
    # #     fits.out = self.filename + '.fits'
    # #     fits.go()
    #
    # #############################################################################################
    # ##### Helper functions to get information from datasets and clear previous calibrations #####
    # #############################################################################################
    #
    # def get_uvfiles(self, path):
    #     '''
    #     get_uvfiles: Scan the path and its subdirectories for datasets split in frequency
    #     path: The path in which to search for the uv-files
    #     return: A list of the names of the files without the absolute directory path
    #     '''
    #     filesmain = glob.glob(path + '/*.[0-9][0-9][0-9][0-9].[0-9]')
    #     filessub = glob.glob(path + '/[0-9][0-9]/*.[0-9][0-9][0-9][0-9].[0-9]')
    #     for n,f in enumerate(filesmain):
    #         filesmain[n] = os.path.basename(f)
    #     for n,f in enumerate(filessub):
    #         filessub[n] = os.path.basename(f)
    #     lm = len(filesmain)
    #     ls = len(filessub)
    #     if lm==0 and ls==0:
    #         self.splitstatus = -1
    #         files = []
    #     elif lm>0 and ls==0:
    #         files = filesmain
    #         self.splitstatus = 1
    #     elif lm==0  and ls>0:
    #         files = filessub
    #         self.splitstatus = 2
    #     elif lm>0 and ls>0:
    #         self.logger.error('### Subband uv-files in main selfcal directory and sub directories! Clean up your selfcal directory first! ###')
    #         self.splitstatus = 0
    #         sys.exit(1)
    #     return files
    #
    # def get_freqs(self, files, setting='starting'):
    #     '''
    #     get_freqs: Get the starting, centre, or rest frequencies for a list of uv-files
    #     files: A list of strings with the names of the uv-files
    #     setting: starting, centre, or rest frequency
    #     return: A list of strings with the freqeuncies
    #     '''
    #     freqs = []
    #     for x,f in enumerate(files):
    #         if setting == 'starting':
    #             freqs = [f.split('.')[-2] for f in files]
    #         if setting == 'centre':
    #             print('Later')
    #         if setting == 'rest':
    #             print('Later')
    #     return freqs
    #
    # def clear_all(self):
    #     '''
    #     clear_all: Removes the complete selfcal directory
    #     '''
    #     self.director('ch', self.crosscaldir)
    #     self.director('rm', self.selfcaldir)
    #     self.logger.info('### Removed the complete self calibration from the data! ###')
    #
    # def clear_cal(self, ifs=None):
    #     '''
    #     clear_cal: Removes the gains and products from self calibration iterations for the given subbands
    #     ifs: You can give a list of subbands here to remove. If none is given all IFs are cleared from the calibration
    #     '''
    #     if ifs == None:
    #         self.clear_ifs = range(len(self.subbands))
    #     self.logger.info('### Deleting calibration of subbands ' + str(self.clear_ifs) + ' ###')
    #     for n,sbfile in enumerate(self.subbands):
    #         self.director('rn', self.selfcaldir, self.selfcaldir + '/' + str(n+1).zfill(2) + '/' + str(sbfile))
    #         self.director('rm', self.selfcaldir + '/' + str(n+1).zfill(2) + '/*')
    #         self.director('rm', self.selfcaldir + '/' + str(sbfile) + '/gains')
    #         self.director('rn', self.selfcaldir + '/' + str(n+1).zfill(2) + '/' , self.selfcaldir + '/' + str(sbfile))
    #
    # ###########################################################
    # ##### Handle the config files and check manual inputs #####
    # ###########################################################
    #
    # def default(self):
    #     '''
    #     default: Loads the default settings from the default.cfg file
    #     '''
    #     self.load()
    #
    # def save(self, configfile = 'last.cfg'):
    #     '''
    #     save: Saves the current inputs to a file
    #     configfile: The file to save to. Default is last.cfg
    #     '''
    #     default = ConfigParser.ConfigParser()
    #     default.readfp(open(self.apercaldir + '/default.cfg'))
    #     for s in default.sections():
    #         for o in default.items(s):
    #             default.set(s, o[0], self.__dict__.__getitem__(o[0]))
    #     with open(str(configfile), 'wb') as lastfile:
    #         default.write(lastfile)
    #     self.logger.info('### Wrote current configuration to ' + str(configfile) + '! ###')
    #
    # def load(self, configfile = 'default.cfg'):
    #     '''
    #     load: Loads the settings from a given configfile
    #     configfile: The configfile to load. Full path is safe
    #     '''
    #     config = ConfigParser.ConfigParser()
    #     if configfile == 'default.cfg':
    #         config.readfp(open(self.apercaldir + '/default.cfg'))
    #         self.logger.info('### Reading default config settings! ###')
    #     else:
    #         config.readfp(open(str(configfile)))
    #         self.logger.info('### Reading config settings from ' + str(configfile) + '! ###')
    #     for s in config.sections():
    #         for o in config.items(s):
    #             setattr(self, o[0], eval(o[1]))
    #
    # def show(self):
    #     '''
    #     Prints the current settings of the pipeline. Only shows keywords, which are in the default config file default.cfg
    #     '''
    #     config = ConfigParser.ConfigParser()
    #     config.readfp(open(self.apercaldir + '/default.cfg'))
    #     for s in config.sections():
    #         print(s)
    #         o = config.options(s)
    #         for o in config.items(s):
    #             print('\t' + str(o[0]) + ' = ' + str(self.__dict__.__getitem__(o[0])))
    #
    # def read_singleselfcalvalue(self, keyword):
    #     '''
    #     read_defaultvalue: Function to read a default value from the default config file
    #     keyword: The keyword to read from the config file
    #     return: The value of the keyword to return
    #     '''
    #     config = ConfigParser.ConfigParser()
    #     config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
    #     setting = config.get('SELFCAL', str(keyword))
    #     return setting
    #
    # def handle_inputs(self, mode): # Hopefully works now. Handles the format of the inputs for the manual inputs. No explanation here. Hope I clean this up later.
    #     if len(self.manual_if) == 0 and self.mode == 'manual':
    #         self.manual_nif = range(len(self.get_uvfiles(self.selfcaldir)))
    #     else:
    #         self.manual_nif = self.manual_if
    #
    #     if len(self.adaptive_if) == 0 and self.mode == 'adaptive':
    #         self.adaptive_nif = range(len(self.get_uvfiles(self.selfcaldir)))
    #     else:
    #         self.adaptive_nif = self.adaptive_if
    #
    #     if len(self.parametric_if) == 0 and self.parametric == True:
    #         self.parametric_nif = range(len(self.get_uvfiles(self.selfcaldir)))
    #     else:
    #         self.parametric_nif = self.parametric_if
    #
    #     def get_depth(a):  # Calculate the depth of a list
    #         try:
    #             b = 1 + get_depth(a[0]) if type(a) is list else 0
    #         except IndexError:
    #             b = False
    #         return b
    #
    #     def correct_cycles(cycles, nif):
    #         if get_depth(cycles) == 0:
    #             cycles = [cycles]
    #             cycles = correct_cycles(cycles, nif)
    #         elif get_depth(cycles) == 1:
    #             if len(cycles) == 1:
    #                 cycles = cycles * len(nif)
    #             elif len(cycles) == len(nif):
    #                 pass
    #             else:
    #                 self.logger.error('### Number of subbands not equal to the number of given values! Exiting! ###')
    #                 sys.exit(1)
    #         else:
    #             self.logger.error('### Parameter list can only have depth 0 or 1! Exiting! ###')
    #             sys.exit(1)
    #         return cycles
    #
    #     if mode == 'manual':
    #         self.manual_cycles = correct_cycles(self.manual_cycles, self.manual_nif)
    #     if mode == 'adaptive':
    #         self.adaptive_startinterval = correct_cycles(self.adaptive_startinterval, self.adaptive_nif)
    #         self.adaptive_startuvrange = correct_cycles(self.adaptive_startuvrange, self.adaptive_nif)
    #         self.adaptive_maxcycle = correct_cycles(self.adaptive_maxcycle, self.adaptive_nif)
    #         self.adaptive_drlim = correct_cycles(self.adaptive_drlim, self.adaptive_nif)
    #         self.adaptive_firstniter = correct_cycles(self.adaptive_firstniter, self.adaptive_nif)
    #     if self.parametric == True:
    #         self.parametric_radius = correct_cycles(self.parametric_radius, self.parametric_nif)
    #         self.parametric_cutoff = correct_cycles(self.parametric_cutoff, self.parametric_nif)
    #         self.parametric_distance = correct_cycles(self.parametric_distance, self.parametric_nif)
    #         self.parametric_interval = correct_cycles(self.parametric_interval, self.parametric_nif)
    #         self.parametric_minuvrange = correct_cycles(self.parametric_minuvrange, self.parametric_nif)
    #         self.parametric_maxuvrange = correct_cycles(self.parametric_maxuvrange, self.parametric_nif)
    #         self.parametric_amp = correct_cycles(self.parametric_amp, self.parametric_nif)
    #
    #     def correct_entry(keyword):
    #         value = getattr(self,keyword)
    #         if type(value) is list:
    #             depth = get_depth(value)
    #             if type(depth) is int and depth == 1:
    #                 if len(value) == 1:
    #                     entry = value
    #                     value = [value]
    #                     value.pop(0)
    #                     value.extend(entry*self.manual_cycles[i] for i in range(len((self.manual_nif))))
    #                     self.logger.info('### Using the same values for all subbands and selfcal cycles for keyword ' + str(keyword) + '! ###')
    #                 elif len(value) == self.manual_cycles[0]:
    #                     entry = value
    #                     value = [value]
    #                     value.pop(0)
    #                     value.extend(entry for i in range(len((self.manual_nif))))
    #                     self.logger.info('### Using the same values for all subbands for keyword ' + str(keyword) + '! ###')
    #                 else:
    #                     self.logger.error('### Wrong number of values given for keyword ' + str(keyword) + '! Exiting! ###')
    #                     sys.exit(1)
    #             elif type(depth) is int and depth == 2:
    #                 for m,n in enumerate(self.manual_cycles):
    #                     if len(value[m]) == self.manual_cycles[m]:
    #                         continue
    #                     elif len(value[m]) == 1 and self.manual_cycles[m] != 1:
    #                         value[m] = value[m]*self.manual_cycles[m]
    #                         self.logger.info('### Only one value given for keyword ' + str(keyword) + ' for subband ' + str(self.manual_nif[m]) + '! Using the same value for all selfcal iterations! ###')
    #                     else:
    #                         self.logger.error('### Wrong number of selfcal cycles given for subband ' + str(self.manual_nif[m]) + ' ! Exiting! ###')
    #                         sys.exit(1)
    #             elif type(depth) is int and depth >= 2:
    #                 self.logger.error('### Value ' + str(value) + ' list has the wrong depth! Exiting! ###')
    #                 sys.exit(1)
    #             else:
    #                 self.logger.error('### Value for keyword ' + str(keyword) + ' must be given! Exiting! ###')
    #                 sys.exit(1)
    #         else:
    #             value = [value] * len(self.manual_nif)
    #             entry = value
    #             value = [value]
    #             value.pop(0)
    #             value.extend(entry for i in range(len((self.manual_nif))))
    #         return(value)
    #
    #     if mode == 'manual':
    #         self.manual_minuvrange = correct_entry('manual_minuvrange')
    #         self.manual_maxuvrange = correct_entry('manual_maxuvrange')
    #         self.manual_interval = correct_entry('manual_interval')
    #         self.manual_niters = correct_entry('manual_niters')
    #         self.manual_cleancutoff = correct_entry('manual_cleancutoff')
    #         self.manual_mskcutoff = correct_entry('manual_mskcutoff')

    #######################################################################
    ##### Manage the creation and moving of new directories and files #####
    #######################################################################

    def show(self, showall=False):
        '''
        show: Prints the current settings of the pipeline. Only shows keywords, which are in the default config file default.cfg
        showall: Set to true if you want to see all current settings instead of only the ones from the current step
        '''
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.apercaldir + '/default.cfg'))
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
        self.logger.warning('### Deleting all self-calibrated data. ###')
        self.director('ch', self.selfcaldir)
        self.director('rm', self.selfcaldir + '/*')

    def director(self, option, dest, file=None, verbose=True):
        '''
        director: Function to move, remove, and copy files and directories
        option: 'mk', 'ch', 'mv', 'rm', and 'cp' are supported
        dest: Destination of a file or directory to move to
        file: Which file to move or copy, otherwise None
        '''
        if option == 'mk':
            if os.path.exists(dest):
                pass
            else:
                os.mkdir(dest)
                if verbose == True:
                    self.logger.info('# Creating directory ' + str(dest) + ' #')
        elif option == 'ch':
            if os.getcwd() == dest:
                pass
            else:
                self.lwd = os.getcwd()  # Save the former working directory in a variable
                try:
                    os.chdir(dest)
                except:
                    os.mkdir(dest)
                    if verbose == True:
                        self.logger.info('# Creating directory ' + str(dest) + ' #')
                    os.chdir(dest)
                self.cwd = os.getcwd()  # Save the current working directory in a variable
                if verbose == True:
                    self.logger.info('# Moved to directory ' + str(dest) + ' #')
        elif option == 'mv':  # Move
            if os.path.exists(dest):
                lib.basher("mv " + str(file) + " " + str(dest))
            else:
                os.mkdir(dest)
                lib.basher("mv " + str(file) + " " + str(dest))
        elif option == 'rn':  # Rename
            lib.basher("mv " + str(file) + " " + str(dest))
        elif option == 'cp':  # Copy
            lib.basher("cp -r " + str(file) + " " + str(dest))
        elif option == 'rm':  # Remove
            lib.basher("rm -r " + str(dest))
        else:
            print('### Option not supported! Only mk, ch, mv, rm, rn, and cp are supported! ###')