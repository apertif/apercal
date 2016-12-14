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

    ####################################################################################
    ##### Functions to execute the different modes of the self-calibration process #####
    ####################################################################################

    def go(self):
        '''
        Execute the full cross calibration process
        '''
        self.logger.info("########## Starting CROSS CALIBRATION ##########")
        self.fluxcal = self.fluxcal.rstrip('MS') + 'mir'
        self.polcal = self.polcal.rstrip('MS') + 'mir'
        self.target = self.target.rstrip('MS') + 'mir'
        self.director('ch', self.crosscaldir)
        if self.compensate_fringestop_fluxcal or self.compensate_fringestop_polcal or self.compensate_fringestop_target:
            self.comp_fstop()
        if self.fluxcal_gains or self.fluxcal_bandpass:
            self.cal_fluxcal()
        if self.transfer_to_target:
            self.copy_gains()
        self.logger.info("########## CROSS CALIBRATION done ##########")

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

    ###########################################################################################
    ##### Functions to compensate for the fringe stopping. Hopefully not needed for long. #####
    ###########################################################################################

    def comp_fstop(self):
        '''
        Divide the dataset by a model of amplitude 1 at the North Pole to compensate for the non-existent fringe stopping
        '''
        self.logger.info('### Doing fringe stopping ###')
        if self.compensate_fringestop_fluxcal:
            self.vis = self.fluxcal
            fluxcalcoords = self.getradec(self.vis)
            self.logger.info('# Apparent coordinates of the flux calibrator are RA: ' + str(fluxcalcoords.ra.deg) + ' deg, DEC: ' + str(fluxcalcoords.dec.deg) + ' deg #')
            equinox = self.getequinox(self.vis)
            self.logger.info('# Equinox of the day of the observation is ' + str(equinox) + ' #')
            curr_coords = fluxcalcoords.transform_to(FK5(equinox='J' + str(equinox)))
            self.logger.info('# Transforming coordinates to new equinox #')
            self.logger.info('# New coordinates are RA: '  + str(curr_coords.ra.deg) + ' deg, DEC: ' + str(curr_coords.dec.deg) + ' deg #')
            dec_off = self.calc_np_offset(curr_coords)
            self.logger.info('# Declination offset towards north pole for the flux calibrator is ' + str(dec_off) + ' arcsec #')
            self.fringe_stop(dec_off)
        if self.compensate_fringestop_polcal:
            self.vis = self.polcal
            polcalcoords = self.getradec(self.vis)
            self.logger.info('# Apparent coordinates of the polarisation calibrator are RA: ' + str(polcalcoords.ra.deg) + ' deg, DEC: ' + str(polcalcoords.dec.deg) + ' deg #')
            equinox = self.getequinox(self.vis)
            self.logger.info('# Equinox of the day of the observation is ' + str(equinox) + ' #')
            curr_coords = polcalcoords.transform_to(FK5(equinox='J' + str(equinox)))
            self.logger.info('# Transforming coordinates to new equinox #')
            self.logger.info('# New coordinates are RA: ' + str(curr_coords.ra.deg) + ' deg, DEC: ' + str(curr_coords.dec.deg) + ' deg #')
            dec_off = self.calc_np_offset(curr_coords)
            self.logger.info('# Declination offset towards north pole for the polarised calibrator is ' + str(dec_off) + ' arcsec #')
            self.fringe_stop(dec_off)
        if self.compensate_fringestop_target:
            self.vis = self.target
            targetcoords = self.getradec(self.vis)
            self.logger.info('# Apparent coordinates of the target are RA: ' + str(targetcoords.ra.deg) + ' deg, DEC: ' + str(targetcoords.dec.deg) + ' deg #')
            equinox = self.getequinox(self.vis)
            self.logger.info('# Equinox of the day of the observation is ' + str(equinox) + ' #')
            curr_coords = targetcoords.transform_to(FK5(equinox='J' + str(equinox)))
            self.logger.info('# Transforming coordinates to new equinox #')
            self.logger.info('# New coordinates are RA: ' + str(curr_coords.ra.deg) + ' deg, DEC: ' + str(curr_coords.dec.deg) + ' deg #')
            dec_off = self.calc_np_offset(curr_coords)
            self.logger.info('# Declination offset towards north pole for the target is ' + str(dec_off) + ' arcsec #')
            self.fringe_stop(dec_off)
        self.logger.info('### Fringe stopping done! ###')

    def correct_freq(self):
        self.logger.info('# Correcting the observing frequency (sfreq keyword in MIRIAD) #')
        puthd = lib.miriad('puthd')
        puthd.in_ = self.vis + '/sfreq'
        puthd.value = self.obsfreq
        self.logger.info('# New frequency is ' + str(puthd.value) + ' #')
        puthd.go()

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
        regex = re.compile(".*(J2000).*")
        # regex = re.compile(".*(Apparent).*")
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