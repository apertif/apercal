import os, sys
import logging
import lib
import ConfigParser
import casac

class convert:
    '''
    Class to convert data from MS-format into UVFITS, and from UVFITS into MIRIAD format. Resulting datasets will have the endings .MS, .UVFITS, and .mir.
    '''
    def __init__(self, file=None, **kwargs):
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

        # Create the directory names
        self.rawdir = self.basedir + self.rawsubdir
        self.crosscaldir = self.basedir + self.crosscalsubdir
        self.selfcaldir = self.basedir + self.selfcalsubdir

    def ms2uvfits(self):
        '''
        Executes the CASA exportuvfits or the command line utility ms2uvfits to convert the data from MS to UVFITS format. Does it for the flux calibrator, polarisation calibrator, and target field independently.
        '''
        if self.convert_ms2uvfits:
            self.logger.info('### Starting conversion from MS to UVFITS format ###')
            self.director('ch', self.crosscaldir)
            if self.convert_ms2uvfits_tool == 'casa':
                self.logger.info('### Using CASA toolkit to convert from MS to UVFITS format! ###')
                ms = casac.casac.ms()
                if self.convert_fluxcal == True:
                    ms.open(self.rawdir + '/' + self.fluxcal)
                    if self.convert_ms2uvfits_tool_casa_autocorr:
                        ms.tofits(self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, writesyscal=True, padwithflags=True, multisource=True, writestation=True)
                    else:
                        ms.tofits(self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, writesyscal=True, padwithflags=True, multisource=True, writestation=True, uvrange='>0m')
                    ms.done()
                    self.logger.info('### Converted MS file ' + self.fluxcal + ' to UVFITS using CASA toolkit! ###')
                if self.convert_polcal == True:
                    ms.open(self.rawdir + '/' + self.polcal)
                    if self.convert_ms2uvfits_tool_casa_autocorr:
                        ms.tofits(self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, writesyscal=True, padwithflags=True, multisource=True, writestation=True)
                    else:
                        ms.tofits(self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, writesyscal=True, padwithflags=True, multisource=True, writestation=True, uvrange='>0m')
                    ms.done()
                    self.logger.info('### Converted MS file ' + self.polcal + ' to UVFITS using CASA toolkit! ###')
                if self.convert_target == True:
                    ms.open(self.rawdir + '/' + self.target)
                    if self.convert_ms2uvfits_tool_casa_autocorr:
                        ms.tofits(self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, writesyscal=True, padwithflags=True, multisource=True, writestation=True)
                    else:
                        ms.tofits(self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS', column='DATA', combinespw=True, writesyscal=True, padwithflags=True, multisource=True, writestation=True, uvrange='>0m')
                    ms.done()
                    self.logger.info('### Converted MS file ' + self.target + ' to UVFITS using CASA toolkit! ###')
            elif self.convert_ms2uvfits_tool == 'ms2uvfits':
                self.logger.info('### Using ms2uvfits to convert from MS to UVFITS format! ###')
                if self.convert_fluxcal == True:
                    os.system('ms2uvfits in=' + self.rawdir + '/' + self.fluxcal + ' out=' + self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted MS file ' + self.fluxcal + ' to UVFITS using ms2uvfits! ###')
                if self.convert_polcal == True:
                    os.system('ms2uvfits in=' + self.rawdir + '/' + self.polcal + ' out=' + self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted MS file ' + self.polcal + ' to UVFITS using ms2uvfits! ###')
                if self.convert_fluxcal == True:
                    os.system('ms2uvfits in=' + self.rawdir + '/' + self.target + ' out=' + self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted MS file ' + self.target + ' to UVFITS using ms2uvfits! ###')
            else:
                self.logger.error('### Conversion tool not supported! Exiting pipeline! ###')
                sys.exit(1)
            self.logger.info('### Conversion from MS to UVFITS format done! ###')

    def uvfits2miriad(self):
        '''
        Executes the selected miriad task (fits or wsrtfits) to convert the data from UVFITS to MIRIAD format. Does it for the flux calibrator, polarisation calibrator, and target field independently.
        '''
        if self.convert_uvfits2mir:
            self.logger.info('### Starting conversion from UVFITS to MIRIAD format ###')
            self.director('ch', self.crosscaldir)
            if self.convert_uvfits2mir_tool == 'fits':
                self.logger.info('### Using MIRIAD fits task to convert data from UVFITS to MIRIAD format ###')
                fits = lib.miriad('fits')
                fits.op = 'uvin'
                if self.convert_fluxcal == True:
                    fits.in_ = self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS'
                    fits.out = self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'mir'
                    fits.go()
                    self.director('rm', self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted UVFITS file ' + self.fluxcal + ' to MIRIAD format using MIRIAD task fits! ###')
                if self.convert_polcal == True:
                    fits.in_ = self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS'
                    fits.out = self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'mir'
                    fits.go()
                    self.director('rm', self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted UVFITS file ' + self.polcal + ' to MIRIAD format using MIRIAD task fits! ###')
                if self.convert_target == True:
                    fits.in_ = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS'
                    fits.out = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'mir'
                    fits.go()
                    self.director('rm', self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted UVFITS file ' + self.target + ' to MIRIAD format using MIRIAD task fits! ###')
            elif self.convert_uvfits2mir_tool == 'wsrtfits':
                self.logger.info('### Using MIRIAD wsrtfits task to convert data from UVFITS to MIRIAD format ###')
                wsrtfits = lib.miriad('wsrtfits')
                wsrtfits.op = 'uvin'
                if self.convert_fluxcal == True:
                    wsrtfits.in_ = self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS'
                    wsrtfits.out = self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'mir'
                    wsrtfits.go()
                    self.director('rm', self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted UVFITS file ' + self.fluxcal + ' to MIRIAD format using MIRIAD task wsrtfits! ###')
                if self.convert_polcal == True:
                    wsrtfits.in_ = self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS'
                    wsrtfits.out = self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'mir'
                    wsrtfits.go()
                    self.director('rm', self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted UVFITS file ' + self.polcal + ' to MIRIAD format using MIRIAD task wsrtfits! ###')
                if self.convert_target == True:
                    wsrtfits.in_ = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS'
                    wsrtfits.out = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'mir'
                    wsrtfits.go()
                    self.director('rm', self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS')
                    self.logger.info('### Converted UVFITS file ' + self.target + ' to MIRIAD format using MIRIAD task wsrtfits! ###')
            else:
                self.logger.error('### Conversion tool not supported! Exiting pipeline! ###')
                sys.exit(1)
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
        self.logger.warning('### Deleting all converted data. ###')
        self.director('ch', self.crosscaldir)
        self.director('rm', self.crosscaldir + '/*')

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