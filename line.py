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

class line:
    '''
    Line class to do continuum subtraction and prepare data for line imaging.
    '''
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('LINE')
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

    #################################################################
    ##### Function to execute the continuum subtraction process #####
    #################################################################

    def go(self):
        '''
        Executes the whole continuum subtraction process in the following order:
        splitdata
        transfergains
        subtract
        '''
        self.logger.info("########## Starting CONTINUUM SUBTRACTION ##########")
        self.splitdata()
        self.transfergains()
        self.subtract()
        self.logger.info("########## CONTINUUM SUBTRACTION done ##########")

    def splitdata(self):
        '''
        Applies calibrator corrections to data, splits the data into chunks in frequency and bins it to the given frequency resolution for continuum subtraction.
        '''
        if self.line_splitdata:
            self.director('ch', self.linedir)
            self.logger.info('### Splitting of target data into individual freqeuncy chunks for continuum subtraction started ###')
            uv = aipy.miriad.UV(self.selfcaldir + '/' + self.target)
            try:
                nsubband = len(uv['nschan'])  # Number of subbands in data
            except TypeError:
                nsubband = 1  # Only one subband in data since exception was triggered
            self.logger.info('# Found ' + str(nsubband) + ' subband(s) in target data #')
            counter = 0  # Counter for naming the chunks and directories
            for subband in range(nsubband):
                self.logger.info('# Started splitting of subband ' + str(subband) + ' #')
                if nsubband == 1:
                    numchan = uv['nschan']
                    finc = np.fabs(uv['sdf'])
                else:
                    numchan = uv['nschan'][subband]  # Number of channels per subband
                    finc = np.fabs(uv['sdf'][subband])  # Frequency increment for each channel
                subband_bw = numchan * finc  # Bandwidth of one subband
                subband_chunks = round(subband_bw / self.line_splitdata_chunkbandwidth)
                subband_chunks = int(np.power(2, np.ceil(np.log(subband_chunks) / np.log(2))))  # Round to the closest power of 2 for frequency chunks with the same bandwidth over the frequency range of a subband
                if subband_chunks == 0:
                    subband_chunks = 1
                chunkbandwidth = (numchan / subband_chunks) * finc
                self.logger.info('# Adjusting chunk size to ' + str(chunkbandwidth) + ' GHz for regular gridding of the data chunks over frequency #')
                for chunk in range(subband_chunks):
                    self.logger.info('# Starting splitting of data chunk ' + str(chunk) + ' for subband ' + str(subband) + ' #')
                    binchan = round(self.line_splitdata_channelbandwidth / finc)  # Number of channels per frequency bin
                    chan_per_chunk = numchan / subband_chunks
                    if chan_per_chunk % binchan == 0:  # Check if the freqeuncy bin exactly fits
                        self.logger.info('# Using frequency binning of ' + str(self.line_splitdata_channelbandwidth) + ' for all subbands #')
                    else:
                        while chan_per_chunk % binchan != 0:  # Increase the frequency bin to keep a regular grid for the chunks
                            binchan = binchan + 1
                        else:
                            if chan_per_chunk >= binchan:  # Check if the calculated bin is not larger than the subband channel number
                                pass
                            else:
                                binchan = chan_per_chunk  # Set the frequency bin to the number of channels in the chunk of the subband
                        self.logger.info('# Increasing frequency bin of data chunk ' + str(chunk) + ' to keep bandwidth of chunks equal over the whole bandwidth #')
                        self.logger.info('# New frequency bin is ' + str(binchan * finc) + ' GHz #')
                    nchan = int(chan_per_chunk / binchan)  # Total number of output channels per chunk
                    start = 1 + chunk * chan_per_chunk
                    width = int(binchan)
                    step = int(width)
                    self.director('mk', self.linedir + '/' + str(counter).zfill(2))
                    uvaver = lib.miriad('uvaver')
                    uvaver.vis = self.selfcaldir + '/' + self.target
                    uvaver.out = self.linedir + '/' + str(counter).zfill(2) + '/' + str(counter).zfill(2) + '.mir'
                    uvaver.select = "'" + 'window(' + str(subband + 1) + ')' + "'"
                    uvaver.line = "'" + 'channel,' + str(nchan) + ',' + str(start) + ',' + str(width) + ',' + str(step) + "'"
                    uvaver.go()
                    counter = counter + 1
                    self.logger.info('# Splitting of data chunk ' + str(chunk) + ' for subband ' + str(subband) + ' done #')
                self.logger.info('# Splitting of data for subband ' + str(subband) + ' done #')
            self.logger.info('### Splitting of target data into individual frequency chunks done ###')

    def transfergains(self):
        '''
        Checks if the continuum datasets have self calibration gains and copies their gains over.
        '''
        if self.line_transfergains:
            self.director('ch', self.linedir)
            self.logger.info('### Copying gains from continuum to line data ###')
            for chunk in self.list_chunks():
                if os.path.isfile(self.selfcaldir + '/' + chunk + '/' + chunk + '.mir' + '/gains'):
                    gpcopy = lib.miriad('gpcopy')
                    gpcopy.vis = self.selfcaldir + '/' + chunk + '/' + chunk + '.mir'
                    gpcopy.out = chunk + '/' + chunk + '.mir'
                    gpcopy.go()
                    self.logger.info('# Copying gains from continuum to line data for chunk ' + chunk + ' #')
                else:
                    self.logger.warning('# Dataset ' + chunk + '.mir does not seem to have self calibration gains. Cannot copy gains to line data! #')
            self.logger.info('### Gains from continuum to line data copied ###')

    def subtract(self):
        '''
        Module for subtracting the continuum from the line data. Supports uvlin and uvmodel (from the last self calibration cycle of each chunk).
        '''
        if self.line_subtract:
            self.director('ch', self.linedir)
            if self.line_subtract_mode == 'uvlin':
                self.logger.info('### Starting continuum subtraction of individual chunks using uvlin ###')
                for chunk in self.list_chunks():
                    uvlin = lib.miriad('uvlin')
                    uvlin.vis = chunk + '/' + chunk + '.mir'
                    uvlin.out = chunk + '/' + chunk + '_line.mir'
                    uvlin.go()
                    self.logger.info('# Continuum subtraction using uvlin method for chunk ' + chunk + ' done #')
            elif self.line_subtract_mode == 'uvmodel':
                self.logger.info('### Starting continuum subtraction of individual chunks using uvmodel ###')
                for chunk in self.list_chunks():
                    uvcat = lib.miriad('uvcat')
                    uvcat.vis = chunk + '/' + chunk + '.mir'
                    uvcat.out = chunk + '/' + chunk + '_uvcat.mir'
                    uvcat.go()
                    self.logger.info('# Applied gains to chunk ' + chunk + ' for subtraction of continuum model #')
                    uvmodel = lib.miriad('uvmodel')
                    uvmodel.vis = chunk + '/' + chunk + '_uvcat.mir'
                    for m in range(100):
                        if os.path.exists(self.selfcaldir + '/' + chunk + '/' + str(m).zfill(2)):
                            pass
                        else:
                            break # Stop the counting loop at the directory you cannot find anymore
                    for n in range(100):
                        if os.path.exists(self.selfcaldir + '/' + chunk + '/' + str(m-1).zfill(2) + '/model_' + str(n).zfill(2)):
                            pass
                        else:
                            break # Stop the counting loop at the directory you cannot find anymore
                    self.logger.info('# Found most complete model for chunk ' + chunk + ' in ' + self.selfcaldir + '/' + chunk + '/' + str(m-1).zfill(2) + '/model_' + str(n-1).zfill(2) + ' #')
                    uvmodel.model = self.selfcaldir + '/' + chunk + '/' + str(m-1).zfill(2) + '/model_' + str(n-1).zfill(2)
                    uvmodel.options = 'subtract,mfs'
                    uvmodel.out = chunk + '/' + chunk + '_line.mir'
                    uvmodel.go()
                    self.director('rm', chunk + '/' + chunk + '_uvcat.mir')
                    self.logger.info('# Continuum subtraction using uvmodel method for chunk ' + chunk + ' done #')
            else:
                self.logger.error('### Subtract mode not know. Exiting! ###')
                sys.exit(1)

    ######################################################################
    ##### Subfunctions for managing the location and naming of files #####
    ######################################################################

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
                if s == 'LINE':
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
        self.logger.warning('### Deleting all continuum subtracted line data. ###')
        self.director('ch', self.linedir)
        self.director('rm', self.linedir + '/*')

    def director(self, option, dest, file=None, verbose=True):
        '''
        director: Function to move, remove, and copy files and directories
        option: 'mk', 'ch', 'mv', 'rm', 'rn', and 'cp' are supported
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