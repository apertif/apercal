import glob
import logging

import numpy as np
import pandas as pd
import os

from apercal.subs import setinit as subs_setinit
from apercal.subs import managefiles as subs_managefiles
from apercal.subs.param import get_param_def
from apercal.subs import param as subs_param
from apercal.subs import msutils as subs_msutils
from apercal.libs import lib

logger = logging.getLogger(__name__)


class convert:
    """
    Class to convert data from MS-format into UVFITS, and from UVFITS into MIRIAD format. Resulting datasets will
    have the endings .MS, .UVFITS, and .mir.
    """
    fluxcal = None
    polcal = None
    target = None
    basedir = None
    beam = None
    rawsubdir = None
    crosscalsubdir = None
    selfcalsubdir = None
    linesubdir = None
    contsubdir = None
    polsubdir = None
    mossubdir = None
    transfersubdir = None

    convert_fluxcal = True  # Convert the flux calibrator dataset
    convert_polcal = True  # Convert the polarised calibrator dataset
    convert_target = True  # Convert the target beam dataset
    convert_targetbeams = 'all'  # Targetbeams to convert, options: 'all' or '00,01,02'
    convert_removeuvfits = True  # Remove the UVFITS files

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)

    def go(self):
        """
        Executes the whole conversion from MS format to MIRIAD format of the flux calibrator, polarisation calibrator
         and target dataset in the following order:
        ms2uvfits
        uvfits2miriad
        """
        logger.info('FILE CONVERSION started')
        self.ms2miriad()
        logger.info('FILE CONVERSION done')

    def ms2miriad(self):
        """
        Converts the data from MS to MIRIAD format via UVFITS using drivecasa. Does it for the flux calibrator,
        polarisation calibrator, and target field independently.
        """
        subs_setinit.setinitdirs(self)
        nbeams = 37

        # Create the parameters for the parameter file for converting from MS to UVFITS format

        # Flux calibrator MS dataset available?
        convertfluxcalmsavailable = get_param_def(self, 'convert_fluxcal_MSavailable', False)

        # Polarised calibrator MS dataset available?
        convertpolcalmsavailable = get_param_def(self, 'convert_polcal_MSavailable', False)

        # Target beam MS dataset available?
        converttargetbeamsmsavailable = get_param_def(self, 'convert_targetbeams_MSavailable', np.full(nbeams, False))

        # Flux calibrator MS dataset converted to UVFITS?
        convertfluxcalms2uvfits = get_param_def(self, 'convert_fluxcal_MS2UVFITS', False)

        # Polarised calibrator MS dataset converted to UVFITS?
        convertpolcalms2uvfits = get_param_def(self, 'convert_polcal_MS2UVFITS', False)

        # Target beam MS dataset converted to UVFITS?
        converttargetbeamsms2uvfits = get_param_def(self, 'convert_targetbeams_MS2UVFITS', np.full(nbeams, False))

        # Flux calibrator UVFITS dataset available?
        convertfluxcaluvfitsavailable = get_param_def(self, 'convert_fluxcal_UVFITSavailable', False)

        # Polarised calibrator UVFITS dataset available?
        convertpolcaluvfitsavailable = get_param_def(self, 'convert_polcal_UVFITSavailable', False)

        # Target beam UVFITS dataset available?
        converttargetbeamsuvfitsavailable = get_param_def(self, 'convert_targetbeams_UVFITSavailable',
                                                          np.full(nbeams, False))

        # Flux calibrator UVFITS dataset converted to MIRIAD?
        convertfluxcaluvfits2miriad = get_param_def(self, 'convert_fluxcal_UVFITS2MIRIAD', False)

        # Polarised calibrator UVFITS dataset converted to MIRIAD?
        convertpolcaluvfits2miriad = get_param_def(self, 'convert_polcal_UVFITS2MIRIAD', False)
        # Target beam UVFITS dataset converted to MIRIAD?

        converttargetbeamsuvfits2miriad = get_param_def(self, 'convert_targetbeams_UVFITS2MIRIAD',
                                                        np.full(nbeams, False))

        # Check which datasets are available in MS format #
        if self.fluxcal != '':
            convertfluxcalmsavailable = os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal)
        else:
            logger.warning('Flux calibrator dataset not specified. Cannot convert flux calibrator!')
        if self.polcal != '':
            convertpolcalmsavailable = os.path.isdir(self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal)
        else:
            logger.warning('Polarised calibrator dataset not specified. Cannot convert polarised calibrator!')
        if self.target != '':
            for b in range(nbeams):
                converttargetbeamsmsavailable[b] = os.path.isdir(
                    self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target)
        else:
            logger.warning('Target beam dataset not specified. Cannot convert target beams!')

        # Save the derived parameters for the availability to the parameter file

        subs_param.add_param(self, 'convert_fluxcal_MSavailable', convertfluxcalmsavailable)
        subs_param.add_param(self, 'convert_polcal_MSavailable', convertpolcalmsavailable)
        subs_param.add_param(self, 'convert_targetbeams_MSavailable', converttargetbeamsmsavailable)

        # Convert the available MS-datasets to UVFITS #
        raw_convert_cmd = 'exportuvfits(vis="{basedir}00/{rawsubdir}/{cal}", ' \
                          'fitsfile="{basedir}00/{crosscalsubdir}/{calbase}UVFITS", datacolumn="{datacolumn}", ' \
                          'combinespw=True, padwithflags=True, multisource=True, writestation=True)'

        # Convert the flux calibrator
        if self.convert_fluxcal:
            if self.fluxcal != '':
                if not convertfluxcaluvfits2miriad:
                    if convertfluxcalmsavailable:
                        logger.debug('Converting flux calibrator dataset from MS to UVFITS format.')
                        subs_managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.crosscalsubdir,
                                                  verbose=False)
                        path = self.basedir + '00' + '/' + self.rawsubdir + '/' + self.fluxcal
                        if subs_msutils.has_correcteddata(path):
                            fc_convert = raw_convert_cmd.format(basedir=self.basedir, rawsubdir=self.rawsubdir,
                                                                cal=self.fluxcal, calbase=self.fluxcal[:-2],
                                                                crosscalsubdir=self.crosscalsubdir,
                                                                datacolumn="corrected")
                        else:
                            fc_convert = raw_convert_cmd.format(basedir=self.basedir, rawsubdir=self.rawsubdir,
                                                                cal=self.fluxcal, calbase=self.fluxcal[:-2],
                                                                crosscalsubdir=self.crosscalsubdir,
                                                                datacolumn="data")
                            logger.warning('Flux calibrator does not have a corrected_data column! Using uncorrected'
                                           'data for conversion!')

                        lib.run_casa([fc_convert], timeout=3600)
                        if os.path.isfile(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip(
                                'MS') + 'UVFITS'):
                            convertfluxcalms2uvfits = True
                            logger.info('Converted flux calibrator dataset from MS to UVFITS format!')
                        else:
                            convertfluxcalms2uvfits = False
                            logger.warning('Could not convert flux calibrator dataset from MS to UVFITS format!')
                    else:
                        logger.warning('Flux calibrator dataset not available!')
                else:
                    logger.info('Flux calibrator dataset was already converted from MS to UVFITS format')
            else:
                logger.warning('Flux calibrator dataset not specified. Cannot convert flux calibrator!')
        else:
            logger.warning('Not converting flux calibrator dataset!')

        # Convert the polarised calibrator
        if self.convert_polcal:
            if self.polcal != '':
                if not convertpolcaluvfits2miriad:
                    if convertpolcalmsavailable:
                        logger.debug('Converting polarised calibrator dataset from MS to UVFITS format.')
                        subs_managefiles.director(self, 'mk', self.basedir + '00' + '/' + self.crosscalsubdir,
                                                  verbose=False)
                        path = self.basedir + '00' + '/' + self.rawsubdir + '/' + self.polcal
                        if subs_msutils.has_correcteddata(path):
                            pc_convert = raw_convert_cmd.format(basedir=self.basedir, rawsubdir=self.rawsubdir,
                                                                cal=self.fluxcal, calbase=self.polcal[:-2],
                                                                crosscalsubdir=self.crosscalsubdir,
                                                                datacolumn="corrected")
                        else:
                            pc_convert = raw_convert_cmd.format(basedir=self.basedir, rawsubdir=self.rawsubdir,
                                                                cal=self.fluxcal, calbase=self.polcal[:-2],
                                                                crosscalsubdir=self.crosscalsubdir,
                                                                datacolumn="data")
                            logger.warning('Polarised calibrator does not have a corrected_data column! Using'
                                           'uncorrected data for conversion!')

                        lib.run_casa([pc_convert], timeout=3600)
                        if os.path.isfile(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip(
                                'MS') + 'UVFITS'):
                            convertpolcalms2uvfits = True
                            logger.info('Converted polarised calibrator dataset from MS to UVFITS format!')
                        else:
                            convertpolcalms2uvfits = False
                            logger.warning('Could not convert polarised calibrator dataset from MS to UVFITS format!')
                    else:
                        logger.warning('Polarised calibrator dataset not available!')
                else:
                    logger.info('Polarised calibrator dataset was already converted from MS to UVFITS format')
            else:
                logger.warning('Polarised calibrator dataset not specified. Cannot convert polarised calibrator!')
        else:
            logger.warning('Not converting polarised calibrator dataset!')

        # Convert the target beams
        if self.convert_target:
            if self.target != '':
                logger.info('Converting target beam datasets from MS to UVFITS format.')
                if self.convert_targetbeams == 'all':
                    datasets = glob.glob(self.basedir + '[0-9][0-9]' + '/' + self.rawsubdir + '/' + self.target)
                    logger.debug('Converting all available target beam datasets')
                else:
                    beams = self.convert_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.rawsubdir + '/' + self.target for b in
                                beams]
                    logger.debug('Converting all selected target beam datasets')
                for vis in datasets:
                    if not converttargetbeamsuvfits2miriad[int(vis.split('/')[-3])]:
                        if converttargetbeamsmsavailable[int(vis.split('/')[-3])]:
                            subs_managefiles.director(self, 'mk',
                                                      self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir,
                                                      verbose=False)

                            beam_dataset = vis.split('/')[-3]
                            raw_tg_cmd = 'exportuvfits(vis="{basedir}{beam_dataset}/{rawsubdir}/{target}", ' \
                                         'fitsfile="{basedir}{beam_dataset}/{crosscalsubdir}/{targetbase}UVFITS", ' \
                                         'datacolumn="{datacolumn}", combinespw=True, padwithflags=True, ' \
                                         'multisource=True, writestation=True)'

                            path = self.basedir + beam_dataset + '/' + self.rawsubdir + '/' + self.target
                            if subs_msutils.has_correcteddata(path):
                                datacolumn = "corrected"
                            else:
                                datacolumn = "data"
                                logger.warning('Target beam dataset {} does not have a corrected_data column! Using '
                                               'uncorrected data for conversion!'.format(beam_dataset))

                            tg_convert = raw_tg_cmd.format(basedir=self.basedir, rawsubdir=self.rawsubdir,
                                                           target=self.target, crosscalsubdir=self.crosscalsubdir,
                                                           targetbase=self.target.rstrip('MS'), datacolumn=datacolumn,
                                                           beam_dataset=beam_dataset)

                            lib.run_casa([tg_convert], timeout=7200)
                            if os.path.isfile(self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir + '/' +
                                              self.target.rstrip('MS') + 'UVFITS'):
                                converttargetbeamsms2uvfits[int(vis.split('/')[-3])] = True
                                logger.debug('Converted dataset of target beam ' + vis.split('/')[
                                    -3] + ' from MS to UVFITS format!')
                            else:
                                converttargetbeamsms2uvfits[int(vis.split('/')[-3])] = False
                                logger.warning('Could not convert dataset for target beam ' + vis.split('/')[
                                    -3] + ' from MS to UVFITS format!')
                        else:
                            logger.warning('Dataset for target beam ' + vis.split('/')[-3] + ' not available!')
                    else:
                        logger.info('Dataset for target beam ' + vis.split('/')[
                            -3] + ' was already converted from MS to UVFITS format')
            else:
                logger.warning('Target beam dataset(s) not specified. Cannot convert target beam datasets!')
        else:
            logger.warning('Not converting target beam dataset(s)!')

        # Save the derived parameters for the MS to UVFITS conversion to the parameter file

        subs_param.add_param(self, 'convert_fluxcal_MS2UVFITS', convertfluxcalms2uvfits)
        subs_param.add_param(self, 'convert_polcal_MS2UVFITS', convertpolcalms2uvfits)
        subs_param.add_param(self, 'convert_targetbeams_MS2UVFITS', converttargetbeamsms2uvfits)

        # Check which datasets are available in UVFITS format #
        if self.fluxcal != '':
            convertfluxcaluvfitsavailable = os.path.isfile(
                self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip('MS') + 'UVFITS')
        else:
            logger.warning('Flux calibrator dataset not specified. Cannot convert flux calibrator!')
        if self.polcal != '':
            convertpolcaluvfitsavailable = os.path.isfile(
                self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip('MS') + 'UVFITS')
        else:
            logger.warning('Polarised calibrator dataset not specified. Cannot convert polarised calibrator!')
        if self.target != '':
            for b in range(nbeams):
                converttargetbeamsuvfitsavailable[b] = os.path.isfile(
                    self.basedir + str(b).zfill(2) + '/' + self.crosscalsubdir + '/' + self.target.rstrip(
                        'MS') + 'UVFITS')
        else:
            logger.warning('Target beam dataset not specified. Cannot convert target beams!')

        # Save the derived parameters for the availability to the parameter file

        subs_param.add_param(self, 'convert_fluxcal_UVFITSavailable', convertfluxcaluvfitsavailable)
        subs_param.add_param(self, 'convert_polcal_UVFITSavailable', convertpolcaluvfitsavailable)
        subs_param.add_param(self, 'convert_targetbeams_UVFITSavailable', converttargetbeamsuvfitsavailable)

        # Convert the available UVFITS-datasets to MIRIAD format #

        # Convert the flux calibrator
        if self.convert_fluxcal:
            if self.fluxcal != '':
                if not convertfluxcaluvfits2miriad:
                    if convertfluxcaluvfitsavailable:
                        logger.debug('Converting flux calibrator dataset from UVFITS to MIRIAD format.')
                        subs_managefiles.director(self, 'ch', self.basedir + '00' + '/' + self.crosscalsubdir,
                                                  verbose=False)
                        fits = lib.miriad('fits')
                        fits.op = 'uvin'
                        fits.in_ = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip(
                            'MS') + 'UVFITS'
                        fits.out = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip(
                            'MS') + 'mir'
                        fits.go()
                        if os.path.isdir(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip(
                                'MS') + 'mir'):
                            convertfluxcaluvfits2miriad = True
                            logger.info('Converted flux calibrator dataset from UVFITS to MIRIAD format!')
                        else:
                            convertfluxcaluvfits2miriad = False
                            logger.warning('Could not convert flux calibrator dataset from UVFITS to MIRIAD format!')
                    else:
                        logger.warning('Flux calibrator dataset not available!')
                else:
                    logger.info('Flux calibrator dataset was already converted from UVFITS to MIRIAD format')
            else:
                logger.warning('Flux calibrator dataset not specified. Cannot convert flux calibrator!')
        else:
            logger.warning('Not converting flux calibrator dataset!')
        # Convert the polarised calibrator
        if self.convert_polcal:
            if self.polcal != '':
                if not convertpolcaluvfits2miriad:
                    if convertpolcaluvfitsavailable:
                        logger.debug('Converting polarised calibrator dataset from UVFITS to MIRIAD format.')
                        subs_managefiles.director(self, 'ch', self.basedir + '00' + '/' + self.crosscalsubdir,
                                                  verbose=False)
                        fits = lib.miriad('fits')
                        fits.op = 'uvin'
                        fits.in_ = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip(
                            'MS') + 'UVFITS'
                        fits.out = self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip(
                            'MS') + 'mir'
                        fits.go()
                        if os.path.isdir(self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip(
                                'MS') + 'mir'):
                            convertpolcaluvfits2miriad = True
                            logger.info('Converted polarised calibrator dataset from UVFITS to MIRIAD format!')
                        else:
                            convertpolcaluvfits2miriad = False
                            logger.warning(
                                'Could not convert polarised calibrator dataset from UVFITS to MIRIAD format!')
                    else:
                        logger.warning('Polarised calibrator dataset not available!')
                else:
                    logger.info('Polarised calibrator dataset was already converted from UVFITS to MIRIAD format')
            else:
                logger.warning('Polarised calibrator dataset not specified. Cannot convert polarised calibrator!')
        else:
            logger.warning('Not converting polarised calibrator dataset!')
        # Convert the target beams
        if self.convert_target:
            if self.target != '':
                logger.info('Converting target beam datasets from UVFITS to MIRIAD format.')
                if self.convert_targetbeams == 'all':
                    datasets = glob.glob(
                        self.basedir + '[0-9][0-9]' + '/' + self.crosscalsubdir + '/' + self.target.rstrip(
                            'MS') + 'UVFITS')
                    logger.debug('Converting all available target beam datasets')
                else:
                    beams = self.convert_targetbeams.split(",")
                    datasets = [self.basedir + str(b).zfill(2) + '/' + self.crosscalsubdir + '/' + self.target.rstrip(
                        'MS') + 'UVFITS' for b in beams]
                    logger.debug('Converting all selected target beam datasets')
                for vis in datasets:
                    if not converttargetbeamsuvfits2miriad[int(vis.split('/')[-3])]:
                        if converttargetbeamsuvfitsavailable[int(vis.split('/')[-3])]:
                            subs_managefiles.director(self, 'ch',
                                                      self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir,
                                                      verbose=False)
                            fits = lib.miriad('fits')
                            fits.op = 'uvin'
                            fits.in_ = self.basedir + vis.split('/')[
                                -3] + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS'
                            fits.out = self.basedir + vis.split('/')[
                                -3] + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'mir'
                            fits.go()
                            if os.path.isdir(self.basedir + vis.split('/')[-3] + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'mir'):
                                converttargetbeamsuvfits2miriad[int(vis.split('/')[-3])] = True
                                logger.debug('Converted dataset of target beam ' + vis.split('/')[
                                    -3] + ' from UVFITS to MIRIAD format!')
                            else:
                                converttargetbeamsuvfits2miriad[int(vis.split('/')[-3])] = False
                                logger.warning('Could not convert dataset for target beam ' + vis.split('/')[
                                    -3] + ' from UVFITS to MIRIAD format!')
                        else:
                            logger.warning('Dataset for target beam ' + vis.split('/')[-3] + ' not available!')
                    else:
                        logger.info('Dataset for target beam ' + vis.split('/')[
                            -3] + ' was already converted from MS to UVFITS format')
            else:
                logger.warning('Target beam dataset(s) not specified. Cannot convert target beam datasets!')
        else:
            logger.warning('Not converting target beam dataset(s)!')

        # Save the derived parameters for the MS to UVFITS conversion to the parameter file

        subs_param.add_param(self, 'convert_fluxcal_UVFITS2MIRIAD', convertfluxcaluvfits2miriad)
        subs_param.add_param(self, 'convert_polcal_UVFITS2MIRIAD', convertpolcaluvfits2miriad)
        subs_param.add_param(self, 'convert_targetbeams_UVFITS2MIRIAD', converttargetbeamsuvfits2miriad)

        # Remove the UVFITS files if wanted #
        if self.convert_removeuvfits:
            logger.info('Removing all UVFITS files')
            subs_managefiles.director(self, 'rm',
                                      self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.fluxcal.rstrip(
                                          'MS') + 'UVFITS')
            subs_managefiles.director(self, 'rm',
                                      self.basedir + '00' + '/' + self.crosscalsubdir + '/' + self.polcal.rstrip(
                                          'MS') + 'UVFITS')
            for beam in range(nbeams):
                if os.path.isdir(self.basedir + str(beam).zfill(2) + '/' + self.crosscalsubdir):
                    subs_managefiles.director(self, 'rm', self.basedir + str(beam).zfill(
                        2) + '/' + self.crosscalsubdir + '/' + self.target.rstrip('MS') + 'UVFITS')
                else:
                    pass

    def summary(self):
        """
        Creates a general summary of the parameters in the parameter file generated during CONVERT. No detailed summary
        is available for CONVERT.

        returns (DataFrame): A python pandas dataframe object, which can be looked at with the style function in the
                             notebook
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
        dataset_indices = ['Flux calibrator (' + self.fluxcal[:-3] + ')',
                           'Polarised calibrator (' + self.polcal[:-3] + ')'] + dataset_beams

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

    def show(self, showall=False):
        lib.show(self, 'CONVERT', showall)

    def reset(self):
        """
        Function to reset the current step and remove all generated data. Be careful! Deletes all data generated in
        this step!
        """
        subs_setinit.setinitdirs(self)
        nbeams = 37

        logger.warning(' Deleting all converted data.')
        for beam in range(nbeams):
            if os.path.isdir(self.basedir + str(beam).zfill(2) + '/' + self.crosscalsubdir):
                subs_managefiles.director(self, 'rm',
                                          self.basedir + str(beam).zfill(2) + '/' + self.crosscalsubdir + '/*')
            else:
                pass
        logger.warning(' Deleting all parameter file entries for CONVERT module')
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
