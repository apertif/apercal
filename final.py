__author__ = "Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "adebahr@astron.nl"

import lib
import logging
import os,sys
import ConfigParser
import lsm
import aipy
import numpy as np
import astropy.io.fits as pyfits

####################################################################################################

class final:
    '''
    final: Final class
    '''
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('FINAL')
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values for final! ###')
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

    #########################################################
    ##### Function to execute the final imaging process #####
    #########################################################

    def go(self):
        '''
        Executes the whole final imaging process.
        '''
        self.logger.info("########## Starting FINAL IMAGING ##########")
        self.continuum()
        self.line()
        self.polarisation()
        self.logger.info("########## FINAL IMAGING done ##########")

    def continuum(self):
        '''
        Create a deep continuum image by whether producing a deep image of each freqeucny chunk and stacking in the end (option stack) or combining all datasets into one and creating a deep multi-frequency image (option mf). Self=calibration gains are always applied before imaging.
        '''
        if self.final_continuum:
            self.logger.info('### Starting deep continuum imaging of full dataset ###')
            self.director('ch', self.finaldir)
            self.director('ch', self.finaldir + '/continuum')
            if self.final_continuum_mode == 'stack':
                self.logger.info('### Creating individual deep images from frequency chunks ###')
                self.director('ch', self.finaldir + '/continuum/stack')
                for chunk in self.list_chunks(): # Produce an image for each chunk
                    self.director('ch', self.finaldir + '/continuum/stack/' + chunk)
                    theoretical_noise = self.calc_theoretical_noise(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
                    self.logger.info('# Theoretical noise for chunk ' + chunk + ' is ' + str(theoretical_noise / 1000) + ' Jy/beam #')
                    for minc in range(self.final_continuum_minorcycle): # Iterate over the minor imaging cycles and masking
                        if minc == 0:
                            invert = lib.miriad('invert')  # Create the dirty image
                            invert.vis = self.selfcaldir + '/' + chunk + '/' + chunk + '.mir'
                            invert.map = 'map_' + str(minc).zfill(2)
                            invert.beam = 'beam_' + str(minc).zfill(2)
                            invert.imsize = self.final_continuum_image_imsize
                            invert.cell = self.final_continuum_image_cellsize
                            invert.stokes = 'i'
                            invert.options = 'mfs,double'
                            invert.slop = 1
                            invert.go()
                            fits = lib.miriad('fits')  # Convert to fits format
                            fits.op = 'xyout'
                            fits.in_ = 'map_' + str(minc).zfill(2)
                            fits.out = 'map_' + str(minc).zfill(2) + '.fits'
                            fits.go()
                            image = pyfits.open('map_' + str(minc).zfill(2) + '.fits')  # Get the maximum in the image
                            data = image[0].data
                            imax = np.max(data)
                            self.logger.info('# Maximum value in the image is ' + str(imax) + ' Jy/beam #')
                            self.director('rm', 'map_' + str(minc).zfill(2) + '.fits')  # Remove the obsolete fits file
                            mask_threshold = self.calc_mask_threshold(imax, minc)
                            self.logger.info('# Mask threshold minor cycle ' + str(minc) + ' is ' + str(mask_threshold) + ' Jy/beam #')
                            maths = lib.miriad('maths')
                            maths.out = 'mask_' + str(minc).zfill(2)
                            maths.exp = '"<map_' + str(minc).zfill(2) + '>"'
                            maths.mask = '"<map_' + str(minc).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
                            maths.go()
                            self.logger.info('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
                            clean_noise_threshold = self.calc_clean_noise_threshold(imax, minc)
                            self.logger.info('# Clean noise threshold at minor cycle ' + str(minc) + ' is ' + str(clean_noise_threshold) + ' Jy/beam #')
                            clean_threshold = np.max([clean_noise_threshold, theoretical_noise])
                            self.logger.info('# Clean threshold at minor cycle ' + str(minc) + ' was set to ' + str(clean_threshold) + ' Jy/beam #')
                            clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                            clean.map = 'map_' + str(0).zfill(2)
                            clean.beam = 'beam_' + str(0).zfill(2)
                            clean.out = 'model_' + str(minc).zfill(2)
                            clean.cutoff = clean_threshold
                            clean.niters = 1000000
                            clean.region = '"' + 'mask(mask_' + str(minc).zfill(2) + ')' + '"'
                            clean.go()
                            self.logger.info('Minor cycle ' + str(minc) + ' cleaning done #')
                            restor = lib.miriad('restor')
                            restor.model = 'model_' + str(minc).zfill(2)
                            restor.beam = 'beam_' + str(0).zfill(2)
                            restor.map = 'map_' + str(0).zfill(2)
                            restor.out = 'image_' + str(minc).zfill(2)
                            restor.mode = 'clean'
                            restor.go()  # Create the cleaned image
                            self.logger.info('# Cleaned image for minor cycle ' + str(minc) + ' created #')
                            restor.mode = 'residual'
                            restor.out = 'residual_' + str(minc).zfill(2)
                            restor.go()
                            self.logger.info('# Residual image for major/minor cycle ' + str(minc) + ' created #')
                        else:
                            fits = lib.miriad('fits')
                            fits.op = 'xyout'
                            fits.in_ = 'residual_' + str(minc - 1).zfill(2)
                            fits.out = 'residual_' + str(minc - 1).zfill(2) + '.fits'
                            fits.go()
                            image = pyfits.open('residual_' + str(minc - 1).zfill(2) + '.fits')  # Get the maximum in the image
                            data = image[0].data
                            imax = np.max(data)
                            self.logger.info('# Maximum value in the image at minor cycle ' + str(minc) + ' is ' + str(imax) + ' Jy/beam #')
                            self.director('rm', 'residual_' + str(minc - 1).zfill(2) + '.fits')  # Remove the obsolete fits file
                            mask_threshold = self.calc_mask_threshold(imax, minc)
                            self.logger.info('# Mask threshold at minor cycle ' + str(minc) + ' is ' + str(mask_threshold) + ' Jy/beam #')
                            maths = lib.miriad('maths')
                            maths.out = 'mask_' + str(minc).zfill(2)
                            maths.exp = '"<residual_' + str(minc - 1).zfill(2) + '>"'
                            maths.mask = '"<residual_' + str(minc - 1).zfill(2) + '>.gt.' + str(mask_threshold) + '"'
                            maths.go()
                            self.logger.info('# Mask with threshold ' + str(mask_threshold) + ' Jy/beam created #')
                            clean_noise_threshold = self.calc_clean_noise_threshold(imax, minc)
                            self.logger.info('# Clean noise threshold at minor cycle ' + str(minc) + ' is ' + str(clean_noise_threshold) + ' Jy/beam #')
                            clean_threshold = np.max([clean_noise_threshold, theoretical_noise])
                            self.logger.info('# Clean threshold at major/minor cycle ' + str(minc) + ' was set to ' + str(clean_threshold) + ' Jy/beam #')
                            clean = lib.miriad('clean')  # Clean the image down to the calculated threshold
                            clean.map = 'map_' + str(0).zfill(2)
                            clean.beam = 'beam_' + str(0).zfill(2)
                            clean.model = 'model_' + str(minc - 1).zfill(2)
                            clean.out = 'model_' + str(minc).zfill(2)
                            clean.cutoff = clean_threshold
                            clean.niters = 1000000
                            clean.region = '"' + 'mask(mask_' + str(minc).zfill(2) + ')' + '"'
                            clean.go()
                            self.logger.info('# Minor cycle ' + str(minc) + ' cleaning done #')
                            restor = lib.miriad('restor')
                            restor.model = 'model_' + str(minc).zfill(2)
                            restor.beam = 'beam_' + str(0).zfill(2)
                            restor.map = 'map_' + str(0).zfill(2)
                            restor.out = 'image_' + str(minc).zfill(2)
                            restor.mode = 'clean'
                            restor.go()  # Create the cleaned image
                            self.logger.info('# Cleaned image for minor cycle ' + str(minc) + ' created #')
                            restor.mode = 'residual'
                            restor.out = 'residual_' + str(minc).zfill(2)
                            restor.go()
                            self.logger.info('# Residual image for Minor cycle ' + str(minc) + ' created #')
                self.logger.info('### Stacking images of individual frequency chunks ###')
                self.director('ch', self.finaldir + '/continuum/stack')
                linmos = lib.miriad('linmos')
                images = ''
                for chunk in self.list_chunks():
                    images = images + chunk + '/' + 'image_' + str(self.final_continuum_minorcycle -1).zfill(2) + ','
                linmos.in_ = images.rstrip(',')
                linmos.out = self.target.rstrip('.mir') + '_stack_linmos'
                linmos.go()
                self.logger.info('### Final deep continuum image is ' + self.finaldir + '/continuum/stack/' + self.target.rstrip('.mir') + '_stack_linmos ###')
            elif self.final_continuum_mode == 'mf':
                self.logger.info('### Combining frequency chunks in the (u,v)-plane and creating an mfclean image ###')
                self.director('ch', self.finaldir + '/continuum/mf')
                self.logger.info('# Copying calibrated datasets to ' + self.finaldir + '/continuum/mf')
                for chunk in self.list_chunks(): # Copy the datasets over to keep pathnames short
                    self.director('cp', '.', self.selfcaldir + '/' + chunk + '/' + chunk + '.mir')
                uvcat = lib.miriad('uvcat')
                datasets = ''  # Create a string for the uvcat task containing all datasets
                for chunk in self.list_chunks():
                    datasets = datasets + chunk + '.mir,'
                uvcat.vis = datasets.rstrip(',')
                uvcat.out = self.target
                uvcat.go()
                theoretical_noise = self.calc_theoretical_noise(self.target)
                self.logger.info('# Theoretical noise for combined dataset is ' + str(theoretical_noise / 1000) + ' Jy/beam #')
            self.logger.info('### Deep continuum imaging of full dataset done ###')

    def calc_mask_threshold(self, imax, minor_cycle):
        '''
        Calculates the mask threshold
        imax: the maximum in the input image
        minor_cycle: the current minor cycle the self-calibration is in
        major_cycle: the current major cycle the self-calibration is in
        returns: the mask threshold
        '''
        mask_threshold = imax / ((self.final_continuum_c0 + (minor_cycle) * self.final_continuum_c0))
        return mask_threshold

    def calc_clean_noise_threshold(self, imax, minor_cycle):
        '''
        Calculates the clean nosie threshold
        imax: the maximum in the input image
        minor_cycle: the current minor cycle the self-calibration is in
        major_cycle: the current major cycle the self-calibration is in
        returns: the clean noise threshold
        '''
        clean_noise_threshold = imax / (((self.final_continuum_c0 + (minor_cycle) * self.final_continuum_c0)) * self.final_continuum_c1)
        return clean_noise_threshold

    def calc_theoretical_noise_threshold(self, theoretical_noise):
        '''
        Calculates the theoretical noise threshold from the theoretical noise
        theoretical_noise: the theoretical noise of the observation
        returns: the theoretical noise threshold
        '''
        theoretical_noise_threshold = (self.final_continuum_nsigma * theoretical_noise)
        return theoretical_noise_threshold

    def calc_theoretical_noise(self, dataset):
        '''
        Calculate the theoretical rms of a given dataset
        dataset: The input dataset to calculate the theoretical rms from
        returns: The theoretical rms of the input dataset as a float
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

    def list_chunks(self):
        '''
        Checks how many chunk directories exist and returns a list of them
        '''
        for n in range(100):
            if os.path.exists(self.selfcaldir + '/' + str(n).zfill(2)):
                pass
            else:
                break  # Stop the counting loop at the directory you cannot find anymore
        chunks = range(n)
        chunkstr = [str(i).zfill(2) for i in chunks]
        return chunkstr

    #######################################################################
    ##### Manage the creation and moving of new directories and files #####
    #######################################################################

    def show(self):
        '''
        Prints the current settings of the pipeline. Only shows keywords, which are in the default config file default.cfg
        '''
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.apercaldir + '/default.cfg'))
        for s in config.sections():
            print(s)
            o = config.options(s)
            for o in config.items(s):
                print('\t' + str(o[0]) + ' = ' + str(self.__dict__.__getitem__(o[0])))

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