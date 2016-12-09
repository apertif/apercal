import os, sys
import logging
import lib
import ConfigParser

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

    def create_casascript(self):
        casatext = ''
        if self.convert_fluxcal == True:
            casatext = casatext + "exportuvfits(vis='" + self.rawdir + '/' + self.fcal + "', fitsfile='" + self.crosscaldir + '/' + str(self.fcal).rstrip('MS') + "UVFITS')\n"
        if self.convert_polcal == True:
            casatext = casatext + "exportuvfits(vis='" + self.rawdir + '/' + self.pcal + "', fitsfile='" + self.crosscaldir + '/' + str(self.pcal).rstrip('MS') + "UVFITS')\n"
        if self.convert_target == True:
            casatext = casatext + "exportuvfits(vis='" + self.rawdir + '/' + self.target + "', fitsfile='" + self.crosscaldir + '/' + str(self.target).rstrip('MS') + "UVFITS')\n"
        casa2uvfile = self.rawdir + '/casa2uvfits.py'
        casafile = open(casa2uvfile, 'w')
        casafile.write(casatext)
        casafile.close()
        self.logger.info('### Wrote CASA conversion script from MS to UVFITS to ' + casa2uvfile + '! ###')

    def uvfits2miriad(self):
        fits = lib.miriad('fits')
        fits.op = 'uvin'
        if self.convert_fluxcal == True:
            fits._in = self.crosscaldir + '/' + str(self.fcal).rstrip('MS') + 'UVFITS'
            fits.out = self.crosscaldir + '/' + str(self.fcal).rstrip('MS') + 'mir'
            fits.go()
            self.logger.info('### Converted UVFITS file ' + self.fcal + ' to MIRIAD format! ###')
        if self.convert_polcal == True:
            fits._in = self.crosscaldir + '/' + str(self.pcal).rstrip('MS') + 'UVFITS'
            fits.out = self.crosscaldir + '/' + str(self.pcal).rstrip('MS') + 'mir'
            fits.go()
            self.logger.info('### Converted UVFITS file ' + self.pcal + ' to MIRIAD format! ###')
        if self.convert_target == True:
            fits._in = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'UVFITS'
            fits.out = self.crosscaldir + '/' + str(self.target).rstrip('MS') + 'mir'
            fits.go()
            self.logger.info('### Converted UVFITS file ' + self.target + ' to MIRIAD format! ###')

    def go(self):
        self.director('ch', self.crosscaldir)
        if self.tool == 'casapy':
            self.create_casascript()
            self.logger.info('### Executing CASA conversion script! ###')
            os.system("casapy --nologger --log2term -c casa2uvfits.py")
            self.uvfits2miriad()
        else:
            self.logger.error('### Conversion tool not supported! Exiting! ###')
            sys.exit(1)

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
            print('### Option not supported! Only mk, ch, mv, rm, and cp are supported! ###')