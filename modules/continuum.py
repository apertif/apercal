__author__ = "Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "adebahr@astron.nl"

import ConfigParser
import logging

import aipy
import numpy as np
import pandas as pd
import os
import sys

import subs.setinit
import subs.managefiles
import subs.combim
import subs.readmirhead
import subs.imstats
import subs.param

from libs import lib


####################################################################################################

class continuum:
    '''
    Continuum class to produce continuum data products (Deep continuum images of individual frequency chunks and stacked continuum image).
    '''
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger('CONTINUUM')
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

    #############################################################
    ##### Function to execute the continuum imaging process #####
    #############################################################

    def go(self):
        '''
        Executes the continuum imaging process in the following order
        image_continuum
        '''
        self.logger.info("########## Starting CONTINUUM IMAGING of beam " + str(self.beam) + " ##########")
        self.image_continuum()
        self.logger.info("########## CONTINUUM IMAGING of beam " + str(self.beam) + " done ##########")

    def image_continuum(self):
        '''
        Create a deep continuum image by producing a deep image of each frequency chunk and stacking. Self-calibration gains are always applied before imaging.
        '''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        self.logger.info('### Starting deep continuum imaging of full dataset ###')
        subs.managefiles.director(self, 'ch', self.contdir)

        #####################
        # Start the imaging #
        #####################

        self.logger.debug('### Creating individual deep images from frequency chunks ###')
        subs.managefiles.director(self,'ch', self.contdir + '/stack')

        ##########################################################################################################
        # Check if the parameter is already in the parameter file and load it otherwise create the needed arrays #
        ##########################################################################################################

        nchunks = len(self.list_chunks())

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_minoriterations'):
            continuumminiters = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_minoriterations')
        else:
            continuumminiters = np.full((nchunks), np.nan) # Number of the last executed minor iterations during imaging

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestats'):
            continuumimagestats = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestats')
        else:
            continuumimagestats = np.full((nchunks, self.continuum_minorcycle, 3), np.nan) # Stats of the created continuum images (minimum, maximum, standard deviation)

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstats'):
            continuumresidualstats = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstats')
        else:
            continuumresidualstats = np.full((nchunks, self.continuum_minorcycle, 3), np.nan) # Stats of the created continuum residual images (minimum, maximum, standard deviation)

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_status'):
            continuumstatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_status')
        else:
            continuumstatus = np.full((nchunks), False) # Status if imaging completed successfully

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestatus'):
            continuumimagestatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestatus')
        else:
            continuumimagestatus = np.full((nchunks, self.continuum_minorcycle), False)  # Was the final image for each iteration created successfully?

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_maskstatus'):
            continuummaskstatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_maskstatus')
        else:
            continuummaskstatus = np.full((nchunks, self.continuum_minorcycle), False)  # Was the mask for each iteration created successfully?

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_modelstatus'):
            continuummodelstatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_modelstatus')
        else:
            continuummodelstatus = np.full((nchunks, self.continuum_minorcycle), False)  # Was the model for each iteration created successfully?

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstatus'):
            continuumresidualstatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstatus')
        else:
            continuumresidualstatus = np.full((nchunks, self.continuum_minorcycle), False)  # Was the residual image for each iteration created successfully?

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_thresholdtype'):
            continuumthresholdtype = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_thresholdtype')
        else:
            continuumthresholdtype = np.full((nchunks, self.continuum_minorcycle), '') # Threshold type for each individual cycle and chunk

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_masklimit'):
            continuummasklimit = subs.param.get_param(self,'continuum_B' + str(self.beam).zfill(2) + '_masklimit')
        else:
            continuummasklimit = np.full((nchunks, self.continuum_minorcycle), np.nan) # Masking threshold for each individual cycle and chunk

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_cleanlimit'):
            continuumcleanlimit = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_cleanlimit')
        else:
            continuumcleanlimit = np.full((nchunks, self.continuum_minorcycle), np.nan) # Cleaning threshold for each individual cycle and chunk

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_synthbeamparams'):
            continuumsynthbeamparams = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_synthbeamparams')
        else:
            continuumsynthbeamparams = np.full((nchunks, 3), np.nan) # Cleaning threshold for each individual cycle and chunk

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackstatus'):
            continuumchunkimageacceptforstacking = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackstatus')
        else:
            continuumchunkimageacceptforstacking = np.full((nchunks), False)  # Is the final image accepted for stacking

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackrejreason'):
            continuumchunkstackrejreason = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackrejreason')
        else:
            continuumchunkstackrejreason = np.full((nchunks), '', dtype='U50')  # Reason for rejecting an image

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombrms'):
            continuumimcombrms = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombrms')
        else:
            continuumimcombrms = np.full((nchunks), np.nan)  # RMS of the final chunk images

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombweights'):
            continuumimcombweights = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombweights')
        else:
            continuumimcombweights = np.full((nchunks), np.nan)  # Weighting of the final chunk images (normalised)

        if subs.param.check_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackedimagestatus'):
            continuumstackedimagestatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackedimagestatus')
        else:
            continuumstackedimagestatus = False  # Is the final image accepted for stacking

        ####################################
        # Imaging of each individual chunk #
        ####################################

        for chunk in self.list_chunks(): # Produce a final image for each chunk doing an additional cleaning run
            self.logger.info('### Continuum imaging for chunk ' + chunk + ' started ###')
            majc = int(self.get_last_major_iteration(chunk))
            self.logger.debug('# Last major self-calibration cycle seems to have been ' + str(majc) + ' #')
            # Check if a chunk could be calibrated and has data left
            if os.path.isfile(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir/gains'):
                subs.managefiles.director(self, 'ch', self.contdir + '/stack/' + chunk)
                # Check if the chunk was already imaged
                if os.path.isdir(self.contdir + '/stack/' + chunk + '/' + 'image_' + str(self.continuum_minorcycle-1).zfill(2)):
                    self.logger.info('# Frequency chunk ' + chunk + ' has already been imaged! #')
                else:

                    #######################
                    # Final deep cleaning #
                    #######################

                    theoretical_noise = self.calc_theoretical_noise(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
                    self.logger.debug('# Theoretical noise for chunk ' + chunk + ' is ' + str(theoretical_noise) + ' Jy/beam #')
                    theoretical_noise_threshold = self.calc_theoretical_noise_threshold(theoretical_noise, self.continuum_nsigma)
                    self.logger.debug('# Your theoretical noise threshold will be ' + str(self.continuum_nsigma) + ' times the theoretical noise corresponding to ' + str(theoretical_noise_threshold) + ' Jy/beam #')
                    dr_list = self.calc_dr_maj(self.continuum_drinit, self.continuum_dr0, majc + 2, self.continuum_majorcycle_function)
                    self.logger.debug('# Dynamic range limits for the selfcal major iterations were ' + str(dr_list) + ' #')
                    dr_minlist = self.calc_dr_min(dr_list, majc + 1, self.continuum_minorcycle, self.continuum_minorcycle_function)
                    self.logger.debug('# Dynamic range limits for the continuum minor iterations to clean are ' + str(dr_minlist) + ' #')

                    #####################################
                    # Run the cleaning minor iterations #
                    #####################################

                    cont = True # Set the cycle continuation trigger to True (changes to False if something goes wrong)
                    for minc in range(self.continuum_minorcycle):
                        if cont:

                            #########################
                            # The first minor cycle #
                            #########################

                            if minc == 0:

                                # Create the dirty image
                                if os.path.isdir('map_00') and os.path.isdir('beam_00'):
                                    self.logger.debug('# Data for chunk ' + str(chunk) + ' has already been inverted #')
                                    mapmin, mapmax, mapstd = subs.imstats.getimagestats(self, 'map_00') # Calculate the image stats for later usage
                                else:
                                    invert = lib.miriad('invert')
                                    invert.vis = self.selfcaldir + '/' + chunk + '/' + chunk + '.mir'
                                    invert.map = 'map_00'
                                    invert.beam = 'beam_00'
                                    invert.imsize = self.continuum_image_imsize
                                    invert.cell = self.continuum_image_cellsize
                                    invert.stokes = 'ii'
                                    invert.slop = 1
                                    if self.continuum_image_robust == '':
                                        invert.robust = -1
                                    else:
                                        invert.robust = self.continuum_image_robust
                                    if self.continuum_image_centre != '':  # Use the image centre given in the cfg file
                                        invert.offset = self.continuum_image_centre
                                        invert.options = 'mfs,double,mosaic'
                                    else:
                                        if os.path.isdir(self.basedir + '00' + '/' + self.selfcalsubdir + '/' + self.target):
                                            invert.offset = subs.readmirhead.getradecsex(self.basedir + '00' + '/' + self.selfcalsubdir + '/' + self.target)
                                            invert.options = 'mfs,double,mosaic'
                                            self.logger.debug('# Using pointing centre of beam 00 for gridding of all beams! #')
                                        else:
                                            invert.options = 'mfs,double,sdb'  # Use the image centre of the individual beams for gridding (not recommended)
                                            self.logger.warning('### Using pointing centres of individual beams for gridding. Not recommended for mosaicking! ###')
                                    invert.go()
                                    if os.path.isdir('map_00') and os.path.isdir('beam_00'): # Check if the image and beam are there
                                        mapmin, mapmax, mapstd = subs.imstats.getimagestats(self, 'map_00')
                                        if mapmax>=mapmin and mapstd!=np.nan: # Check if the dirty image is valid
                                            pass
                                        else: # if not exit the imaging loop
                                            self.logger.error('### Dirty image for chunk '+ str(chunk) + ' was not created successfully! ###')
                                            cont = False
                                            break
                                    else: # if not exit the imaging loop
                                        self.logger.error('### Dirty image and beam for chunk ' + str(chunk) + ' were not created successfully! ###')
                                        cont = False
                                        break

                                # Copy the mask from the last selfcal loop and regrid to the common grid
                                if os.path.isdir('mask_00'): # Has the mask already been copied
                                    continuummaskstatus[int(chunk), minc] = True
                                    self.logger.debug('# Mask for chunk ' + str(chunk) + ' has already been copied from selfcal and regridded #')
                                else: # if not look for it
                                    if os.path.isdir(self.selfcaldir + '/' + chunk + '/' + str(majc).zfill(2) + '/mask_' + str(self.get_last_minor_iteration(chunk, self.get_last_major_iteration(chunk))).zfill(2)): # Find the last created mask
                                        subs.managefiles.director(self, 'cp', 'mask_00', file=self.selfcaldir + '/' + chunk + '/' + str(majc).zfill(2) + '/mask_' + str(self.get_last_minor_iteration(chunk, self.get_last_major_iteration(chunk))).zfill(2))
                                        self.logger.debug('# Mask from last selfcal loop found! #')
                                    else: # If it is not there leave the loop for this chunk
                                        continuummaskstatus[int(chunk), minc] = False
                                        self.logger.error('# Mask from last selfcal loop not found! #')
                                        cont = False
                                        break
                                    regrid = lib.miriad('regrid')
                                    regrid.in_ = 'mask_00'
                                    regrid.out = 'mask_regrid'
                                    regrid.tin = 'map_00'
                                    regrid.axes = '1,2'
                                    regrid.go()
                                    subs.managefiles.director(self, 'rm', 'mask_00')
                                    subs.managefiles.director(self, 'rn', 'mask_00', file='mask_regrid')
                                    self.logger.debug('# Mask from last selfcal cycle copied and regridded to common grid #')
                                    if os.path.isdir('mask_00'):
                                        maskmin, maskmax, maskstd = subs.imstats.getimagestats(self, 'mask_00')
                                        if maskstd != np.nan: # Check if the mask is not empty
                                            continuummaskstatus[int(chunk), minc] = True
                                        else: # if not exit the imaging loop
                                            continuummaskstatus[int(chunk), minc] = False
                                            self.logger.error('### Mask for chunk '+ str(chunk) + ' was not created successfully! ###')
                                            cont = False
                                            break
                                    else: # if not exit the imaging loop
                                        continuummaskstatus[int(chunk), minc] = False
                                        self.logger.error('### Mask for chunk ' + str(chunk) + ' was not created successfully! ###')
                                        cont = False
                                        break

                                # Now calculate the thresholds for the first minor cycles
                                noise_threshold = self.calc_noise_threshold(mapmax, minc, majc + 1, self.continuum_c0)
                                dynamic_range_threshold = self.calc_dynamic_range_threshold(mapmax, dr_minlist[minc], self.continuum_minorcycle0_dr)
                                mask_threshold, mask_threshold_type = self.calc_mask_threshold(theoretical_noise_threshold, noise_threshold, dynamic_range_threshold)
                                self.logger.debug('# Mask threshold for final minor cycle ' + str(minc) + ' set to ' + str(mask_threshold) + ' Jy/beam #')
                                self.logger.debug('# Mask threshold set by ' + str(mask_threshold_type) + ' #')
                                continuumthresholdtype[int(chunk), minc] = str(mask_threshold_type)
                                continuummasklimit[int(chunk), minc] = mask_threshold
                                clean_cutoff = self.calc_clean_cutoff(mask_threshold, self.continuum_c1)
                                continuumcleanlimit[int(chunk), minc] = clean_cutoff
                                self.logger.debug('# Clean threshold for minor cycle ' + str(minc) + ' was set to ' + str(clean_cutoff) + ' Jy/beam #')

                                # Clean the dirty image down to the calculated threshold
                                if os.path.isdir('model_00'): # Has the clean model already been created
                                    continuummodelstatus[int(chunk), minc] = True
                                    self.logger.debug('# Clean model for first minor iteration of chunk ' + str(chunk) + ' has already been created #')
                                else: # if not create it
                                    clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                                    clean.map = 'map_00'
                                    clean.beam = 'beam_00'
                                    clean.out = 'model_00'
                                    clean.cutoff = clean_cutoff
                                    clean.niters = 100000
                                    clean.region = '"' + 'mask(mask_' + str(minc).zfill(2) + ')' + '"'
                                    clean.go()
                                    if os.path.isdir('model_00'):  # Check if it was created successfully
                                        modmin, modmax, modstd = subs.imstats.getimagestats(self, 'model_00')
                                        if modstd != np.nan and modmax<=10000 and modmin>=-10:  # Check if the clean model is valid
                                            continuummodelstatus[int(chunk), minc] = True
                                        else:  # if not exit the imaging loop
                                            continuummodelstatus[int(chunk), minc] = False
                                            self.logger.error('### Model for first minor iteration for chunk ' + str(chunk) + ' is empty or shows extreme values! ###')
                                            cont = False
                                            break
                                    else:  # if not exit the imaging loop
                                        continuummodelstatus[int(chunk), minc] = False
                                        self.logger.error('### Clean model for first minor iteration of chunk ' + str(chunk) + ' was not created successfully! ###')
                                        cont = False
                                        break
                                    self.logger.debug('# Clean model for first minor iteration of chunk ' + str(chunk) + ' was created successfully! #')

                                # Now create the restored image
                                if os.path.isdir('image_00'): # Check if the restored image was already created
                                    continuumimagestatus[int(chunk), minc] = True
                                    self.logger.debug('# Restored image for first minor iteration of chunk ' + str(chunk) + ' has already been created #')
                                else: # if not create it
                                    restor = lib.miriad('restor')
                                    restor.model = 'model_00'
                                    restor.beam = 'beam_00'
                                    restor.map = 'map_00'
                                    restor.out = 'image_00'
                                    restor.mode = 'clean'
                                    restor.go()
                                    if os.path.isdir('image_00'):  # Check if it was created successfully
                                        immin, immax, imstd = subs.imstats.getimagestats(self, 'image_00')
                                        continuumimagestats[int(chunk), minc, :] = np.array([immin, immax, imstd])
                                        if imstd != np.nan and immax <= 10000 and immin >= -10:  # Check if the image is valid
                                            continuumimagestatus[int(chunk), minc] = True
                                        else:  # if not exit the imaging loop
                                            continuumimagestatus[int(chunk), minc] = False
                                            self.logger.error('### Restored image of first minor iteration for chunk ' + str(chunk) + ' is empty or shows extreme values! ###')
                                            cont = False
                                            break
                                    else:  # if not exit the imaging loop
                                        continuumimagestatus[int(chunk), minc] = False
                                        self.logger.error('### Restored image of first minor iteration for chunk ' + str(chunk) + ' was not created successfully! ###')
                                        continuumimagestats[int(chunk), minc, :] = np.array([np.nan, np.nan, np.nan])
                                        cont = False
                                        break
                                    self.logger.debug('# Restored image for first minor iteration of chunk ' + str(chunk) + ' was created successfully! #')

                                # Now create the residual image
                                if os.path.isdir('residual_00'):  # Check if the restored image was already created
                                    continuumresidualstatus[int(chunk), minc] = True
                                    self.logger.debug('# Residual image for first minor iteration of chunk ' + str(chunk) + ' has already been created #')
                                else:  # if not create it
                                    restor = lib.miriad('restor')
                                    restor.model = 'model_00'
                                    restor.beam = 'beam_00'
                                    restor.map = 'map_00'
                                    restor.out = 'residual_00'
                                    restor.mode = 'residual'
                                    restor.go()
                                    if os.path.isdir('residual_00'):  # Check if it was created successfully
                                        resimin, resimax, resistd = subs.imstats.getimagestats(self, 'residual_00')
                                        continuumresidualstats[int(chunk), minc, :] = np.array([resimin, resimax, resistd])
                                        if resistd != np.nan and resimax <= 10000 and resimin >= -10:  # Check if the image is valid
                                            continuumresidualstatus[int(chunk), minc] = True
                                        else:  # if not exit the imaging loop
                                            continuumresidualstatus[int(chunk), minc] = False
                                            self.logger.error('### Residual image of first minor iteration for chunk ' + str(chunk) + ' is empty or shows extreme values! ###')
                                            cont = False
                                            break
                                    else:  # if not exit the imaging loop
                                        continuumresidualstatus[int(chunk), minc] = False
                                        self.logger.error('### Residual image of first minor iteration for chunk ' + str(chunk) + ' was not created successfully! ###')
                                        continuumresidualstats[int(chunk), minc, :] = np.array([np.nan, np.nan, np.nan])
                                        cont = False
                                        break
                                    self.logger.debug('# Residual image for first minor iteration of chunk ' + str(chunk) + ' was created successfully! #')
                                self.logger.debug('# Peak of the residual image for first minor iteration is ' + str(resimax) + ' Jy/beam #')
                                self.logger.debug('# RMS of the residual image for first minor iteration is ' + str(resistd) + ' Jy/beam #')
                                continuumminiters[int(chunk)] = 0

                            ####################################
                            # All minor cycles after the first #
                            ####################################

                            else:
                                # Now calculate the thresholds for the current minor cycle
                                if os.path.isdir('map_00'): # Check if the dirty map is there
                                    mapmin, mapmax, mapstd = subs.imstats.getimagestats(self, 'map_00')  # Calculate the image stats for later usage
                                    if mapmax>=mapmin and mapstd!=np.nan: # Check if the dirty image is valid
                                        pass
                                    else: # if not exit the imaging loop
                                        self.logger.error('### Dirty map for chunk '+ str(chunk) + ' shows extreme values! Cannot calculate thresholds! ###')
                                        cont = False
                                        break
                                else: # if not exit the imaging loop
                                    self.logger.error('### No dirty map for chunk ' + str(chunk) + ' available! ###')
                                    cont = False
                                    break
                                noise_threshold = self.calc_noise_threshold(mapmax, minc, majc + 1, self.continuum_c0)
                                dynamic_range_threshold = self.calc_dynamic_range_threshold(mapmax, dr_minlist[minc], self.continuum_minorcycle0_dr)
                                mask_threshold, mask_threshold_type = self.calc_mask_threshold(theoretical_noise_threshold, noise_threshold, dynamic_range_threshold)
                                self.logger.debug('# Mask threshold for final minor cycle ' + str(minc) + ' set to ' + str(mask_threshold) + ' Jy/beam #')
                                continuumthresholdtype[int(chunk), minc] = str(mask_threshold_type)
                                continuummasklimit[int(chunk), minc] = mask_threshold
                                clean_cutoff = self.calc_clean_cutoff(mask_threshold, self.continuum_c1)
                                continuumcleanlimit[int(chunk), minc] = clean_cutoff
                                self.logger.debug('# Clean threshold for minor cycle ' + str(minc) + ' was set to ' + str(clean_cutoff) + ' Jy/beam #')

                                # Calculate the mask
                                if os.path.isdir('mask_' + str(minc).zfill(2)): # Check if the mask is already there
                                    continuummaskstatus[int(chunk), minc] = True
                                    self.logger.debug('# Mask for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' is already available #')
                                else: # Create the mask
                                    maths = lib.miriad('maths')
                                    maths.out = 'mask_' + str(minc).zfill(2)
                                    maths.exp = '"<' + 'image_' + str(minc - 1).zfill(2) + '>"'
                                    maths.mask = '"<' + 'image_' + str(minc - 1).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
                                    maths.go()
                                    if os.path.isdir('mask_' + str(minc).zfill(2)):  # Check if the mask was created successfully
                                        maskmin, maskmax, maskstd = subs.imstats.getimagestats(self, 'mask_' + str(minc).zfill(2))  # Calculate the mask stats for viability
                                        if maskstd != np.nan: # Check if mask is not empty
                                            continuummaskstatus[int(chunk), minc] = True
                                        else:# If not stop the imaging
                                            continuummaskstatus[int(chunk), minc] = False
                                            self.logger.error('### Mask for minor iteration ' + str(minc).zfill(2) + ' for chunk ' + str(chunk) + ' is empty or shows extreme values! ###')
                                            cont = False
                                            break
                                    else:
                                        continuummaskstatus[int(chunk), minc] = False
                                        self.logger.error('### Mask for minor iteration ' + str(minc).zfill(2) + ' for chunk ' + str(chunk) + ' was not created successfully! ###')
                                        cont = False
                                        break
                                    self.logger.debug('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')

                                # Clean the image with the new mask using the model from the previous iteration
                                if os.path.isdir('model_' + str(minc).zfill(2)): # Has the clean model already been created
                                    continuummodelstatus[int(chunk), minc] = True
                                    self.logger.debug('# Clean model for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' has already been created #')
                                else: # if not create it
                                    clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                                    clean.map = 'map_' + str(0).zfill(2)
                                    clean.beam = 'beam_' + str(0).zfill(2)
                                    clean.model = 'model_' + str(minc - 1).zfill(2)
                                    clean.out = 'model_' + str(minc).zfill(2)
                                    clean.cutoff = clean_cutoff
                                    clean.niters = 100000
                                    clean.region = '"' + 'mask(' + 'mask_' + str(minc).zfill(2) + ')' + '"'
                                    clean.go()
                                    if os.path.isdir('model_' + str(minc).zfill(2)):  # Check if it was created successfully
                                        modmin, modmax, modstd = subs.imstats.getimagestats(self, 'model_' + str(minc).zfill(2))
                                        if modstd != np.nan and modmax <= 10000 and modmin >= -10:  # Check if the clean model is valid
                                            continuummodelstatus[int(chunk), minc] = True
                                        else:  # if not exit the imaging loop
                                            continuummodelstatus[int(chunk), minc] = False
                                            self.logger.error('### Clean model for minor iteration ' + str(minc).zfill(2) + ' for chunk ' + str(chunk) + ' is empty or shows extreme values! ###')
                                            cont = False
                                            break
                                    else:  # if not exit the imaging loop
                                        continuummodelstatus[int(chunk), minc] = False
                                        self.logger.error('### Clean model for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' was not created successfully! ###')
                                        cont = False
                                        break
                                    self.logger.debug('# Clean model for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' was created successfully! #')

                                    # Now create the restored image
                                    if os.path.isdir('image_' + str(minc).zfill(2)):  # Check if the restored image was already created
                                        continuumimagestatus[int(chunk), minc] = True
                                        self.logger.debug('# Restored image for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' has already been created #')
                                    else:  # if not create it
                                        restor = lib.miriad('restor')
                                        restor.model = 'model_' + str(minc).zfill(2)
                                        restor.beam = 'beam_' + str(0).zfill(2)
                                        restor.map = 'map_' + str(0).zfill(2)
                                        restor.out = 'image_' + str(minc).zfill(2)
                                        restor.mode = 'clean'
                                        restor.go()
                                        if os.path.isdir('image_' + str(minc).zfill(2)):  # Check if it was created successfully
                                            immin, immax, imstd = subs.imstats.getimagestats(self, 'image_' + str(minc).zfill(2))
                                            continuumimagestats[int(chunk), minc, :] = np.array([immin, immax, imstd])
                                            if imstd != np.nan and immax <= 10000 and immin >= -10:  # Check if the image is valid
                                                continuumimagestatus[int(chunk), minc] = True
                                            else:  # if not exit the imaging loop
                                                continuumimagestatus[int(chunk), minc] = False
                                                self.logger.error('### Restored image of minor iteration ' + str(minc).zfill(2) + ' for chunk ' + str(chunk) + ' is empty or shows extreme values! ###')
                                                cont = False
                                                break
                                        else:  # if not exit the imaging loop
                                            continuumimagestatus[int(chunk), minc] = False
                                            self.logger.error('### Restored image of minor iteration ' + str(minc).zfill(2) + ' for chunk ' + str(chunk) + ' was not created successfully! ###')
                                            continuumimagestats[int(chunk), minc, :] = np.array([np.nan, np.nan, np.nan])
                                            cont = False
                                            break
                                        self.logger.debug('# Restored image for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' was created successfully! #')

                                    # Now create the residual image
                                    if os.path.isdir('residual_' + str(minc).zfill(2)):  # Check if the restored image was already created
                                        continuumresidualstatus[int(chunk), minc] = True
                                        self.logger.debug('# Residual image for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' has already been created #')
                                    else:  # if not create it
                                        restor = lib.miriad('restor')
                                        restor.model = 'model_' + str(minc).zfill(2)
                                        restor.beam = 'beam_' + str(0).zfill(2)
                                        restor.map = 'map_' + str(0).zfill(2)
                                        restor.out = 'residual_' + str(minc).zfill(2)
                                        restor.mode = 'residual'
                                        restor.go()
                                        if os.path.isdir('residual_' + str(minc).zfill(2)):  # Check if it was created successfully
                                            resimin, resimax, resistd = subs.imstats.getimagestats(self, 'residual_' + str(minc).zfill(2))
                                            continuumresidualstats[int(chunk), minc, :] = np.array([resimin, resimax, resistd])
                                            if resistd != np.nan and resimax <= 10000 and resimin >= -10:  # Check if the image is valid
                                                continuumresidualstatus[int(chunk), minc] = True
                                            else:  # if not exit the imaging loop
                                                continuumresidualstatus[int(chunk), minc] = False
                                                self.logger.error('### Residual image for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' is empty or shows extreme values! ###')
                                                cont = False
                                                break
                                        else:  # if not exit the imaging loop
                                            continuumresidualstatus[int(chunk), minc] = False
                                            self.logger.error('### Residual image for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' was not created successfully! ###')
                                            continuumresidualstats[int(chunk), minc, :] = np.array([np.nan, np.nan, np.nan])
                                            cont = False
                                            break
                                        self.logger.debug('# Residual image for minor iteration ' + str(minc).zfill(2) + ' of chunk ' + str(chunk) + ' was created successfully! #')
                                    self.logger.debug('# Peak of the residual image for minor iteration ' + str(minc).zfill(2) + ' is ' + str(resimax) + ' Jy/beam #')
                                    self.logger.debug('# RMS of the residual image for minor iteration ' + str(minc).zfill(2) + ' is ' + str(resistd) + ' Jy/beam #')
                                    continuumminiters[int(chunk)] = minc

                        #######################################
                        # Imaging did not finish successfully #
                        #######################################

                        else:
                            continuumstatus[int(chunk)] = False

                    # Create a list of files and check if all of them are there
                    filelist = ['map_00', 'beam_00']
                    iterlist = [str(iter) for iter in range(self.continuum_minorcycle)]
                    for map in ['image_', 'mask_', 'model_', 'residual_']:
                        for n in iterlist:
                            filelist.append(map + n.zfill(2))
                    for f in filelist:
                        if os.path.isdir(self.contdir + '/stack/' + chunk + '/' + f):
                            continuumstatus[int(chunk)] = True
                        else:
                            continuumstatus[int(chunk)] = False
                            self.logger.warning('###  Continuum imaging for chunk ' + str(chunk) + ' not successful! ' + file +  ' was not found! ###')
                            continuumchunkstackrejreason[int(chunk)] = file + ' missing'
                            break
            else:
                continuumchunkstackrejreason[int(chunk)] = 'Self-calibration failed'
                self.logger.error('### Chunk ' + str(chunk) + ' could or was not successfully calibrated! No continuum imaging for this chunk possible! ###')


        # Save the derived parameters to the parameter file
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_minoriterations', continuumminiters)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestats', continuumimagestats)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstats', continuumresidualstats)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_status', continuumstatus)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestatus', continuumimagestatus)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_maskstatus', continuummaskstatus)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_modelstatus', continuummodelstatus)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstatus', continuumresidualstatus)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_thresholdtype', continuumthresholdtype)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_masklimit', continuummasklimit)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_cleanlimit', continuumcleanlimit)

        ################################
        # Stacking of continuum images #
        ################################

        status = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_status')
        minoriterations = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_minoriterations')

        # Check if the final stacked continuum image is already available
        if os.path.isdir(self.contdir + '/' + self.target.rstrip('.mir') + '_stack') and os.path.isfile(self.contdir + '/' + self.target.rstrip('.mir') + '_stack.fits'):
            self.logger.info('### Final stacked continuum image is already available! ###')
        else: # if not create it

            # Check if the continuum imaging worked for any of the chunks
            if any(status):
                self.logger.info('### Stacking continuum images of individual frequency chunks ###')
                subs.managefiles.director(self, 'ch', self.contdir + '/stack')
                images = ''

                # Check if continuum imaging was successful and then check the image
                for nch, chstat in enumerate(status):
                    if chstat:
                        lastimage = str(nch).zfill(2) + '/' + 'image_' + str(int(minoriterations[nch])).zfill(2)
                        lastimage_stats = subs.imstats.getimagestats(self, lastimage)
                        if np.isnan(lastimage_stats[2]):  # Check if the image is not blank
                            continuumchunkimageacceptforstacking[nch] = False
                            continuumchunkstackrejreason[nch] = 'Final image not valid'
                            self.logger.warning('# Image from frequency chunk ' + str(nch).zfill(2) + ' is not valid. This image is not added in stacking! #')
                        elif lastimage_stats[1] >= 100000.0:  # Check if the image has high amplitudes
                            continuumchunkimageacceptforstacking[nch] = False
                            continuumchunkstackrejreason[nch] = 'High amplitudes in final image'
                            self.logger.warning('# Image from frequency chunk ' + str(nch).zfill(2) + ' shows high amplitudes and is not added in stacking! #')
                        elif lastimage_stats[0] <= -1.0:  # Check if the image has strong negative residuals
                            continuumchunkimageacceptforstacking[nch] = False
                            continuumchunkstackrejreason[nch] = 'Strong negative residuals in final image'
                            self.logger.warning('# Image from frequency chunk ' + str(nch).zfill(2) + ' shows strong negative residuals and is not added in stacking! #')
                        else:
                            continuumchunkimageacceptforstacking[nch] = True
                            images = images + lastimage + ','
                            continuumsynthbeamparams[nch, :] = subs.readmirhead.getbeamimage(lastimage)

                    else: # Continuum imaging was not successful for a specific chunk
                        continuumchunkimageacceptforstacking[nch] = False
                        continuumchunkstackrejreason[nch] = 'Continuum imaging not successful'
                        self.logger.warning('# Continuum imaging for chunk ' + str(nch).zfill(2) + ' was not successful. Image of this chunk will not be added in stacking! #')

                ########################################
                # Convolve the images to a common beam #
                ########################################

                # Calculate the beam automatically or use the given one from the config-file
                if self.continuum_image_convolbeam == '':

                    # Calculate the common beam and make a list of accepted and rejected chunks and update the parameters for the parameter file
                    avchunklist = np.where(continuumchunkimageacceptforstacking)[0]
                    notavchunklist = np.where(continuumchunkimageacceptforstacking == False)[0]
                    avchunks = [str(x).zfill(2) for x in list(avchunklist)]
                    notavchunks = [str(x).zfill(2) for x in list(notavchunklist)]
                    beamarray = continuumsynthbeamparams[avchunklist, :]
                    rejchunks, stackbeam = subs.combim.calc_synbeam(avchunks, beamarray)
                    if len(rejchunks) == 0:
                        self.logger.debug('# No chunks are rejected due to synthesised beam parameters. #')
                    else:
                        for c in rejchunks:
                            avchunks.remove(c)
                            notavchunks.extend(c)
                            self.logger.warning('# Chunk ' + str(c).zfill(2) + ' was rejected due to synthesised beam parameters! #')
                            continuumchunkimageacceptforstacking[int(c)] = False
                            continuumchunkstackrejreason[int(c)] = 'Synthesised beam parameters'
                        sorted(avchunks)
                        sorted(notavchunks)

                else:
                    beam_parameters = self.continuum_image_convolbeam.split(',')
                    stackbeam = np.array([beam_parameters[0], beam_parameters[1], beam_parameters[2]])

                self.logger.info('# Final beam size is fwhm = ' + str(stackbeam[0]) + ' arcsec , ' + str(stackbeam[1]) + ' arcsec, pa = ' + str(stackbeam[2]) + ' deg')

                # Now convolve the images to the calculated or given beam
                for nch, chstat in enumerate(continuumchunkimageacceptforstacking):
                    if chstat:
                        if os.path.exists(str(nch).zfill(2) + '/' + 'convol_' + str(int(minoriterations[nch])).zfill(2)): # Check if the convolved image is already available
                            self.logger.info('# Convolved image for chunk ' + str(nch).zfill(2) + ' already available! #')
                        else: # if not create it
                            convol = lib.miriad('convol')
                            convol.map = str(nch).zfill(2) + '/' + 'image_' + str(int(minoriterations[nch])).zfill(2)
                            convol.fwhm = str(stackbeam[0]) + ',' + str(stackbeam[1])
                            convol.pa = str(stackbeam[2])
                            convol.out = str(nch).zfill(2) + '/' + 'convol_' + str(int(minoriterations[nch])).zfill(2)
                            convol.options = 'final'
                            convol.go()
                    else:
                        pass

                ###################################
                # Combination of convolved images #
                ###################################

                finalimages = ''
                for nch, chstat in enumerate(continuumchunkimageacceptforstacking):
                    if chstat:
                        residualimage = str(nch).zfill(2) + '/' + 'residual_' + str(int(minoriterations[nch])).zfill(2)
                        finalimage = str(nch).zfill(2) + '/' + 'image_' + str(int(minoriterations[nch])).zfill(2)
                        rms = subs.imstats.getimagestats(self, residualimage)[2]
                        continuumimcombrms[nch] = rms
                        images = finalimages + finalimage
                    else:
                        continuumimcombrms[nch] = np.nan
                continuumimcombweights = (1/continuumimcombrms**2.0)/np.nansum((1/continuumimcombrms**2.0))
                imcombrms = list(continuumimcombrms[~np.isnan(continuumimcombrms)])
                imcomb = lib.miriad('imcomb')
                imcomb.in_ = images.rstrip(',')
                imcomb.out = self.contdir + '/' + self.target.rstrip('.mir') + '_stack'
                imcomb.rms = ','.join(str(e) for e in imcombrms)
                imcomb.options = 'fqaver'
                imcomb.go()
                subs.managefiles.director(self,'rm', self.contdir + '/' + self.target.rstrip('.mir') + '_stack/mask')
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = self.contdir + '/' + self.target.rstrip('.mir') + '_stack'
                fits.out = self.contdir + '/' + self.target.rstrip('.mir') + '_stack.fits'
                fits.go()

                # Check the final stacked continuum image
                if os.path.isdir(self.contdir + '/' + self.target.rstrip('.mir') + '_stack') and os.path.isfile(self.contdir + '/' + self.target.rstrip('.mir') + '_stack.fits'):  # Check if the image file is there
                    stackmin, stackmax, stackstd = subs.imstats.getimagestats(self, self.contdir + '/' + self.target.rstrip('.mir') + '_stack.fits')
                    if stackstd != np.nan and stackmax <= 10000 and stackmin >= -10:  # Check if the image is valid
                        continuumstackedimagestatus = True
                        self.logger.info('### Final deep continuum image is ' + self.contdir + '/' + self.target.rstrip('.mir') + '_stack.fits ###')
                    else: # if not issue a error
                        continuumstackedimagestatus = False
                        self.logger.error('### Final stacked continuum image is empty or shows high values! ###')
                else:  # if not issue an error
                    continuumstackedimagestatus = False
                    self.logger.error('### Final stacked continuum image could not be created! ###')

        # Save the derived parameters to the parameter file
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackstatus', continuumchunkimageacceptforstacking)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackrejreason', continuumchunkstackrejreason)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombrms', continuumimcombrms)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombweights', continuumimcombweights)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackedimagestatus', continuumstackedimagestatus)
        subs.param.add_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_synthbeamparams', continuumsynthbeamparams)



    #########################################
    ### Subroutines for the final imaging ###
    #########################################

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
        if majc == 0:  # Take care about the first major cycle
            prevdr = 0
        else:
            prevdr = dr_maj[majc - 1]
        # The different options to increase the minor cycle threshold
        if function == 'square':
            dr_min = [prevdr + ((dr_maj[majc] - prevdr) * (n ** 2.0)) / ((minorcycles - 1) ** 2.0) for n in range(minorcycles)]
        elif function == 'power':
            dr_min = [prevdr + np.power((dr_maj[majc] - prevdr), (1.0 / (n))) for n in range(minorcycles)][::-1]  # Not exactly need to work on this, but close
        elif function == 'linear':
            dr_min = [(prevdr + ((dr_maj[majc] - prevdr) / (minorcycles - 1)) * n) for n in range(minorcycles)]
        else:
            self.logger.error('### Function for minor cycles not supported! Exiting! ###')
            sys.exit(1)
        if dr_min[0] == 0:
            dr_min[0] = self.continuum_minorcycle0_dr
        else:
            pass
        return dr_min

    def calc_mask_threshold(self, theoretical_noise_threshold, noise_threshold, dynamic_range_threshold):
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

    def calc_noise_threshold(self, imax, minor_cycle, major_cycle, c0):
        '''
        Calculates the noise threshold
        imax (float): the maximum in the input image
        minor_cycle (int): the current minor cycle the self-calibration is in
        major_cycle (int): the current major cycle the self-calibration is in
        returns (float): the noise threshold
        '''
        noise_threshold = imax / ((c0 + (minor_cycle) * c0) * (major_cycle + 1))
        return noise_threshold

    def calc_clean_cutoff(self, mask_threshold, c1):
        '''
        Calculates the cutoff for the cleaning
        mask_threshold (float): the mask threshold to calculate the clean cutoff from
        returns (float): the clean cutoff
        '''
        clean_cutoff = mask_threshold / c1
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

    def calc_theoretical_noise_threshold(self, theoretical_noise, nsigma):
        '''
        Calculates the theoretical noise threshold from the theoretical noise
        theoretical_noise (float): the theoretical noise of the observation
        returns (float): the theoretical noise threshold
        '''
        theoretical_noise_threshold = (nsigma * theoretical_noise)
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
        obsrms.bw = np.abs(uv['sdf'] * uv['nschan']) * 1000.0
        obsrms.inttime = 12.0 * 60.0
        obsrms.coreta = 0.88
        theorms = float(obsrms.go()[-1].split()[3]) / 1000.0
        return theorms

    def list_chunks(self):
        '''
        Checks how many chunk directories exist and returns a list of them
        '''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        for n in range(100):
            if os.path.isdir(self.selfcaldir + '/' + str(n).zfill(2)):
                pass
            else:
                break  # Stop the counting loop at the directory you cannot find anymore
        chunks = range(n)
        chunkstr = [str(i).zfill(2) for i in chunks]
        return chunkstr

    def get_last_major_iteration(self, chunk):
        '''
        Get the number of the last major iteration
        chunk: The frequency chunk to look into. Usually an entry generated by list_chunks
        return: The number of the last major clean iteration for a frequency chunk
        '''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        for n in range(100):
            if os.path.isdir(self.selfcaldir + '/' + str(chunk) + '/' + str(n).zfill(2)):
                pass
            else:
                break  # Stop the counting loop at the file you cannot find anymore
        lastmajor = n-1
        return lastmajor

    def get_last_minor_iteration(self, chunk, maj):
        '''
        Get the number of the last minor iteration
        chunk: The frequency chunk to look into. Usually an entry generated by list_chunks
        maj: Number of the last major iteration
        return: The number of the last major clean iteration for a frequency chunk
        '''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        for n in range(100):
            if os.path.isdir(self.selfcaldir + '/' + str(chunk) + '/' + str(maj).zfill(2) + '/' + 'image_' + str(n).zfill(2)):
                pass
            else:
                break  # Stop the counting loop at the file you cannot find anymore
        lastminor = n-1
        return lastminor

    ######################################################################
    ##### Functions to create the summaries of the CONTINUUM imaging #####
    ######################################################################

    def summary(self):
        '''
        Creates a general summary of the parameters in the parameter file generated during the continuum imaging. A more detailed summary can be generated by the detailed_summary function
        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        '''

        # Load the parameters from the parameter file

        IT = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_minoriterations')
        ST = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_status')
        SBEAMS = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_synthbeamparams')
        STST = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackstatus')
        ICW = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombweights')
        RR = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackrejreason')

        # Create the data frame

        chunk_indices = self.list_chunks()

        df_it = pd.DataFrame(np.ndarray.flatten(IT), index=chunk_indices, columns=['Iterations'])
        df_st = pd.DataFrame(np.ndarray.flatten(ST), index=chunk_indices, columns=['Success?'])
        df_bmaj = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 0]), decimals=2), index=chunk_indices, columns=['Bmaj ["]'])
        df_bmin = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 1]), decimals=2), index=chunk_indices, columns=['Bmin ["]'])
        df_bpa = pd.DataFrame(np.around(np.ndarray.flatten(SBEAMS[:, 2]), decimals=2), index=chunk_indices, columns=['Bpa [deg]'])
        df_icw = pd.DataFrame(np.around(np.ndarray.flatten(ICW), decimals=5), index=chunk_indices, columns=['Image weight'])

        df_stst = pd.DataFrame(np.ndarray.flatten(STST), index=chunk_indices, columns=['Accepted?'])
        df_rr = pd.DataFrame(np.ndarray.flatten(RR), index=chunk_indices, columns=['Reason'])

        df = pd.concat([df_it, df_st, df_bmaj, df_bmin, df_bpa, df_icw, df_stst, df_rr], axis=1)

        return df

    def detailed_summary(self):
        '''
        Creates a detailed summary of the parameters in the parameter file generated during the continuum imaging
        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        '''

        # Load the parameters from the parameter file

        IMST = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestats')
        RSST = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstats')
        IMstatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestatus')
        MAstatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_maskstatus')
        MOstatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_modelstatus')
        REstatus = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstatus')
        TH = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_thresholdtype')
        MLIM = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_masklimit')
        CLIM = subs.param.get_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_cleanlimit')

        # Create the data frames

        chunk_iter_indices = pd.MultiIndex.from_product([self.list_chunks(), np.arange(0, self.continuum_minorcycle)], names=['Chunk', 'Iter #'])

        df_th = pd.DataFrame(np.ndarray.flatten(TH), index = chunk_iter_indices, columns = ['TH type'])

        df_mastat = pd.DataFrame(np.ndarray.flatten(MAstatus), index=chunk_iter_indices, columns=['Mask created/ valid?'])
        df_malim = pd.DataFrame(np.around(np.ndarray.flatten(MLIM), decimals=5), index = chunk_iter_indices, columns = ['Mask Limit'])

        df_mostat = pd.DataFrame(np.ndarray.flatten(MOstatus), index=chunk_iter_indices, columns=['Model created/ valid?'])
        df_clim = pd.DataFrame(np.around(np.ndarray.flatten(CLIM), decimals=5), index = chunk_iter_indices, columns = ['Clean Limit'])

        df_imstat = pd.DataFrame(np.ndarray.flatten(IMstatus), index=chunk_iter_indices, columns=['Image created/ valid?'])
        df_immin = pd.DataFrame(np.around(np.ndarray.flatten(IMST[:, :, 0]), decimals=5), index = chunk_iter_indices, columns = ['Image Min'])
        df_immax = pd.DataFrame(np.around(np.ndarray.flatten(IMST[:, :, 1]), decimals=5), index = chunk_iter_indices, columns = ['Image Max'])
        df_imstd = pd.DataFrame(np.around(np.ndarray.flatten(IMST[:, :, 2]), decimals=5), index = chunk_iter_indices, columns = ['Image StD'])

        df_restat = pd.DataFrame(np.ndarray.flatten(REstatus), index=chunk_iter_indices, columns=['Residual created/ valid?'])
        df_rdmin = pd.DataFrame(np.around(np.ndarray.flatten(RSST[:, :, 0]), decimals=5), index = chunk_iter_indices, columns = ['Residual Image Min'])
        df_rdmax = pd.DataFrame(np.around(np.ndarray.flatten(RSST[:, :, 1]), decimals=5), index = chunk_iter_indices, columns = ['Residual Image Max'])
        df_rdstd = pd.DataFrame(np.around(np.ndarray.flatten(RSST[:, :, 2]), decimals=5), index = chunk_iter_indices, columns = ['Residual Image StD'])

        # Combine all the data frames into one to display

        df = pd.concat([df_th, df_mastat, df_malim, df_mostat, df_clim, df_imstat, df_immin, df_immax, df_imstd, df_restat, df_rdmin, df_rdmax, df_rdstd], axis=1)

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
                if s == 'CONTINUUM':
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
        Function to reset the current step and remove all generated data including continuum parameters in the parameter file. Be careful! Deletes all data generated in this step!
        '''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        self.logger.warning('### Deleting all continuum data products. ###')
        subs.managefiles.director(self,'ch', self.contdir)
        subs.managefiles.director(self,'rm', self.contdir + '/*')
        self.logger.warning('### Deleteing all parameter file entries for CONTINUUM module ###')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcomb_rms')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_minoriterations')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestats')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_maskstatus')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_modelstatus')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imagestatus')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstatus')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_residualstats')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_status')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_thresholdtype')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_masklimit')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_cleanlimit')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_synthbeamparams')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackstatus')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackrejreason')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombrms')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_imcombweights')
        subs.param.del_param(self, 'continuum_B' + str(self.beam).zfill(2) + '_stackedimagestatus')