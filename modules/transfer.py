__author__ = "Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "adebahr@astron.nl"

import ConfigParser
import glob
import logging

import aipy
import astropy.io.fits as pyfits
import numpy as np
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

class transfer:
    '''
    Transfer class to combine the calibrated data chunks with full spectral resolution into one file and export to UVFITS.
    Gain tables and flags are already applied. Data is then ready to get ingested into ALTA.
    '''
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger('TRANSFER')
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

    ####################################################
    ##### Function to execute the transfer process #####
    ####################################################

    def go(self):
        '''
        Executes the continuum imaging process in the following order
        convert_lineuv2uvfits
        '''
        self.logger.info("########## Starting TRANSFER process of all beams ##########")
        self.convert_lineuv2uvfits()
        self.logger.info("########## TRANSFER process for all beams done ##########")

    def convert_lineuv2uvfits(self):
        '''
        Looks for all calibrated datasets created by the line module, combines the chunks of individual beams and converts them to UVFITS format
        '''
        subs.setinit.setinitdirs(self)
        subs.managefiles.director(self, 'ch', self.transferdir, verbose=False)
        beamlist = sorted(glob.glob(self.basedir + '[0-9][0-9]'))
        beamnames = [beam.split('/')[-1] for beam in beamlist]
        subs.param.add_param(self, 'transfer_input_beams', beamnames)
#        transferstatusarray = np.full((len(beamnames, 2), np.False))
        for b, beam in enumerate(beamlist):
            uvgluestatusarray = np.full((len(beamnames)), False)
            uvfitsstatusarray = np.full((len(beamnames)), False)
            if os.path.isfile(self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.UVFITS'):
                self.logger.warning('# UVFITS file for beam ' + beam.split('/')[-1] + ' already exists! #')
            else:
                chunklist = sorted(glob.glob(beam + '/' + self.linesubdir + '/' + '[0-9][0-9]/[0-9][0-9]' + '.mir'))
                chunknames = [chunk.split('/')[-2] for chunk in chunklist]
                subs.param.add_param(self, 'transfer_input_beam_' + str(beamnames[b]) + '_chunks', chunknames)
                uvcatstatusarray = np.full((len(chunknames)), False)
                self.logger.debug('# Starting combination of frequency chunks for beam ' + beam.split('/')[-1] + ' #')
                for c, chunk in enumerate(chunklist):
                    uvcat = lib.miriad('uvcat')
                    uvcat.vis = chunk
                    uvcat.out = self.transferdir + '/' + 'B' + beam.split('/')[-1] + '_' + str(c+1)
                    uvcat.go()
                    if os.path.isdir(self.transferdir + '/' + 'B' + beam.split('/')[-1] + '_' + str(c+1)): # Check if file has been copied successfully
                        self.logger.debug('# Chunk ' + str(chunk).zfill(2) + ' for beam ' + str(beam.split('/')[-1]) + ' copied successfully! #')
                        uvcatstatusarray[c] = True
                    else:
                        self.logger.warning('# Chunk ' + str(chunk).zfill(2) + ' for beam ' + str(beam.split('/')[-1]) + ' NOT copied successfully! #')
                        uvcatstatusarray[c] = False
                subs.param.add_param(self, 'transfer_input_beam_' + str(beamnames[b]) + '_copy_status', uvcatstatusarray)
                uvglue = lib.miriad('uvglue')
                uvglue.vis = 'B' + beam.split('/')[-1]
                uvglue.nfiles = len(chunklist)
                uvglue.out = self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.mir'
                uvglue.go()
                if os.path.isdir(self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.mir'):
                    self.logger.debug('# Combination of frequency chunks for beam ' + beam.split('/')[-1] + ' successful! #')
                    subs.managefiles.director(self, 'rm', 'B' + beam.split('/')[-1] + '*')
                    uvgluestatusarray[b] = True
                else:
                    self.logger.warning('# Combination of frequency chunks for beam ' + beam.split('/')[-1] + ' not successful! #')
                    uvgluestatusarray[b] = False
                fits = lib.miriad('fits')
                fits.op = 'uvout'
                fits.in_ = self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.mir'
                fits.out = self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.UVFITS'
                fits.go()
                if os.path.isfile(self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.UVFITS'):
                    self.logger.debug('# Conversion of MIRIAD file to UVFITS for beam '  + beam.split('/')[-1] + ' successful! #')
                    subs.managefiles.director(self, 'rm', self.target.rstrip('.mir') + '_B' + beam.split('/')[-1] + '.mir')
                    uvfitsstatusarray[b] = True
                else:
                    self.logger.warning('# Conversion of MIRIAD file to UVFITS for beam '  + beam.split('/')[-1] + ' NOT successful! #')
                    uvfitsstatusarray[b] = False
            subs.param.add_param(self, 'transfer_input_beams_uvglue', uvgluestatusarray)
            subs.param.add_param(self, 'transfer_input_beams_uvfits', uvfitsstatusarray)

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
                if s == 'TRANSFER':
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
        self.logger.warning('### Deleting all data products ready for transfer. ###')
        subs.managefiles.director(self,'ch', self.basedir)
        subs.managefiles.director(self,'rm', self.transferdir)