import ConfigParser
import glob
import logging

import casac
import os

import subs.setinit
import subs.managefiles
from libs import lib


class convert:
    '''
    Class to convert data from MS-format into UVFITS, and from UVFITS into MIRIAD format. Resulting datasets will have the endings .MS, .UVFITS, and .mir.
    '''
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=20)
        self.logger = logging.getLogger('CONVERT')
        config = ConfigParser.ConfigParser()  # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        subs.setinit.setinitdirs(self)

    def ms2uvfits(self):
        '''
        Converts the data from MS to UVFITS format using the CASA toolkit. Does it for the flux calibrator, polarisation calibrator, and target field independently.
        '''
        subs.setinit.setinitdirs(self)
        if self.convert_ms2uvfits:
            self.logger.info('### Starting conversion from MS to UVFITS format ###')
            subs.managefiles.director(self, 'ch', self.basedir + '00' + '/' + self.crosscalsubdir, verbose=False)
            ms = casac.casac.ms()
            if self.convert_fluxcal == True:
                ms.open(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
                if self.convert_ms2uvfits_tool_casa_autocorr:
                    ms.tofits(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, padwithflags=True, multisource=True, writestation=True)
                else:
                    ms.tofits(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, padwithflags=True, multisource=True, writestation=True, uvrange='>0m')
                ms.done()
                self.logger.info('### Converted MS file ' + self.fluxcal + ' to UVFITS format! ###')
            if self.convert_polcal == True:
                ms.open(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
                if self.convert_ms2uvfits_tool_casa_autocorr:
                    ms.tofits(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, padwithflags=True, multisource=True, writestation=True)
                else:
                    ms.tofits(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, padwithflags=True, multisource=True, writestation=True, uvrange='>0m')
                ms.done()
                self.logger.info('### Converted MS file ' + self.polcal + ' to UVFITS format! ###')
            if self.convert_target == True:
                mslist = glob.glob(self.basedir + '*/' + self.rawsubdir + '/' + self.target)
                for dataset in mslist:
                    ms.open(dataset)
                    subs.managefiles.director(self, 'mk', dataset.rstrip(self.target).rstrip(self.rawsubdir + '/') + '/' + self.crosscalsubdir)
                    if self.convert_ms2uvfits_tool_casa_autocorr:
                        ms.tofits(dataset.rstrip(self.target).rstrip(self.rawsubdir + '/') + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, padwithflags=True, multisource=True, writestation=True)
                    else:
                        ms.tofits(dataset.rstrip(self.target).rstrip(self.rawsubdir + '/') + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, padwithflags=True, multisource=True, writestation=True, uvrange='>0m')
                    ms.done()
                    self.logger.info('### Converted MS file ' + dataset + ' to UVFITS format! ###')
            self.logger.info('### Conversion from MS to UVFITS format done! ###')

    def uvfits2miriad(self):
        '''
        Converts the data from UVFITS to MIRIAD format. Does it for the flux calibrator, polarisation calibrator, and target field independently.
        '''
        subs.setinit.setinitdirs(self)
        if self.convert_uvfits2mir:
            self.logger.info('### Starting conversion from UVFITS to MIRIAD format ###')
            subs.managefiles.director(self, 'ch', self.basedir + '00' + '/' + self.crosscalsubdir, verbose=False)
            fits = lib.miriad('fits')
            fits.op = 'uvin'
            if self.convert_fluxcal == True:
                fits.in_ = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS'
                fits.out = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.fluxcal).rstrip('MS') + 'mir'
                fits.go()
                subs.managefiles.director(self, 'rm', self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS', verbose=False)
                self.logger.info('### Converted UVFITS file ' + self.fluxcal + ' to MIRIAD format! ###')
            if self.convert_polcal == True:
                fits.in_ = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS'
                fits.out = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.polcal).rstrip('MS') + 'mir'
                fits.go()
                subs.managefiles.director(self, 'rm', self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS', verbose=False)
                self.logger.info('### Converted UVFITS file ' + self.polcal + ' to MIRIAD format! ###')
            if self.convert_target == True:
                mslist = glob.glob(self.basedir + '*/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS')
                for dataset in mslist:
                    fits.in_ = dataset
                    fits.out = dataset.rstrip('UVFITS') + 'mir'
                    fits.go()
                    subs.managefiles.director(self, 'rm', dataset)
                    self.logger.info('### Converted UVFITS file ' + dataset + ' to MIRIAD format! ###')
            self.logger.info('### Conversion from UVFITS to MIRIAD format done! ###')

    def go(self):
        '''
        Executes the whole conversion from MS format to MIRIAD format of the flux calibrator, polarisation calibrator, and target dataset in the following order:
        ms2uvfits
        uvfits2miriad
        '''
        self.logger.info('########## FILE CONVERSION started ##########')
        self.ms2uvfits()
        self.uvfits2miriad()
        self.logger.info('########## FILE CONVERSION done ##########')

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
                if s == 'CONVERT':
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
        self.logger.warning('### Deleting all converted data. ###')
        subs.managefiles.director(self, 'ch', self.crosscaldir)
        subs.managefiles.director(self, 'rm', self.crosscaldir + '/*')