__author__ = "Bradley Frank, Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "frank@astron.nl, adebahr@astron.nl"

import re
import lib
import logging
import os
import ConfigParser
from datetime import datetime
import calendar
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.coordinates import FK5

####################################################################################################

class ccal:
    '''
    ccal: Crosscal class to handle applying the calibrator gains and prepare the dataset for selfcal
    '''
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('CROSSCAL')
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values for crosscal! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        self.default = config # Save the loaded config file as defaults for later usage

        # Create the directory names
        self.rawdir = self.basedir + self.rawsubdir
        self.crosscaldir = self.basedir + self.crosscalsubdir
        self.selfcaldir = self.basedir + self.selfcalsubdir
        self.finaldir = self.basedir + self.finalsubdir

        # Name the datasets
        self.fluxcal = self.fluxcal.rstrip('MS') + 'mir'
        self.polcal = self.polcal.rstrip('MS') + 'mir'
        self.target = self.target.rstrip('MS') + 'mir'

    ####################################################################################
    ##### Functions to execute the different modes of the self-calibration process #####
    ####################################################################################

    def cal_fluxcal(self):
        self.logger.info('### Starting to calibrate flux calibrator ###')
        mfcal = lib.miriad('mfcal')
        mfcal.vis = self.fluxcal
        mfcal.refant = 1
        mfcal.interval = 1000
        self.logger.info('# Using reference antenna ' + str(mfcal.refant) + ' with a solution interval of ' + str(mfcal.interval) + ' #')
        mfcal.go()
        self.logger.info('### Calibration of the flux calibrator done ###')

    def copy_gains(self):
        self.logger.info('### Copying gains to target dataset ###')
        gpcopy = lib.miriad('gpcopy')
        gpcopy.vis = self.fluxcal
        gpcopy.out = self.target
        self.logger.info('# ' + str(self.fluxcal) + ' => ' + str(self.target) + ' #')
        self.logger.info('### Gains copied ###')
        gpcopy.go()

    def go(self):
        '''
        Execute the full cross calibration process
        '''
        self.logger.info("########## Starting CROSS CALIBRATION ##########")
        self.director('ch', self.crosscaldir)
        if self.compensate_fringestop:
            self.comp_fstop()
            self.fluxcal_phasecal()
        if self.fluxcal_gains or self.fluxcal_bandpass:
            self.cal_fluxcal()
        if self.transfer_to_target:
            self.copy_gains()
        self.logger.info("########## CROSS CALIBRATION done ##########")

    ###########################################################################################
    ##### Functions to compensate for the fringe stopping. Hopefully not needed for long. #####
    ###########################################################################################

    def correct_freq(self):
        self.logger.info('# Correcting the observing frequency (sfreq keyword in MIRIAD) of dataset ' + self.vis + ' #')
        puthd = lib.miriad('puthd')
        puthd.in_ = self.vis + '/sfreq'
        puthd.value = self.obsfreq
        self.logger.info('# New frequency is ' + str(puthd.value) + ' #')
        puthd.go()

    def comp_fstop(self):
        '''
        Divide the dataset by a model of amplitude 1 at the North Pole to compensate for the non-existent fringe stopping
        '''
        self.logger.info('### Starting fringe stopping ###')
        # Correct for fringe stopping of the flux calibrator
        self.vis = self.fluxcal
        self.correct_freq()
        if self.equinox == 'J2000' or self.equinox == 'Apparent':
            fluxcalcoords = self.getradec(self.vis)
        elif self.quinox == 'current':
            equinox = self.getequinox(self.vis)
            self.logger.info('# Equinox of the day of the observation is ' + str(equinox) + ' #')
            fluxcalcoords = self.getradec(self.vis)
            curr_coords = fluxcalcoords.transform_to(FK5(equinox='J' + str(equinox)))
            self.logger.info('# Transforming coordinates to new equinox #')
        self.logger.info('# Coordinates of the flux calibrator are RA: ' + str(fluxcalcoords.ra.deg) + ' deg, DEC: ' + str(fluxcalcoords.dec.deg) + ' deg #')
        dec_off = self.calc_np_offset(curr_coords)
        self.logger.info('# Declination offset towards north pole for the flux calibrator is ' + str(dec_off) + ' arcsec #')
        self.fringe_stop(dec_off)
        # Correct for fringe stopping of the target field
        self.vis = self.target
        self.correct_freq()
        if self.equinox == 'J2000' or self.equinox == 'Apparent':
            targetcoords = self.getradec(self.vis)
        elif self.quinox == 'current':
            equinox = self.getequinox(self.vis)
            self.logger.info('# Equinox of the day of the observation is ' + str(equinox) + ' #')
            targetcoords = self.getradec(self.vis)
            curr_coords = targetcoords.transform_to(FK5(equinox='J' + str(equinox)))
            self.logger.info('# Transforming coordinates to new equinox #')
        self.logger.info('# Coordinates of the flux calibrator are RA: ' + str(targetcoords.ra.deg) + ' deg, DEC: ' + str(targetcoords.dec.deg) + ' deg #')
        dec_off = self.calc_np_offset(curr_coords)
        self.logger.info('# Declination offset towards north pole for the target field is ' + str(dec_off) + ' arcsec #')
        self.fringe_stop(dec_off)
        self.logger.info('### Fringe stopping done! ###')

    def fringe_stop(self, offset):
        self.correct_freq()
        self.logger.info('# Dividing by model at the north pole of unit amplitude #')
        uvmodel = lib.miriad('uvmodel')
        uvmodel.vis = self.vis
        uvmodel.options = 'divide'
        uvmodel.offset = '0,' + str(offset)
        uvmodel.out = self.vis.rstrip('.mir') + '_fs.mir'
        uvmodel.go()
        self.director('rm', self.vis)
        self.director('rn', self.vis, file=uvmodel.out)

    def calc_np_offset(self, coords):
        '''
        Calculates the offset of the actual position towards the North Pole
        infile: The coords to calculate the offset for
        '''
        dec_off = (90.0 - coords.dec.deg) * 3600.0
        return dec_off

    def fluxcal_phasecal(self):
        '''
        Self-calibrate the calibrator on phase to move it to the field centre to derive a good bandpass
        '''
        self.logger.info('### Self-calibrating calibrator to move it to the field centre ###')
        self.vis = self.fluxcal
        selfcal = lib.miriad('selfcal')
        selfcal.vis = self.vis
        selfcal.interval = self.selfcal_fluxcal_solint
        selfcal.options = 'mfs,phase'
        selfcal.go()
        self.logger.info('# Self calibrating calibrator dataset ' + self.vis + ' with solution interval ' + str(self.selfcal_fluxcal_solint) + ' #')
        uvcat = lib.miriad('uvcat')
        uvcat.vis = self.fluxcal
        uvcat.out = self.fluxcal + '.copy'
        uvcat.go()
        self.director('rm', self.fluxcal)
        self.director('rn', self.fluxcal, file=uvcat.out)
        self.logger.info('### Calibrator moved to the field centre ###')

    ##################################################################################################################
    ##### Helper functions to get coordinates and central frequency of a dataset and fix the coordinate notation #####
    ##################################################################################################################

    def getradec(self, infile):
        '''
        getradec: module to extract the pointing centre ra and dec from a miriad image file. Uses the PRTHD task in miriad
        inputs: infile (name of file)
        return: coords, an instance of the astropy.coordinates SkyCoord class which has a few convenient attributes.
        '''
        prthd = lib.basher('prthd in=' + infile)
        if self.equinox == 'J2000':
            regex = re.compile(".*(J2000).*")
        elif self.equinox == 'Apparent':
            regex = re.compile(".*(Apparent).*")
        coordline = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()
        rastr = coordline[3]
        decstr = coordline[5]
        rastr = self.fixra(rastr)
        coords = SkyCoord(FK5, ra=rastr, dec=decstr, unit=(u.deg, u.deg))
        return coords

    def fixra(self, ra0):
        '''
        fixra: module to fix the notation of the ra string
        ra0: input ra notation from a skycoords query
        return: the fixed notation for the ra
        '''
        R = ''
        s = 0
        for i in ra0:
            if i == ':':
                if s == 0:
                    R += 'h'
                    s += 1
                else:
                    R += 'm'
            else:
                R += i
        return R

    def getequinox(self, infile):
        '''
        param infile: The input file to calculate the current equinox for
        return: the equinox in decimal
        '''
        prthd = lib.basher('prthd in=' + infile)
        regex = re.compile(".*(First).*")
        datestr = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()[2]
        YY = int('20' + datestr[0:2])
        month_abbr = datestr[2:5].capitalize()
        MM = int(list(calendar.month_abbr).index(month_abbr))
        DD = int(datestr[5:7])
        hh = int(datestr.split(':')[1])
        mm = int(datestr.split(':')[2])
        ss = int(datestr.split(':')[3].split('.')[0])
        d = datetime(YY, MM, DD, hh, mm, ss)
        equinox = (float(d.strftime("%j")) - 1) / 366 + float(d.strftime("%Y"))
        return equinox

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
        elif option == 'mv': # Move
            if os.path.exists(dest):
                lib.basher("mv " + str(file) + " " + str(dest))
            else:
                os.mkdir(dest)
                lib.basher("mv " + str(file) + " " + str(dest))
        elif option == 'rn': # Rename
            lib.basher("mv " + str(file) + " " + str(dest))
        elif option == 'cp': # Copy
            lib.basher("cp -r " + str(file) + " " + str(dest))
        elif option == 'rm': # Remove
            lib.basher("rm -r " + str(dest))
        else:
            print('### Option not supported! Only mk, ch, mv, rm, and cp are supported! ###')