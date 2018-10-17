import ConfigParser
import glob
import logging

import numpy as np
import pandas as pd
import drivecasa
import os

from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.libs import lib


class convert:
    """
    Class to convert data from MS-format into UVFITS, and from UVFITS into MIRIAD format. Resulting datasets will have the endings .MS, .UVFITS, and .mir.
    """
    def __init__(self, file=None, **kwargs):
        logging.basicConfig(level=logging.DEBUG)
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
        subs_setinit.setinitdirs(self)

    ###################################################
    ##### Function to execute the data conversion #####
    ###################################################

    def go(self):
        """
        Executes the whole conversion from MS format to MIRIAD format of the flux calibrator, polarisation calibrator, and target dataset in the following order:
        ms2uvfits
        uvfits2miriad
        """
        self.logger.info('########## FILE CONVERSION started ##########')
        self.ms2miriad()
        self.logger.info('########## FILE CONVERSION done ##########')

    def ms2miriad(self):
        """
        Converts the data from MS to MIRIAD format via UVFITS using drivecasa. Does it for the flux calibrator, polarisation calibrator, and target field independently.
        """
        subs_setinit.setinitdirs(self)
        nbeams = 37

        # Create the parameters for the parameter file for converting from MS to UVFITS format

        convertfluxcalmsavailable = get_param_def(self, 'convert_fluxcal_MSavailable', False ) # Flux calibrator MS dataset available?
        convertpolcalmsavailable = get_param_def(self, 'convert_polcal_MSavailable', False ) # Polarised calibrator MS dataset available?
        converttargetbeamsmsavailable = get_param_def(self, 'convert_targetbeams_MSavailable', np.full((nbeams), False) ) # Target beam MS dataset available?
        convertfluxcalms2uvfits = get_param_def(self, 'convert_fluxcal_MS2UVFITS', False ) # Flux calibrator MS dataset converted to UVFITS?
        convertpolcalms2uvfits = get_param_def(self, 'convert_polcal_MS2UVFITS', False ) # Polarised calibrator MS dataset converted to UVFITS?
        converttargetbeamsms2uvfits = get_param_def(self, 'convert_targetbeams_MS2UVFITS', np.full((nbeams), False) ) # Target beam MS dataset converted to UVFITS?
        convertfluxcaluvfitsavailable = get_param_def(self, 'convert_fluxcal_UVFITSavailable', False ) # Flux calibrator UVFITS dataset available?
        convertpolcaluvfitsavailable = get_param_def(self, 'convert_polcal_UVFITSavailable', False ) # Polarised calibrator UVFITS dataset available?
        converttargetbeamsuvfitsavailable = get_param_def(self, 'convert_targetbeams_UVFITSavailable', np.full((nbeams), False) ) # Target beam UVFITS dataset available?
        convertfluxcaluvfits2miriad = get_param_def(self, 'convert_fluxcal_UVFITS2MIRIAD', False ) # Flux calibrator UVFITS dataset converted to MIRIAD?
        convertpolcaluvfits2miriad = get_param_def(self, 'convert_polcal_UVFITS2MIRIAD', False ) # Polarised calibrator UVFITS dataset converted to MIRIAD?
        converttargetbeamsuvfits2miriad = get_param_def(self, 'convert_targetbeams_UVFITS2MIRIAD', np.full((nbeams), False) ) # Target beam UVFITS dataset converted to MIRIAD?

        ###################################################
        # Check which datasets are available in MS format #
        ###################################################

        if self.fluxcal != '':
            convertfluxcalmsavailable = os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
        else:
            self.logger.warning('# Flux calibrator dataset not specified. Cannot convert flux calibrator! #')
        if self.polcal != '':
            convertpolcalmsavailable = os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
        else:
            self.logger.warning('# Polarised calibrator dataset not specified. Cannot convert polarised calibrator! #')
        if self.target != '':
            for b in range(nbeams):
                converttargetbeamsmsavailable[b] = os.path.isdir(self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
        else:
            self.logger.warning('# Target beam dataset not specified. Cannot convert target beams! #')

        # Save the derived parameters for the availability to the parameter file

        subs_param.add_param(self, 'convert_fluxcal_MSavailable', convertfluxcalmsavailable)
        subs_param.add_param(self, 'convert_polcal_MSavailable', convertpolcalmsavailable)
        subs_param.add_param(self, 'convert_targetbeams_MSavailable', converttargetbeamsmsavailable)

        ###############################################
        # Convert the available MS-datasets to UVFITS #
        ###############################################

        # Convert the flux calibrator
        if self.convert_fluxcal:
            if self.fluxcal != '':
                if convertfluxcaluvfits2miriad == False:
                    if convertfluxcalmsavailable:
                        self.logger.debug('# Converting flux calibrator dataset from MS to UVFITS format. #')
                        subs_managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.crosscalsubdir, verbose=False)
                        fc_convert = 'exportuvfits(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal + '", fitsfile="' + self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.fluxcal).rstrip('MS') + 'UVFITS' + '", datacolumn="data", combinespw=True, padwithflags=True, multisource=True, writestation=True)'
                        casacmd = [fc_convert]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=3600)
                        if os.path.isfile( self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip('MS') + 'UVFITS'):
                            convertfluxcalms2uvfits = True
                            self.logger.info('# Converted flux calibrator dataset from MS to UVFITS format! #')
                        else:
                            convertfluxcalms2uvfits = False
                            self.logger.warning('# Could not convert flux calibrator dataset from MS to UVFITS format! #')
                    else:
                        self.logger.warning('# Flux calibrator dataset not available! #')
                else:
                    self.logger.info('# Flux calibrator dataset was already converted from MS to UVFITS format #')
            else:
                self.logger.warning('# Flux calibrator dataset not specified. Cannot convert flux calibrator! #')
        else:
            self.logger.warning('# Not converting flux calibrator dataset! #')
        # Convert the polarised calibrator
        if self.convert_polcal:
            if self.polcal != '':
                if convertpolcaluvfits2miriad == False:
                    if convertpolcalmsavailable:
                        self.logger.debug('# Converting polarised calibrator dataset from MS to UVFITS format. #')
                        subs_managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.crosscalsubdir, verbose=False)
                        pc_convert = 'exportuvfits(vis="' + self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal + '", fitsfile="' + self.basedir + '00' + '/' + self.crosscalsubdir + '/' + str(self.polcal).rstrip('MS') + 'UVFITS' + '", datacolumn="data", combinespw=True, padwithflags=True, multisource=True, writestation=True)'
                        casacmd = [pc_convert]
                        casa = drivecasa.Casapy()
                        casa.run_script(casacmd, raise_on_severe=False, timeout=3600)
                        if os.path.isfile( self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip('MS') + 'UVFITS'):
                            convertpolcalms2uvfits = True
                            self.logger.info('# Converted polarised calibrator dataset from MS to UVFITS format! #')
                        else:
                            convertpolcalms2uvfits = False
                            self.logger.warning('# Could not convert polarised calibrator dataset from MS to UVFITS format! #')
                    else:
                        self.logger.warning('# Polarised calibrator dataset not available! #')
                else:
                    self.logger.info('# Polarised calibrator dataset was already converted from MS to UVFITS format #')
            else:
                self.logger.warning('# Polarised calibrator dataset not specified. Cannot convert polarised calibrator! #')
        else:
            self.logger.warning('# Not converting polarised calibrator dataset! #')
        # Convert the target beams
        if self.convert_target:
            if self.target != '':
                self.logger.info('# Converting target beam datasets from MS to UVFITS format. #')
                if self.convert_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                    self.logger.debug('# Converting all available target beam datasets #')
                else:
                    beams = self.convert_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in beams]
                    self.logger.debug('# Converting all selected target beam datasets #')
                for vis in datasets:
                    if converttargetbeamsuvfits2miriad[int(vis.split('/')[-3])] == False:
                        if converttargetbeamsmsavailable[int(vis.split('/')[-3])]:
                            subs_managefiles.director(self, 'mk', self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir, verbose=False)
                            tg_convert = 'exportuvfits(vis="' + self.basedir + vis.split('/')[-3] + '/' + self.rawsubdir + '/' + self.target + '", fitsfile="' + self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS' + '", datacolumn="data", combinespw=True, padwithflags=True, multisource=True, writestation=True)'
                            casacmd = [tg_convert]
                            casa = drivecasa.Casapy()
                            casa.run_script(casacmd, raise_on_severe=False, timeout=7200)
                            if os.path.isfile( self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS'):
                                converttargetbeamsms2uvfits[int(vis.split('/')[-3])] = True
                                self.logger.debug('# Converted dataset of target beam ' + vis.split('/')[-3] + ' from MS to UVFITS format! #')
                            else:
                                converttargetbeamsms2uvfits[int(vis.split('/')[-3])] = False
                                self.logger.warning('# Could not convert dataset for target beam ' + vis.split('/')[-3] + ' from MS to UVFITS format! #')
                        else:
                            self.logger.warning('# Dataset for target beam ' + vis.split('/')[-3] + ' not available! #')
                    else:
                        self.logger.info('# Dataset for target beam ' + vis.split('/')[-3] + ' was already converted from MS to UVFITS format #')
            else:
                self.logger.warning('# Target beam dataset(s) not specified. Cannot convert target beam datasets! #')
        else:
            self.logger.warning('# Not converting target beam dataset(s)! #')

        # Save the derived parameters for the MS to UVFITS conversion to the parameter file

        subs_param.add_param(self, 'convert_fluxcal_MS2UVFITS', convertfluxcalms2uvfits)
        subs_param.add_param(self, 'convert_polcal_MS2UVFITS', convertpolcalms2uvfits)
        subs_param.add_param(self, 'convert_targetbeams_MS2UVFITS', converttargetbeamsms2uvfits)

        #######################################################
        # Check which datasets are available in UVFITS format #
        #######################################################

        if self.fluxcal != '':
            convertfluxcaluvfitsavailable = os.path.isfile(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip('MS') + 'UVFITS')
        else:
            self.logger.warning('# Flux calibrator dataset not specified. Cannot convert flux calibrator! #')
        if self.polcal != '':
            convertpolcaluvfitsavailable = os.path.isfile(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip('MS') + 'UVFITS')
        else:
            self.logger.warning('# Polarised calibrator dataset not specified. Cannot convert polarised calibrator! #')
        if self.target != '':
            for b in range(nbeams):
                converttargetbeamsuvfitsavailable[b] = os.path.isfile(self.basedir + str(b).zfill(2) + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS')
        else:
            self.logger.warning('# Target beam dataset not specified. Cannot convert target beams! #')

        # Save the derived parameters for the availability to the parameter file

        subs_param.add_param(self, 'convert_fluxcal_UVFITSavailable', convertfluxcaluvfitsavailable)
        subs_param.add_param(self, 'convert_polcal_UVFITSavailable', convertpolcaluvfitsavailable)
        subs_param.add_param(self, 'convert_targetbeams_UVFITSavailable', converttargetbeamsuvfitsavailable)

        ##########################################################
        # Convert the available UVFITS-datasets to MIRIAD format #
        ##########################################################

        # Convert the flux calibrator
        if self.convert_fluxcal:
            if self.fluxcal != '':
                if convertfluxcaluvfits2miriad == False:
                    if convertfluxcaluvfitsavailable:
                        self.logger.debug('# Converting flux calibrator dataset from UVFITS to MIRIAD format. #')
                        subs_managefiles.director(self, 'ch', self.basedir + '00' + '/' + self.crosscalsubdir, verbose=False)
                        fits = lib.miriad('fits')
                        fits.op = 'uvin'
                        fits.in_ = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip('MS') + 'UVFITS'
                        fits.out = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip('MS') + 'mir'
                        fits.go()
                        if os.path.isdir( self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip('MS') + 'mir'):
                            convertfluxcaluvfits2miriad = True
                            self.logger.info('# Converted flux calibrator dataset from UVFITS to MIRIAD format! #')
                        else:
                            convertfluxcaluvfits2miriad = False
                            self.logger.warning('# Could not convert flux calibrator dataset from UVFITS to MIRIAD format! #')
                    else:
                        self.logger.warning('# Flux calibrator dataset not available! #')
                else:
                    self.logger.info('# Flux calibrator dataset was already converted from UVFITS to MIRIAD format #')
            else:
                self.logger.warning('# Flux calibrator dataset not specified. Cannot convert flux calibrator! #')
        else:
            self.logger.warning('# Not converting flux calibrator dataset! #')
        # Convert the polarised calibrator
        if self.convert_polcal:
            if self.polcal != '':
                if convertpolcaluvfits2miriad == False:
                    if convertpolcaluvfitsavailable:
                        self.logger.debug('# Converting polarised calibrator dataset from UVFITS to MIRIAD format. #')
                        subs_managefiles.director(self, 'ch',self.basedir + '00' + '/' + self.crosscalsubdir, verbose=False)
                        fits = lib.miriad('fits')
                        fits.op = 'uvin'
                        fits.in_ = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip('MS') + 'UVFITS'
                        fits.out = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip('MS') + 'mir'
                        fits.go()
                        if os.path.isdir(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip('MS') + 'mir'):
                            convertpolcaluvfits2miriad = True
                            self.logger.info('# Converted polarised calibrator dataset from UVFITS to MIRIAD format! #')
                        else:
                            convertpolcaluvfits2miriad = False
                            self.logger.warning('# Could not convert polarised calibrator dataset from UVFITS to MIRIAD format! #')
                    else:
                        self.logger.warning('# Polarised calibrator dataset not available! #')
                else:
                    self.logger.info('# Polarised calibrator dataset was already converted from UVFITS to MIRIAD format #')
            else:
                self.logger.warning('# Polarised calibrator dataset not specified. Cannot convert polarised calibrator! #')
        else:
            self.logger.warning('# Not converting polarised calibrator dataset! #')
        # Convert the target beams
        if self.convert_target:
            if self.target != '':
                self.logger.info('# Converting target beam datasets from UVFITS to MIRIAD format. #')
                if self.convert_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS')
                    self.logger.debug('# Converting all available target beam datasets #')
                else:
                    beams = self.convert_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS' for b in beams]
                    self.logger.debug('# Converting all selected target beam datasets #')
                for vis in datasets:
                    if converttargetbeamsuvfits2miriad[int(vis.split('/')[-3])] == False:
                        if converttargetbeamsuvfitsavailable[int(vis.split('/')[-3])]:
                            subs_managefiles.director(self, 'ch', self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir, verbose=False)
                            fits = lib.miriad('fits')
                            fits.op = 'uvin'
                            fits.in_ = self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS'
                            fits.out = self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'mir'
                            fits.go()
                            if os.path.isdir( self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'mir'):
                                converttargetbeamsuvfits2miriad[int(vis.split('/')[-3])] = True
                                self.logger.debug('# Converted dataset of target beam ' + vis.split('/')[-3] + ' from UVFITS to MIRIAD format! #')
                            else:
                                converttargetbeamsuvfits2miriad[int(vis.split('/')[-3])] = False
                                self.logger.warning('# Could not convert dataset for target beam ' + vis.split('/')[-3] + ' from UVFITS to MIRIAD format! #')
                        else:
                            self.logger.warning('# Dataset for target beam ' + vis.split('/')[-3] + ' not available! #')
                    else:
                        self.logger.info('# Dataset for target beam ' + vis.split('/')[-3] + ' was already converted from MS to UVFITS format #')
            else:
                self.logger.warning('# Target beam dataset(s) not specified. Cannot convert target beam datasets! #')
        else:
            self.logger.warning('# Not converting target beam dataset(s)! #')

        # Save the derived parameters for the MS to UVFITS conversion to the parameter file

        subs_param.add_param(self, 'convert_fluxcal_UVFITS2MIRIAD', convertfluxcaluvfits2miriad)
        subs_param.add_param(self, 'convert_polcal_UVFITS2MIRIAD', convertpolcaluvfits2miriad)
        subs_param.add_param(self, 'convert_targetbeams_UVFITS2MIRIAD', converttargetbeamsuvfits2miriad)

        #####################################
        # Remove the UVFITS files if wanted #
        #####################################

        if self.convert_removeuvfits:
            self.logger.info('# Removing all UVFITS files #')
            subs_managefiles.director(self, 'rm', self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip('MS') + 'UVFITS')
            subs_managefiles.director(self, 'rm', self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip('MS') + 'UVFITS')
            for beam in range(nbeams):
                if os.path.isdir(self.basedir + str(beam).zfill(2) + '/' + self.crosscalsubdir):
                    subs_managefiles.director(self, 'rm', self.basedir + str(beam).zfill(2) + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS')
                else:
                    pass

    #################################################################
    ##### Functions to create the summaries of the CONVERT step #####
    #################################################################

    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during CONVERT. No detailed summary is available for CONVERT.
        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the notebook
        """

        nbeams = 37

        # Load the parameters from the parameter file

        FMSA = subs_param.get_param(self, 'convert_fluxcal_MSavailable')
        PMSA = subs_param.get_param(self, 'convert_polcal_MSavailable')
        TMSA = subs_param.get_param(self, 'convert_targetbeams_MSavailable')

        FMS2UV = subs_param.get_param(self, 'convert_fluxcal_MS2UVFITS')
        PMS2UV = subs_param.get_param(self, 'convert_polcal_MS2UVFITS')
        TMS2UV = subs_param.get_param(self, 'convert_targetbeams_MS2UVFITS')

        FUV2mir = subs_param.get_param(self, 'convert_fluxcal_UVFITS2MIRIAD')
        PUV2mir = subs_param.get_param(self, 'convert_polcal_UVFITS2MIRIAD')
        TUV2mir = subs_param.get_param(self, 'convert_targetbeams_UVFITS2MIRIAD')

        # Create the data frame

        beam_range = range(nbeams)
        dataset_beams = [self.target[:-3] + ' Beam ' + str(b).zfill(2) for b in beam_range]
        dataset_indices = ['Flux calibrator (' + self.fluxcal[:-3] + ')', 'Polarised calibrator (' + self.polcal[:-3] + ')'] + dataset_beams

        all_MA = np.full(39, False)
        all_MA[0] = FMSA
        all_MA[1] = PMSA
        all_MA[2:] = TMSA

        all_M2U = np.full(39, False)
        all_M2U[0] = FMS2UV
        all_M2U[1] = PMS2UV
        all_M2U[2:] = TMS2UV

        all_U2mir = np.full(39, False)
        all_U2mir[0] = FUV2mir
        all_U2mir[1] = PUV2mir
        all_U2mir[2:] = TUV2mir

        df_msav = pd.DataFrame(np.ndarray.flatten(all_MA), index=dataset_indices, columns=['Available?'])
        df_ms2uv = pd.DataFrame(np.ndarray.flatten(all_M2U), index=dataset_indices, columns=['MS -> UVFITS'])
        df_uv2mir = pd.DataFrame(np.ndarray.flatten(all_U2mir), index=dataset_indices, columns=['UVFITS -> MIRIAD'])

        df = pd.concat([df_msav, df_ms2uv, df_uv2mir], axis=1)

        return df

    #######################################################################
    ##### Manage the creation and moving of new directories and files #####
    #######################################################################

    def show(self, showall=False):
        """
        show: Prints the current settings of the pipeline. Only shows keywords, which are in the default config file default.cfg
        showall: Set to true if you want to see all current settings instead of only the ones from the current step
        """
        subs_setinit.setinitdirs(self)
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
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in this step!
        """
        subs_setinit.setinitdirs(self)
        nbeams = 37

        self.logger.warning('### Deleting all converted data. ###')
        for beam in range(nbeams):
            if os.path.isdir(self.basedir + str(beam).zfill(2) + '/' + self.crosscalsubdir):
                subs_managefiles.director(self, 'rm', self.basedir + str(beam).zfill(2) + '/' + self.crosscalsubdir + '/*')
            else:
                pass
        self.logger.warning('### Deleting all parameter file entries for CONVERT module ###')
        subs_param.del_param(self, 'convert_fluxcal_MSavailable')
        subs_param.del_param(self, 'convert_polcal_MSavailable')
        subs_param.del_param(self, 'convert_targetbeams_MSavailable')
        subs_param.del_param(self, 'convert_fluxcal_MS2UVFITS')
        subs_param.del_param(self, 'convert_polcal_MS2UVFITS')
        subs_param.del_param(self, 'convert_targetbeams_MS2UVFITS')
        subs_param.del_param(self, 'convert_fluxcal_UVFITSavailable')
        subs_param.del_param(self, 'convert_polcal_UVFITSavailable')
        subs_param.del_param(self, 'convert_targetbeams_UVFITSavailable')
        subs_param.del_param(self, 'convert_fluxcal_UVFITS2MIRIAD')
        subs_param.del_param(self, 'convert_polcal_UVFITS2MIRIAD')
        subs_param.del_param(self, 'convert_targetbeams_UVFITS2MIRIAD')
