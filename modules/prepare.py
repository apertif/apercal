__author__ = "Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "adebahr@astron.nl"

import ConfigParser
import glob
import logging
import sys

import casac
import os

import subs.setinit
from libs import lib


class prepare:
    '''
    Prepare class. Automatically copies the datasets into the directories and selects valid data (in case of multi-element observations)
    '''
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=20)
        self.logger = logging.getLogger('PREPARE')
        config = ConfigParser.ConfigParser()  # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('prepare.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        subs.setinit.setinitdirs(self)

    def copyobs(self):
        '''
        Copies the datasets from the observation directory in /data[1-4]/apertif/[..] to the specified working directories.
        Has an option to account for the limited bandwidth of the old observations in multi-element mode (prepare_obsmode: multi_element_90)
        '''
        subs.setinit.setinitdirs(self)
        if self.prepare_obsdir_fluxcal != '':
            fluxset = glob.glob(self.prepare_obsdir_fluxcal + '*.MS')[0]
            if fluxset != '':
                self.logger.info('### Flux calibrator dataset found. Copying beam 00 to working directory. ###')
                self.director('mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                if self.prepare_obsmode == 'single_element' or self.prepare_obsmode == 'multi_element':
                    self.director('cp', self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal, file=fluxset)
                elif self.prepare_obsmode == 'multi_element_90':
                    ms = casac.casac.ms()
                    ms.open(fluxset)
                    ms.split(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal, spw='0:0~7359', whichcol='all')
                    ms.close()
                else:
                    self.logger.error('### Obsmode not known! Exiting ###')
                    sys.exit(1)
            else:
                self.logger.warning('### No flux calibrator dataset found. The next steps might not work! ###')
        else:
            self.logger.warning('### No flux calibrator dataset specified. The next steps might not work! ###')
        if self.prepare_obsdir_polcal != '':
            polset = glob.glob(self.prepare_obsdir_polcal + '*.MS')[0]
            if polset != '':
                self.logger.info('### Polarisation calibrator dataset found. Copying beam 00 to working directory. ###')
                self.director('mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                if self.prepare_obsmode == 'single_element' or self.prepare_obsmode == 'multi_element':
                    self.director('cp', self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal, file=polset)
                elif self.prepare_obsmode == 'multi_element_90':
                    ms = casac.casac.ms()
                    ms.open(polset)
                    ms.split(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal, spw='0:0~7359')
                    ms.close()
                else:
                    self.logger.error('### Obsmode not known! Exiting ###')
                    sys.exit(1)
            else:
                self.logger.warning('### No polarisation calibrator dataset found. The next steps might not work! ###')
        else:
            self.logger.warning('### No polarisation calibrator dataset specified. The next steps might not work! ###')
        if self.prepare_obsdir_target != '':
            targetsets = glob.glob(self.prepare_obsdir_target + '*.MS')
            if targetsets != '':
                self.logger.info('### ' + str(len(targetsets)) + ' different beams for target field found. ###')
                if self.prepare_obsmode == 'single_element':
                    self.logger.info('### Copying central element beam to working directory. ###')
                    self.director('mk', self.basedir + '00' + '/' + self.rawsubdir, verbose=False)
                    self.director('cp', self.basedir + '00' + '/' + self.rawsubdir + '/' + self.target, file=targetsets[0])
                elif self.prepare_obsmode == 'multi_element':
                    self.logger.info('### Copying all target datasets to their working directories. ###')
                    for b, ds in enumerate(targetsets):
                        self.director('mk', self.basedir + str(b).zfill(2) + '/' + self.rawsubdir, verbose=False)
                        self.director('cp', self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target, file=ds, verbose=False)
                elif self.prepare_obsmode == 'multi_element_90':
                    self.logger.info('### Copying all target datasets to their working directories. ###')
                    for b, ds in enumerate(targetsets):
                        self.director('mk', self.basedir + str(b).zfill(2) + '/' + self.rawsubdir, verbose=False)
                        ms = casac.casac.ms()
                        ms.open(ds)
                        ms.split(self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target, spw='0:0~7359')
                        ms.close()
                else:
                    self.logger.error('### Obsmode not known! Exiting ###')
                    sys.exit(1)
                self.logger.info('### Target dataset(s) copied to working directories! ###')

    def go(self):
        '''
        Executes the complete prepare step with the parameters indicated in the config-file in the following order:
        copyobs
        '''
        self.logger.info('########## Preparing data for calibration ##########')
        self.copyobs()
        self.logger.info('########## Data prepared for calibration ##########')

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
                if s == 'PREPARE':
                    print(s)
                    o = config.options(s)
                    for o in config.items(s):
                        try:
                            print('\t' + str(o[0]) + ' = ' + str(self.__dict__.__getitem__(o[0])))
                        except KeyError:
                            pass
                else:
                    pass

    def director(self, option, dest, file=None, verbose=True):
        '''
        director: Function to move, remove, and copy files and directories
        option: 'mk', 'ch', 'mv', 'rm', and 'cp' are supported
        dest: Destination of a file or directory to move to
        file: Which file to move or copy, otherwise None
        '''
        subs.setinit.setinitdirs(self)
        if option == 'mk':
            if os.path.exists(dest):
                pass
            else:
                os.makedirs(dest)
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
