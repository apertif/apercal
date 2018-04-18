__author__ = "Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "adebahr@astron.nl"

import ConfigParser
import glob
import logging

import numpy as np
import os

import subs.setinit
import subs.managefiles
import subs.readmirhead
import subs.imstats
import subs.param
import subs.combim

from libs import lib


####################################################################################################

class mosaic:
    '''
    Mosaic class to produce mosaics of continuum, line and polarisation images.
    '''
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger('MOSAIC')
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

    #############################################
    ##### Function to execute the mosaicing #####
    #############################################

    def go(self):
        '''
        Executes the mosaicking process in the following order
        mosaic_continuum
        mosaic_line
        mosaic_polarisation
        '''
        self.logger.info("########## Starting MOSAICKING ##########")
        self.mosaic_continuum_images()
        self.mosaic_continuum_chunk_images()
        self.mosaic_line_cubes()
        self.mosaic_stokes_images()
        self.logger.info("########## MOSAICKING done ##########")

    def mosaic_continuum_images(self):
        '''Looks for all available stacked continuum images and mosaics them into one large image.'''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        if self.mosaic_continuum_stack:
            self.logger.info('### Starting mosaicking of stacked continuum images ###')
            subs.managefiles.director(self, 'ch', self.mosdir + '/continuum')
            if os.path.isfile(self.target.rstrip('.mir') + '_contmosaic.fits'):
                self.logger.warning('### Stacked continuum mosaic already present. ###')
            else:
                stackedimages = sorted(glob.glob(self.basedir + '[0-9][0-9]/' + self.contsubdir + '/' + self.target.rstrip('.mir') + '_stack'))
                if len(stackedimages) == 0:
                    self.logger.error('### Could not find any stacked continuum images! ###')
                else:
                    beamnumbers = []
                    # Create the variables to be saved to the paramater file
                    # Parameters are ordered in the numpy array as follows:
                    # (0)bmaj, (1)bmin, (2)bpa, (3)image_min, (4)image_max, (5)image_rms, (6) resi_rms
                    stackedparams = np.full((37,7), np.nan)
                    for image in stackedimages:
                        beamnumber = image.split('/')[-3]
                        beamnumbers.append(beamnumber)
                        self.logger.debug('# Continuum image for beam ' + str(beamnumber) + ' found #')
                        subs.managefiles.director(self, 'cp', str(beamnumber), file=image)
                        stackedparams[int(beamnumber), 0:3] = subs.readmirhead.getbeamimage(beamnumber)
                        stackedparams[int(beamnumber), 3:6] = subs.imstats.getimagestats(self, beamnumber)
                        if subs.param.check_param(self, 'continuum_B' + str(beamnumber).zfill(2) + '_imcomb_rms'):
                            beamchunksresirms = subs.param.get_param(self, 'continuum_B' + str(beamnumber).zfill(2) + '_imcomb_rms')
                            beamresirms = 1.0 / np.sqrt(np.sum(1.0 / np.square(beamchunksresirms))) # Calculate the rms of the individual stacked beam images
                        else:
                            beamresirms = 0.0
                        stackedparams[int(beamnumber), 6] = beamresirms
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_available', beamnumbers)
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_bmaj', stackedparams[:, 0])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_bmin', stackedparams[:, 1])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_bpa', stackedparams[:, 2])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_imagemin', stackedparams[:, 3])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_imagemax', stackedparams[:, 4])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_imagerms', stackedparams[:, 5])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_resirms', stackedparams[:, 6])
                    # Check the beam sizes of the images and reject any outliers
                    rejbeams, beampars = subs.combim.calc_synbeam(beamnumbers, stackedparams[:, 0:3])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_rejected', sorted(rejbeams, reverse=True))
                    subs.param.add_param(self, 'mosaic_continuum_stacked_beams_accepted', sorted(list(set(beamnumbers) - set(rejbeams))))
                    subs.param.add_param(self, 'mosaic_continuum_stacked_bmaj', beampars[0])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_bmin', beampars[1])
                    subs.param.add_param(self, 'mosaic_continuum_stacked_bpa', beampars[2])
                    linmosrms = stackedparams[:, 6]
                    for beam in rejbeams: # Remove the rejected beams from the list and delete the file in the mosaic directory
                        self.logger.warning('### Beam ' + beam + ' has been rejected due to differing synthesised beam size! ###')
                        rejindex = beamnumbers.index(beam)
                        stackedimages.pop(rejindex)
                        linmosrms = np.delete(linmosrms, beam)
                        subs.managefiles.director(self, 'rm', str(beam))
                    linmosrms = np.round(linmosrms[~np.isnan(linmosrms)], decimals=7)
                    # Convolve all beams to the same synthesised beam
                    toconvolimages = glob.glob('[0-9][0-9]')
                    convolimages = ''
                    for image in toconvolimages:
                        convol = lib.miriad('convol')
                        convol.map = image
                        convol.fwhm = str(beampars[0]) + ',' + str(beampars[1])
                        convol.pa = str(beampars[2])
                        convol.out = 'c' + image
                        convol.options = 'final'
                        convol.go()
                        convolimages = convolimages + convol.out + ','
                    # Combine the images using the WSRT beam model with linmos
                    linmos = lib.miriad('linmos')
                    linmos.in_ = convolimages.rstrip(',')
                    if 0.0 in linmosrms: # Use the noise values of the residual images of the continuum calibration if available
                        self.logger.warning('### Information of noise values for beams from continuum imaging not available for all chunks. Using theoretical noise values for all images! ###')
                    else:
                        linmos.rms = ','.join(str(rms) for rms in linmosrms)
                    linmos.out = self.target.rstrip('.mir') + '_contmosaic'
                    linmos.go()
                    subs.managefiles.imagetofits(self, self.target.rstrip('.mir') + '_contmosaic', self.target.rstrip('.mir') + '_contmosaic.fits')
                    if os.path.isfile(self.target.rstrip('.mir') + '_contmosaic.fits'):
                        subs.param.add_param(self, 'mosaic_continuum_stacked_status', True)
                        subs.managefiles.director(self, 'rm', '[0-9][0-9]')
                        subs.managefiles.director(self, 'rm', 'c[0-9][0-9]')
                    else:
                        self.logger.error('# Final stacked continuum mosaic was not created successfully! #')
                        subs.param.add_param(self, 'mosaic_continuum_stacked_status', False)
                    self.logger.info('### Mosaicking of stacked continuum images done ###')
            subs.managefiles.director(self, 'ch', self.basedir)
        else:
            self.logger.info('### No mosaicking of stacked continuum images done ###')

    def mosaic_continuum_chunk_images(self):
        '''Looks for the continuum images from the different frequency chunks and mosaics them.'''
        subs.setinit.setinitdirs(self)
        subs.setinit.setdatasetnamestomiriad(self)
        if self.mosaic_continuum_chunks:
            self.logger.info('### Starting mosaicking of continuum images of individual frequency chunks ###')
            subs.managefiles.director(self, 'ch', self.mosdir + '/continuum')
            # Collect the images from the individual frequency chunks #
            for chunk in range(100):
                if os.path.isfile(self.target.rstrip('.mir') + '_chunk_' + str(chunk).zfill(2) + '_contmosaic.fits'):
                    self.logger.warning('### Final continuum mosaic of frequency chunk ' + str(chunk).zfill(2) + ' already present! ###')
                else:
                    chunkimages = glob.glob(self.basedir + '[0-9][0-9]/' + self.contsubdir + '/stack/' + str(chunk).zfill(2) + '/image_' + str(self.continuum_minorcycle - 1).zfill(2))
                    if len(chunkimages) > 0:
                        self.logger.debug('# Images for frequency chunk ' + str(chunk).zfill(2) + ' found! #')
                        stackedchunkparams = np.full((37, 7), np.nan) # Create an array for the parameters of the chunks
                        beamnumbers = []
                        for image in chunkimages:
                            beamnumber = image.split('/')[-5]
                            beamnumbers.append(beamnumber)
                            subs.managefiles.director(self, 'cp', str(beamnumber), file=image)
                            stackedchunkparams[int(beamnumber), 0:3] = subs.readmirhead.getbeamimage(beamnumber)
                            stackedchunkparams[int(beamnumber), 3:6] = subs.imstats.getimagestats(self, beamnumber)
                            residual = image.replace('image', 'residual') # Get the rms from the residual in the original continuum directory
                            stackedchunkparams[int(beamnumber), 6] = subs.imstats.getimagestats(self, residual)[2]
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_available', beamnumbers)
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_bmaj', stackedchunkparams[:, 0])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_bmin', stackedchunkparams[:, 1])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_bpa', stackedchunkparams[:, 2])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_imagemin', stackedchunkparams[:, 3])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_imagemax', stackedchunkparams[:, 4])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_imagerms', stackedchunkparams[:, 5])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_resirms', stackedchunkparams[:, 6])
                        # Check the beam sizes of the images and reject any outliers
                        rejbeams, beampars = subs.combim.calc_synbeam(beamnumbers, stackedchunkparams[:, 0:3])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_rejected', sorted(rejbeams, reverse=True))
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_beams_accepted', sorted(list(set(beamnumbers) - set(rejbeams))))
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_bmaj', beampars[0])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_bmin', beampars[1])
                        subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_bpa', beampars[2])
                        linmosrms = stackedchunkparams[:, 6]
                        for beam in rejbeams:  # Remove the rejected beams from the list and delete the file in the mosaic directory
                            self.logger.warning('### Beam ' + beam + ' of frequency chunk ' + str(chunk).zfill(2) + ' has been rejected due to differing synthesised beam size! ###')
                            rejindex = beamnumbers.index(beam)
                            chunkimages.pop(rejindex)
                            linmosrms = np.delete(linmosrms, beam)
                            subs.managefiles.director(self, 'rm', str(beam))
                        linmosrms = np.round(linmosrms[~np.isnan(linmosrms)], decimals=7)
                        # Convolve all beams to the same synthesised beam
                        self.logger.debug('# Convolving images of frequency chunk ' + str(chunk).zfill(2) + ' to common beam size of FWHM=' + str(beampars[0]) + ',' + str(beampars[1]) + ' and PA=' + str(beampars[2]) + ' #')
                        toconvolimages = glob.glob('[0-9][0-9]')
                        convolimages = ''
                        for image in toconvolimages:
                            convol = lib.miriad('convol')
                            convol.map = image
                            convol.fwhm = str(beampars[0]) + ',' + str(beampars[1])
                            convol.pa = str(beampars[2])
                            convol.out = 'c' + image
                            convol.options = 'final'
                            convol.go()
                            convolimages = convolimages + convol.out + ','
                        # Combine the images using the WSRT beam model with linmos
                        self.logger.debug('# Combining images of frequency chunk ' + str(chunk).zfill(2) + '! #')
                        linmos = lib.miriad('linmos')
                        linmos.in_ = convolimages.rstrip(',')
                        linmos.rms = ','.join(str(rms) for rms in linmosrms)
                        self.logger.debug('# RMS of the images is ' + linmos.rms + ' #')
                        linmos.out = self.target.rstrip('.mir') + '_chunk_' + str(chunk).zfill(2) + '_contmosaic'
                        linmos.go()
                        subs.managefiles.imagetofits(self, self.target.rstrip('.mir') + '_chunk_' + str(chunk).zfill(2) + '_contmosaic', self.target.rstrip('.mir') + '_chunk_' + str(chunk).zfill(2) + '_contmosaic.fits')
                        if os.path.isfile(self.target.rstrip('.mir') + '_chunk_' + str(chunk).zfill(2) + '_contmosaic.fits'):
                            subs.managefiles.director(self, 'rm', '[0-9][0-9]')
                            subs.managefiles.director(self, 'rm', 'c[0-9][0-9]')
                            self.logger.info('# Final continuum mosaicking of frequency chunk ' + str(chunk).zfill(2) + ' successful! #')
                            subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_status', True)
                        else:
                            self.logger.error('# Final continuum mosaicking of frequency chunk ' + str(chunk).zfill(2) + ' NOT successful! #')
                            subs.param.add_param(self, 'mosaic_continuum_chunk_' + str(chunk).zfill(2) + '_status', False)
                    else: # If list is empty continue with next chunk
                        pass
            subs.managefiles.director(self, 'ch', self.basedir)
            self.logger.info('### Mosaicking of continuum images from individual frequency chunks done ###')

    def mosaic_line_cubes(self):
        '''Creates a mosaicked line cube of all the individual line cubes from the different beams'''
        self.logger.error('### Mosaicking of line cubes not implemented yet ###')

    def mosaic_stokes_images(self):
        '''Creates a mosaic of all the Stokes Q- and U-cubes from the different beams'''
        self.logger.error('### Mosaicking of Stokes cubes not implemented yet ###')


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
                if s == 'MOSAIC':
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
        self.logger.warning('### Deleting all mosaicked data products. ###')
        subs.managefiles.director(self,'ch', self.basedir)
        subs.managefiles.director(self,'rm', self.mosdir)