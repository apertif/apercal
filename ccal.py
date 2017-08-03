__author__ = "Bradley Frank, Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "frank@astron.nl, adebahr@astron.nl"

import re
import lib
import logging
import os, sys
import ConfigParser
import aipy
from datetime import datetime
import calendar
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.coordinates import FK5

####################################################################################################

class ccal:
    '''
    Crosscal class to handle applying the calibrator gains and prepare the dataset for self-calibration.
    '''
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('CROSSCAL')
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
        self.finaldir = self.basedir + self.finalsubdir

        # Name the datasets
        self.fluxcal = self.fluxcal.rstrip('MS') + 'mir'
        self.polcal = self.polcal.rstrip('MS') + 'mir'
        self.target = self.target.rstrip('MS') + 'mir'

    #############################################################
    ##### Function to execute the cross-calibration process #####
    #############################################################

    def go(self):
        '''
        Executes the full cross calibration process in the following order.
        fringe_stop
        applysys
        bandpass
        polarisation
        tranfer_to_target
        '''
        self.logger.info("########## Starting CROSS CALIBRATION ##########")
        self.fringe_stop()
        self.applysys()
        self.bandpass()
        self.polarisation()
        self.transfer_to_target()
        self.logger.info("########## CROSS CALIBRATION done ##########")

    ###########################################################################################
    ##### Functions to compensate for the fringe stopping. Hopefully not needed for long. #####
    ###########################################################################################

    # def correct_freq(self):
    #     self.logger.info('# Correcting the observing frequency (sfreq keyword in MIRIAD) of dataset ' + self.vis + ' #')
    #     puthd = lib.miriad('puthd')
    #     puthd.in_ = self.vis + '/sfreq'
    #     puthd.value = self.obsfreq
    #     self.logger.info('# New frequency is ' + str(puthd.value) + ' #')
    #     puthd.go()

    # def calc_np_offset(self, coords):
    #     '''
    #     Calculates the offset of the actual position towards the North Pole
    #     infile: The coords to calculate the offset for
    #     '''
    #     dec_off = (90.0 - coords.dec.deg) * 3600.0
    #     return dec_off

    # def comp_fstop(self):
    #     '''
    #     Divide the dataset by a model of amplitude 1 at the North Pole to compensate for the non-existent fringe stopping
    #     '''
    #     self.logger.info('### Starting fringe stopping ###')
    #     # Correct for fringe stopping of the flux calibrator
    #     self.vis = self.fluxcal
    #     self.correct_freq()
    #     if self.equinox == 'J2000' or self.equinox == 'Apparent':
    #         fluxcalcoords = self.getradec(self.vis)
    #     elif self.quinox == 'current':
    #         equinox = self.getequinox(self.vis)
    #         self.logger.info('# Equinox of the day of the observation is ' + str(equinox) + ' #')
    #         fluxcalcoords = self.getradec(self.vis)
    #         curr_coords = fluxcalcoords.transform_to(FK5(equinox='J' + str(equinox)))
    #         self.logger.info('# Transforming coordinates to new equinox #')
    #     self.logger.info('# Coordinates of the flux calibrator are RA: ' + str(fluxcalcoords.ra.deg) + ' deg, DEC: ' + str(fluxcalcoords.dec.deg) + ' deg #')
    #     dec_off = self.calc_np_offset(curr_coords)
    #     self.logger.info('# Declination offset towards north pole for the flux calibrator is ' + str(dec_off) + ' arcsec #')
    #     self.fringe_stop(dec_off)
    #     # Correct for fringe stopping of the target field
    #     self.vis = self.target
    #     self.correct_freq()
    #     if self.equinox == 'J2000' or self.equinox == 'Apparent':
    #         targetcoords = self.getradec(self.vis)
    #     elif self.quinox == 'current':
    #         equinox = self.getequinox(self.vis)
    #         self.logger.info('# Equinox of the day of the observation is ' + str(equinox) + ' #')
    #         targetcoords = self.getradec(self.vis)
    #         curr_coords = targetcoords.transform_to(FK5(equinox='J' + str(equinox)))
    #         self.logger.info('# Transforming coordinates to new equinox #')
    #     self.logger.info('# Coordinates of the flux calibrator are RA: ' + str(targetcoords.ra.deg) + ' deg, DEC: ' + str(targetcoords.dec.deg) + ' deg #')
    #     dec_off = self.calc_np_offset(curr_coords)
    #     self.logger.info('# Declination offset towards north pole for the target field is ' + str(dec_off) + ' arcsec #')
    #     self.fringe_stop(dec_off)
    #     self.logger.info('### Fringe stopping done! ###')

    def fringe_stop(self):
        '''
        Does the fringe stopping for APERTIF data. Only usable for strong point sources at the moment like 3C147. Moves the source to the right position by calibrating on phase for each integration (mostly 1s).
        '''
        if self.crosscal_mode == 'APERTIF':
            if self.crosscal_fringestop:
                self.logger.info('### Fringe stopping started ###')
                self.director('ch', self.crosscaldir)
                if self.crosscal_fringestop_mode == 'direct':
                    self.logger.info('# Doing fringe stopping by using the integration time of the observation and a point source model #')
                    selfcal = lib.miriad('selfcal')
                    selfcal.vis = self.fluxcal
                    selfcal.interval = 0.016666
                    selfcal.options = 'phase'
                    selfcal.go()
                    self.logger.info('# Self calibrating flux calibrator dataset ' + self.fluxcal + ' with solution interval ' + str(selfcal.interval) + ' #')
                    uvcat = lib.miriad('uvcat')
                    uvcat.vis = self.fluxcal
                    uvcat.out = self.fluxcal + '.copy'
                    uvcat.go()
                    self.director('rm', self.fluxcal)
                    self.director('rn', self.fluxcal, file=uvcat.out)
                # elif self.crosscal_fringestop_mode == 'northpole':
                #     self.correct_freq()
                #     self.logger.info('# Dividing by model at the north pole of unit amplitude #')
                #     uvmodel = lib.miriad('uvmodel')
                #     uvmodel.vis = self.vis
                #     uvmodel.options = 'divide'
                #     uvmodel.offset = '0,' + str(offset)
                #     uvmodel.out = self.vis.rstrip('.mir') + '_fs.mir'
                #     uvmodel.go()
                #     self.director('rm', self.vis)
                #     self.director('rn', self.vis, file=uvmodel.out)
                else:
                    self.logger.error('# Fringe stopping mode not supported! Exiting! #')
                    sys.exit(1)
                self.logger.info('### Fringe stopping done ###')
        elif self.crosscal_mode == 'WSRT':
            self.logger.info('### WSRT data set. Fringe stopping was done online! ###')
        else:
            self.logger.error('### Crosscal mode not known! Exiting!')
            sys.exit(1)

    def applysys(self):
        '''
        Apply the system temperatures to the data if it is old WSRT data
        '''
        if self.crosscal_applysys:
            self.director('ch', self.crosscaldir)
            self.logger.info('### Applying system temperatures corrections ###')
            attsys = lib.miriad('attsys')
            self.logger.info('# Applying system temperature corrections to flux calibrator data #')
            attsys.vis = self.fluxcal
            attsys.out = self.fluxcal + '_temp'
            attsys.go()
            self.director('rm', self.fluxcal)
            self.director('rn', self.fluxcal, file=attsys.out)
            self.logger.info('# System temperatures corrections to flux calibrator data applied #')
            if os.path.isdir(self.crosscaldir + '/' + self.polcal):
                self.logger.info('# Applying system temperature corrections to polarised calibrator data #')
                attsys.vis = self.polcal
                attsys.out = self.polcal + '_temp'
                attsys.go()
                self.director('rm', self.polcal)
                self.director('rn', self.polcal, file=attsys.out)
                self.logger.info('# System temperatures corrections to polarised calibrator data applied #')
            self.logger.info('# Applying system temperature corrections to target data #')
            attsys.vis = self.target
            attsys.out = self.target + '_temp'
            attsys.go()
            self.director('rm', self.target)
            self.director('rn', self.target, file=attsys.out)
            self.logger.info('# System temperatures corrections to target data applied #')
            self.logger.info('### System temperatures corrections applied ###')

    def bandpass(self):
        '''
        Calibrates the bandpass for the flux calibrator using mfcal in MIRIAD.
        '''
        if self.crosscal_bandpass:
            self.director('ch', self.crosscaldir)
            self.logger.info('### Bandpass calibration on the flux calibrator data started ###')
            mfcal = lib.miriad('mfcal')
            mfcal.vis = self.fluxcal
            if self.crosscal_delay:
                mfcal.options = 'delay'
            else:
                pass
            mfcal.interval = 1000
            mfcal.go()
            self.logger.info('### Bandpass calibration on the flux calibrator data done ###')

    def polarisation(self):
        '''
        Derives the polarisation corrections (leakage, angle) from the polarised calibrator. Uses the bandpass from the bandpass calibrator. Does not account for freqeuncy dependent solutions at the moment.
        '''
        if self.crosscal_polarisation:
            self.director('ch', self.crosscaldir)
            self.logger.info('### Polarisation calibration on the polarised calibrator data started ###')
            if os.path.isfile(self.crosscaldir + '/' + self.fluxcal + '/' + 'bandpass'):
                self.logger.info('# Bandpass solutions in flux calibrator data found. Using them! #')
                gpcopy = lib.miriad('gpcopy')
                gpcopy.vis = self.fluxcal
                gpcopy.out = self.polcal
                gpcopy.mode = 'copy'
                gpcopy.options = 'nopol,relax'
                gpcopy.go()
                self.logger.info('# Bandpass from flux calibrator data copied to polarised calibrator data #')
                gpcal = lib.miriad('gpcal')
                gpcal.vis = self.polcal
                # uv = aipy.miriad.UV(self.polcal)
                # nchan = uv['nchan']
                # gpcal.nfbin = round(nchan / self.crosscal_polarisation_nchan)
                gpcal.options = 'xyvary,linear'
                gpcal.go()
                self.logger.info('# Solved for polarisation leakage and angle on polarised calibrator #')
            else:
                self.logger.info('# Bandpass solutions from flux calibrator not found #')
                self.logger.info('# Deriving bandpass from polarised calibrator using mfcal #')
                mfcal = lib.miriad('mfcal')
                mfcal.vis = self.polcal
                mfcal.go()
                self.logger.info('# Bandpass solutions from polarised calibrator derived #')
                self.logger.info('# Continuing with polarisation calibration (leakage, angle) from polarised calibrator data #')
                gpcal = lib.miriad('gpcal')
                gpcal.vis = self.polcal
                # uv = aipy.miriad.UV(self.polcal)
                # nchan = uv['nchan']
                # gpcal.nfbin = round(nchan / self.crosscal_polarisation_nchan)
                gpcal.options = 'xyvary,linear'
                gpcal.go()
                self.logger.info('# Solved for polarisation leakage and angle on polarised calibrator #')
            self.logger.info('### Polarisation calibration on the polarised calibrator data done ###')
        else:
            self.logger.info('### No polarisation calibration done! ###')

    def transfer_to_target(self):
        '''
        Transfers the gains of the calibrators to the target field. Automatically checks if polarisation calibration has been done.
        '''
        if self.crosscal_transfer_to_target:
            self.director('ch', self.crosscaldir)
            self.logger.info('### Copying calibrator solutions to target dataset ###')
            gpcopy = lib.miriad('gpcopy')
            if os.path.isfile(self.crosscaldir + '/' + self.polcal + '/' + 'bandpass') and os.path.isfile(self.crosscaldir + '/' + self.polcal + '/' + 'gains') and os.path.isfile(self.crosscaldir + '/' + self.polcal + '/' + 'leakage'):
                gpcopy.vis = self.polcal
                self.logger.info('# Copying calibrator solutions (bandpass, gains, leakage, angle) from polarised calibrator #')
            elif os.path.isfile(self.crosscaldir + '/' + self.fluxcal + '/' + 'bandpass') and os.path.isfile(self.crosscaldir + '/' + self.fluxcal + '/' + 'gains'):
                gpcopy.vis = self.fluxcal
                self.logger.info('# Copying calibrator solutions (bandpass, gains) from flux calibrator #')
                self.logger.info('# Polarisation calibration solutions (leakage, angle) not found #')
            else:
                self.logger.error('# No calibrator solutions found! Exiting! #')
                sys.exit(1)
            gpcopy.out = self.target
            gpcopy.options = 'relax'
            gpcopy.go()
            self.logger.info('### All solutions copied to target data ###')
        else:
            self.logger.info('### No copying of calibrator solutions to target data done! ###')

    ##################################################################################################################
    ##### Helper functions to get coordinates and central frequency of a dataset and fix the coordinate notation #####
    ##################################################################################################################

    # def getradec(self, infile):
    #     '''
    #     getradec: module to extract the pointing centre ra and dec from a miriad image file. Uses the PRTHD task in miriad
    #     inputs: infile (name of file)
    #     return: coords, an instance of the astropy.coordinates SkyCoord class which has a few convenient attributes.
    #     '''
    #     prthd = lib.basher('prthd in=' + infile)
    #     if self.equinox == 'J2000':
    #         regex = re.compile(".*(J2000).*")
    #     elif self.equinox == 'Apparent':
    #         regex = re.compile(".*(Apparent).*")
    #     coordline = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()
    #     rastr = coordline[3]
    #     decstr = coordline[5]
    #     rastr = self.fixra(rastr)
    #     coords = SkyCoord(FK5, ra=rastr, dec=decstr, unit=(u.deg, u.deg))
    #     return coords

    # def fixra(self, ra0):
    #     '''
    #     fixra: module to fix the notation of the ra string
    #     ra0: input ra notation from a skycoords query
    #     return: the fixed notation for the ra
    #     '''
    #     R = ''
    #     s = 0
    #     for i in ra0:
    #         if i == ':':
    #             if s == 0:
    #                 R += 'h'
    #                 s += 1
    #             else:
    #                 R += 'm'
    #         else:
    #             R += i
    #     return R

    # def getequinox(self, infile):
    #     '''
    #     param infile: The input file to calculate the current equinox for
    #     return: the equinox in decimal
    #     '''
    #     prthd = lib.basher('prthd in=' + infile)
    #     regex = re.compile(".*(First).*")
    #     datestr = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()[2]
    #     YY = int('20' + datestr[0:2])
    #     month_abbr = datestr[2:5].capitalize()
    #     MM = int(list(calendar.month_abbr).index(month_abbr))
    #     DD = int(datestr[5:7])
    #     hh = int(datestr.split(':')[1])
    #     mm = int(datestr.split(':')[2])
    #     ss = int(datestr.split(':')[3].split('.')[0])
    #     d = datetime(YY, MM, DD, hh, mm, ss)
    #     equinox = (float(d.strftime("%j")) - 1) / 366 + float(d.strftime("%Y"))
    #     return equinox

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
                if s == 'CROSSCAL':
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
        self.logger.warning('### Deleting all cross calibrated data. ###')
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