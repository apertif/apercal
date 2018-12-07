import logging
from apercal.subs import setinit as subs_setinit
from apercal.libs import lib


logger = logging.getLogger(__name__)


class polarisation:
    """
    Final class to produce final data products (Deep continuum images, line cubes, and polairsation images and
    Faraday-cubes).
    """

    def __init__(self, file_=None, **kwargs):
        self.default = lib.load_config(self, file_)
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)

    def polarisation(self):
        """
        Produces individual images for Stokes Q,U, cleans them with the mask from Stokes I and combines them in a cube.
        Then uses RM-Synthesis to produce a Faraday cube and clean it.
        """
        subs_setinit.setinitdirs(self)
        subs_setinit.setdatasetnamestomiriad(self)
        logger.info(' Polarisation imaging is going to be implemented later')


    # def splitdata(self):
    #     """
    #     Applies calibrator corrections to data, splits the data into chunks in frequency and bins it to the given
    #     frequency resolution for the self-calibration
    #     """
    #     if self.splitdata:
    #         subs_setinit.setinitdirs(self)
    #         subs_setinit.setdatasetnamestomiriad(self)
    #         subs_managefiles.director(self, 'ch', self.selfcaldir)
    #         logger.info(' Splitting of target data into individual frequency chunks started')
    #         if os.path.isfile(self.selfcaldir + '/' + self.target):
    #             logger.info('Calibrator corrections already seem to have been applied #')
    #         else:
    #             logger.info('Applying calibrator solutions to target data before averaging #')
    #             uvaver = lib.miriad('uvaver')
    #             uvaver.vis = self.crosscaldir + '/' + self.target
    #             uvaver.out = self.selfcaldir + '/' + self.target
    #             uvaver.go()
    #             logger.info('Calibrator solutions to target data applied #')
    #         if self.selfcal_flagantenna != '':
    #             uvflag = lib.miriad('uvflag')
    #             uvflag.vis = self.selfcaldir + '/' + self.target
    #             uvflag.flagval = 'flag'
    #             uvflag.select = 'antenna(' + str(self.selfcal_flagantenna) + ')'
    #             uvflag.go()
    #         else:
    #             pass
    #         try:
    #             uv = aipy.miriad.UV(self.selfcaldir + '/' + self.target)
    #         except RuntimeError:
    #             raise ApercalException(' No data in your crosscal directory!')
    #
    #         try:
    #             nsubband = len(uv['nschan'])  # Number of subbands in data
    #         except TypeError:
    #             nsubband = 1  # Only one subband in data since exception was triggered
    #         logger.info('Found ' + str(nsubband) + ' subband(s) in target data #')
    #         counter = 0  # Counter for naming the chunks and directories
    #         for subband in range(nsubband):
    #             logger.info('Started splitting of subband ' + str(subband) + ' #')
    #             if nsubband == 1:
    #                 numchan = uv['nschan']
    #                 finc = np.fabs(uv['sdf'])
    #             else:
    #                 numchan = uv['nschan'][subband]  # Number of channels per subband
    #                 finc = np.fabs(uv['sdf'][subband])  # Frequency increment for each channel
    #             subband_bw = numchan * finc  # Bandwidth of one subband
    #             subband_chunks = round(subband_bw / self.selfcal_splitdata_chunkbandwidth)
    #             # Round to the closest power of 2 for frequency chunks with the same bandwidth over the frequency
    #             # range of a subband
    #             subband_chunks = int(np.power(2, np.ceil(np.log(subband_chunks) / np.log(2))))
    #             if subband_chunks == 0:
    #                 subband_chunks = 1
    #             chunkbandwidth = (numchan / subband_chunks) * finc
    #             logger.info('Adjusting chunk size to ' + str(
    #                 chunkbandwidth) + ' GHz for regular gridding of the data chunks over frequency #')
    #             for chunk in range(subband_chunks):
    #                 logger.info(
    #                     'Starting splitting of data chunk ' + str(chunk) + ' for subband ' + str(subband) + ' #')
    #                 binchan = round(
    #                     self.selfcal_splitdata_channelbandwidth / finc)  # Number of channels per frequency bin
    #                 chan_per_chunk = numchan / subband_chunks
    #                 if chan_per_chunk % binchan == 0:  # Check if the freqeuncy bin exactly fits
    #                     logger.info('Using frequency binning of ' + str(
    #                         self.selfcal_splitdata_channelbandwidth) + ' for all subbands #')
    #                 else:
    #                     # Increase the frequency bin to keep a regular grid for the chunks
    #                     while chan_per_chunk % binchan != 0:
    #                         binchan = binchan + 1
    #                     else:
    #                         # Check if the calculated bin is not larger than the subband channel number
    #                         if chan_per_chunk >= binchan:
    #                             pass
    #                         else:
    #                             # Set the frequency bin to the number of channels in the chunk of the subband
    #                             binchan = chan_per_chunk
    #                     logger.info('Increasing frequency bin of data chunk ' + str(
    #                         chunk) + ' to keep bandwidth of chunks equal over the whole bandwidth #')
    #                     logger.info('New frequency bin is ' + str(binchan * finc) + ' GHz #')
    #                 nchan = int(chan_per_chunk / binchan)  # Total number of output channels per chunk
    #                 start = 1 + chunk * chan_per_chunk
    #                 width = int(binchan)
    #                 step = int(width)
    #                 subs_managefiles.director(self, 'mk', self.selfcaldir + '/' + str(counter).zfill(2))
    #                 uvaver = lib.miriad('uvaver')
    #                 uvaver.vis = self.selfcaldir + '/' + self.target
    #                 uvaver.out = self.selfcaldir + '/' + str(counter).zfill(2) + '/' + str(counter).zfill(2) + '.mir'
    #                 uvaver.select = "'" + 'window(' + str(subband + 1) + ')' + "'"
    #                 uvaver.line = "'" + 'channel,' + str(nchan) + ',' + str(start) + ',' + str(width) + ',' + str(
    #                     step) + "'"
    #                 uvaver.go()
    #                 counter = counter + 1
    #                 logger.info('Splitting of data chunk ' + str(chunk) + ' for subband ' + str(subband) + ' done #')
    #             logger.info('Splitting of data for subband ' + str(subband) + ' done #')
    #         logger.info(' Splitting of target data into individual frequency chunks done')

    #
    # def create_parametric_mask(self, dataset, radius, cutoff, cat, outputdir):
    #     """
    #     Creates a parametric mask using a model from an input catalogue.
    #     dataset (string): The dataset to get the coordiantes for the model from.
    #     radius (float): The radius around the pointing centre of the input dataset to consider sources in in deg.
    #     cutoff (float): The apparent flux percentage to consider sources from 0.0 accounts for no sources, 1.0 for all
    #                     sources in the catalogue within the search radius of the target field.
    #     cat (string): The catalogue to search sources in. Possible options are 'NVSS', 'FIRST', and 'WENSS'.
    #     outputdir (string): The output directory to create the MIRIAD mask file in. The file is named mask.
    #     """
    #     lsm.write_mask(outputdir + '/mask.txt', lsm.lsm_mask(dataset, radius, cutoff, cat))
    #     mskfile = open(outputdir + '/mask.txt', 'r')
    #     object_ = mskfile.readline().rstrip('\n')
    #     spar = mskfile.readline()
    #     mskfile.close()
    #     imgen = lib.miriad('imgen')
    #     imgen.imsize = self.selfcal_image_imsize
    #     imgen.cell = self.selfcal_image_cellsize
    #     imgen.object = object_
    #     imgen.spar = spar
    #     imgen.out = outputdir + '/imgen'
    #     imgen.go()
    #     maths = lib.miriad('maths')
    #     maths.exp = '"<' + outputdir + '/imgen' + '>"'
    #     maths.mask = '"<' + outputdir + '/imgen>.gt.1e-6' + '"'
    #     maths.out = outputdir + '/mask'
    #     maths.go()
    #     subs_managefiles.director(self, 'rm', outputdir + '/imgen')
    #     subs_managefiles.director(self, 'rm', outputdir + '/mask.txt')