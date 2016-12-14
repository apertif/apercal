import os, sys
import logging
import lib
import ConfigParser
import casat

class convert:
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('convert')
        config = ConfigParser.ConfigParser()  # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values for selfcal! ###')
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
        if self.ms2uvfits_tool == 'casa':
            self.logger.info('### Using CASA task exportuvfits to convert from MS to UVFITS format! ###')
            from casat import exportuvfits
            exportuvfits = exportuvfits.exportuvfits
            if self.convert_fluxcal == True:
                exportuvfits(vis=self.rawdir + '/' + self.fluxcal, fitsfile=self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS', datacolumn='data')
                self.logger.info('### Converted MS file ' + self.fluxcal + ' to UVFITS using CASA task exportuvfits! ###')
            if self.convert_polcal == True:
                exportuvfits(vis=self.rawdir + '/' + self.polcal, fitsfile=self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS', datacolumn='data')
                self.logger.info('### Converted MS file ' + self.polcal + ' to UVFITS using CASA task exportuvfits! ###')
            if self.convert_target == True:
                exportuvfits(vis=self.rawdir + '/' + self.target, fitsfile=self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS', datacolumn='data')
                self.logger.info('### Converted MS file ' + self.target + ' to UVFITS using CASA task exportuvfits! ###')
        elif self.ms2uvfits_tool == 'ms2uvfits':
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

    def uvfits2miriad(self):
        '''
        Executes the selected miriad task (fits or wsrtfits) to convert the data from UVFITS to MIRIAD format. Does it for the flux calibrator, polarisation calibrator, and target field independently.
        '''
        if self.uvfits2mir_tool == 'fits':
            self.logger.info('### Using MIRIAD fits task to convert data from UVFITS to MIRIAD format ###')
            fits = lib.miriad('fits')
            fits.op = 'uvin'
            if self.convert_fluxcal == True:
                fits._in = self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS'
                fits.out = self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'mir'
                fits.go()
                self.logger.info('### Converted UVFITS file ' + self.fluxcal + ' to MIRIAD format using MIRIAD task fits! ###')
            if self.convert_polcal == True:
                fits._in = self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS'
                fits.out = self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'mir'
                fits.go()
                self.logger.info('### Converted UVFITS file ' + self.polcal + ' to MIRIAD format using MIRIAD task fits! ###')
            if self.convert_target == True:
                fits._in = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS'
                fits.out = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'mir'
                fits.go()
                self.logger.info('### Converted UVFITS file ' + self.target + ' to MIRIAD format using MIRIAD task fits! ###')
            self.logger.info('### Conversion from UVFITS to MIRIAD fromat done! ###')
        elif self.uvfits2mir_tool == 'wsrtfits':
            self.logger.info('### Using MIRIAD wsrtfits task to convert data from UVFITS to MIRIAD format ###')
            wsrtfits = lib.miriad('wsrtfits')
            wsrtfits.op = 'uvin'
            if self.convert_fluxcal == True:
                wsrtfits._in = self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS'
                wsrtfits.out = self.crosscaldir + '/' + str(self.fluxcal).rstrip('MS') + 'mir'
                wsrtfits.go()
                self.logger.info('### Converted UVFITS file ' + self.fluxcal + ' to MIRIAD format using MIRIAD task wsrtfits! ###')
            if self.convert_polcal == True:
                wsrtfits._in = self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS'
                wsrtfits.out = self.crosscaldir + '/' + str(self.polcal).rstrip('MS') + 'mir'
                wsrtfits.go()
                self.logger.info('### Converted UVFITS file ' + self.polcal + ' to MIRIAD format using MIRIAD task wsrtfits! ###')
            if self.convert_target == True:
                wsrtfits._in = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS'
                wsrtfits.out = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'mir'
                wsrtfits.go()
                self.logger.info('### Converted UVFITS file ' + self.target + ' to MIRIAD format using MIRIAD task wsrtfits! ###')
            self.logger.info('### Conversion from UVFITS to MIRIAD fromat done! ###')
        else:
            self.logger.error('### Conversion tool not supported! Exiting pipeline! ###')
            sys.exit(1)

    def go(self):
        '''
        Executes the whole conversion from MS format to MIRIAD format of the flux calibrator, polarisation calibrator, and target dataset
        '''
        self.logger.info('########## FILE CONVERSION started ##########')
        self.director('ch', self.crosscaldir)
        self.ms2uvfits()
        self.uvfits2miriad()
        self.logger.info('########## FILE CONVERSION done ##########')

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
        elif option == 'mv':
            if os.path.exists(dest):
                lib.basher("mv " + str(file) + " " + str(dest))
            else:
                os.mkdir(dest)
                lib.basher("mv " + str(file) + " " + str(dest))
        elif option == 'rn':
            lib.basher("mv " + str(file) + " " + str(dest))
        elif option == 'cp':
            lib.basher("cp -r " + str(file) + " " + str(dest))
        elif option == 'rm':
            lib.basher("rm -r " + str(dest))
        else:
            print('### Option not supported! Only mk, ch, mv, rm, rn, and cp are supported! ###')