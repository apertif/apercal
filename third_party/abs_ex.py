__author__ = "Filippo Maccagni"
__copyright__ = "ASTRON"
__email__ = "maccagni@astron.nl"

import ConfigParser
import logging

import astropy.io.fits as pyfits
import numpy as np
import os
import string
from astropy import wcs
from astropy.io import ascii
from matplotlib import gridspec
from matplotlib import pyplot as plt
from matplotlib import rc

from libs import lib
import setinit_an

C=2.99792458e5 #km/s
HI=1.420405751e9 #Hz

####################################################################################################


class abs_ex:
    '''
    
    Class for spectral studies (find continuum sources, extract spectra, analyze spectra)
    
    '''
    def __init__(self, file=None, **kwargs):
        '''
    
        Set logger for spectrum extraction
        Find config file
        If not specified by user load default.cfga
    
        '''
        
        self.logger = logging.getLogger('ABS')
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('abs_ex.pyc') + 'default.cfga'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        self.default = config # Save the loaded config file as defaults for later usage
        setinit_an.setinitdirs_abs(self)
        setinit_an.setinitfiles_abs(self)


    def go(self):
        '''

        Executes the whole spectrum extraction process as follows:
        1: set_dirs
        2: find_src_imsad
        3: load_src_csv
        4: spec_ex
        5: plot_spec

        '''
        self.logger.info("########## STARTING ABSORPTION analysis ##########")
        self.set_dirs()
        self.find_src_imsad()
        self.load_src_csv()
        self.spec_ex()
        self.plot_spec()
        self.logger.info("########## END ABSORPTION ANALYSIS ##########")

    def set_dirs(self):
        '''
     
        Sets directory strucure and filenames
        Creates directory abs/ in basedir+beam and subdirectories spec/ and plot/
     
        '''

        setinit_an.setinitdirs_abs(self)
        setinit_an.setinitfiles_abs(self)

        if os.path.exists(self.absdir) == False:
             os.makedirs(self.absdir)                 
        if os.path.exists(self.specdir) == False:
             os.makedirs(self.specdir)    
                
        if os.path.exists(self.plotdir) == False:
             os.makedirs(self.plotdir)

        print '\t*****\n\tAbs_Ex INPUTS\n\t*****\n'
        print '\tCube     \t: '+self.data_cube
        print '\tContinuum\t: '+self.cont_im

    #######################################################################
    ##### Modules to convert units                                    #####
    #######################################################################        

    def ra2deg(self,ra_hms):
        '''
            
            Converts RA from HH:MM:SS to degrees
        
        '''
        ra = string.split(ra_hms, ':')

        hh = float(ra[0])*15
        mm = (float(ra[1])/60)*15
        ss = (float(ra[2])/3600)*15

        return hh+mm+ss
        
    def dec2deg(self,dec_dms):
        '''
            
            Converts DEC from DD:MM:SS to degrees
        
        '''

        dec = string.split(dec_dms, ':')

        hh = abs(float(dec[0]))
        mm = float(dec[1])/60
        ss = float(dec[2])/3600

        return hh+mm+ss        
    
    def optical_depth(self, flux, peak_flux):
        '''

        Module called by spec_ex
        Finds optical depth of an absorption line
        IN
            flux: absorbed flux of the line in Jy
            peak_flux: flux of the continuum source in Jy

        '''
        tau_vec=-np.log(1.-flux/float(peak_flux))
        
        return tau_vec 

    #######################################################################
    ##### Modules for continuum sources                               #####
    #######################################################################      
    
    def find_src_imsad(self):
        '''
        
        Finds sources in continuum image above a threshold in flux specified by the user
        IN
            Continuum image: located in contdir
        IN cfga
            abs_ex_imsad_clip:   sets flux threshold in Jy
            abs_ex_imsad_region: xmin,xmax,ymin,ymax 
                                 defines regions where to search for sources
        OUT
            cont_src_imsad.txt:  table with found sources
                                 stored in contdir
        
        '''
        self.logger.info('### Find continuum sources ###')    

        os.chdir(self.contdir)
        if os.path.exists(self.cont_im_mir) == False: 
        
            fits = lib.miriad('fits')
            fits.op = 'xyin'
            fits.in_ = self.cont_im
            fits.out = self.cont_im_mir
            fits.go(rmfiles=True)

        if os.path.exists(self.cont_im) == False: 
        
            fits = lib.miriad('fits')
            fits.op = 'xyout'
            fits.in_ = self.cont_im_mir
            fits.out = self.cont_im
            fits.go(rmfiles=True)
      
        
        imsad = lib.miriad('imsad')
        imsad.in_ = self.cont_im_mir
        imsad.out = self.src_imsad_out
        imsad.clip = self.abs_ex_imsad_clip
        #imsad.region = 'boxes\('+self.abs_ex_imsad_region+'\)'
        imsad.options = self.abs_ex_imsad_options

        imsad.go(rmfiles=True)
        
        
        #modify output of imsad for module load_src_csv
        src_list = open(self.src_imsad_out,'r')
        lines = src_list.readlines()
        len_lines = len(lines)
        
        ra_tmp = []
        dec_tmp = []
        peak_tmp = []        
        
        for i in xrange (0,len_lines):
            lines[i] = lines[i].strip()
            tmp = lines[i].split(' ')
            ra_tmp.append(str(tmp[3]))
            dec_tmp.append(str(tmp[4]))
            peak_tmp.append(str(tmp[6]))
    
        ra_tmp = np.array(ra_tmp)
        dec_tmp = np.array(dec_tmp)
        peak_tmp = np.array(peak_tmp)
       
        #ID
        ids = np.array(np.arange(1,len_lines+1,1),dtype=str)
        
        #J2000
        #convert ra
        ra_vec = []
        for i in xrange (0, len_lines):
            line = ra_tmp[i].split(':')
            last_dig = int(round(float(line[2]),0))
            if last_dig < 10:
                last_dig = '0'+str(last_dig)
            ra_vec.append(line[0]+line[1]+str(last_dig))
        
        #convert dec 
        dec_vec = []
        dec_coord = []
        for i in xrange (0, len_lines):
            line = dec_tmp[i].split(':')
            last_dig = int(round(float(line[2]),0))
            first_dig = line[0].split('+')
            dec_vec.append(first_dig[2]+line[1]+str(last_dig))
            dec_coord.append('+'+first_dig[2]+':'+line[1]+':'+str(last_dig))        

        J2000_tmp = np.array([ a+'+'+b for a,b in zip(ra_vec,dec_vec)])
        dec_coord = np.array(dec_coord)
       
        ### Find pixels of sources in continuum image
        #open continuum image
        hdulist = pyfits.open(self.cont_im)  # read input
        # read data and header
        #what follows works for wcs, but can be written better
        prihdr = hdulist[0].header   
        if prihdr['NAXIS'] == 4:
            del prihdr['CTYPE4']
            del prihdr['CDELT4']    
            del prihdr['CRVAL4']
            del prihdr['CRPIX4']
        del prihdr['CTYPE3']
        del prihdr['CDELT3']
        del prihdr['CRVAL3']
        del prihdr['CRPIX3'] 
        del prihdr['NAXIS3']
        del prihdr['NAXIS']
        prihdr['NAXIS']=2
        #load wcs system
        w=wcs.WCS(prihdr)    

        self.pixels_cont=np.zeros([ra_tmp.shape[0],2])
        ra_list_tmp = np.zeros([ra_tmp.shape[0]])
        for i in xrange (0,ra_tmp.shape[0]):
            
            ra_deg_tmp = self.ra2deg(ra_tmp[i])
            dec_deg_tmp = self.dec2deg(dec_coord[i])
            
            px,py=w.wcs_world2pix(ra_deg_tmp,dec_deg_tmp,0)
            self.pixels_cont[i,0]= str(round(px,0))
            self.pixels_cont[i,1]= str(round(py,0))        
        
        #make csv file with ID, J2000, Ra, Dec, Pix_y, Pix_y, Peak[Jy] 
        tot = np.column_stack((ids,J2000_tmp,ra_tmp,dec_coord,
                               self.pixels_cont[:,0],self.pixels_cont[:,1],peak_tmp))

        self.logger.info('# Continuum sources found. #')    


        self.write_src_csv(tot)  
        
        self.logger.info('### Continuum sources found ###')    

        
        return 0    
    
    def load_src_csv(self):
        '''

        Loads .csv table, output of find_src_imsad
        Coordinates and flux of each source are stored in memory.
        
        '''
        os.chdir(self.contdir)
        
        if os.path.exists(self.src_list_csv):
            # open file
            src_list_vec = ascii.read(self.src_list_csv)
            self.src_id= np.array(src_list_vec['ID'],dtype=str)
            self.J2000_name = np.array(src_list_vec['J2000'],dtype=str)
            self.ra = np.array(src_list_vec['ra'],dtype=str)
            self.dec = np.array(src_list_vec['dec'],dtype=str)
            self.peak_flux = np.array(src_list_vec['peak'],dtype=float)
            
            #if redshift of sources are known
            if len(src_list_vec.dtype.names) > 7:
                self.z = np.array(src_list_vec['z'],dtype=float)
                if self.abs_ex_plot_redsrc == True:
                    self.vsys = C*self.z
                    self.fsys = HI/(1+self.z)
        else:             
            self.logger.warning('### File of continuum sources not found! Run source finder first! ###')    

        if self.abs_ex_convert_radec == True:
            #convert hms,dms to degrees
            self.ra_deg = np.zeros([self.ra.size])
            self.dec_deg = np.zeros([self.dec.size])
            for i in xrange (0,self.ra.size):
                self.ra_deg[i] = self.ra2deg(self.ra[i])
                self.dec_deg[i] = self.dec2deg(self.dec[i])
        return 0

    def write_src_csv(self,tot):
        '''
        
        Module called by find_src_imsad
        Writes output of Miriad imsad in .csv file
        The table has the following columns

        Obs_ID, Beam, Source_ID, J2000, Ra, Dec, Pix_x(continuum), Pix_y(continuum), Flux_peak[Jy/beam]
        
        '''

        # write the spectrum on file
        out_file = self.src_list_csv
        f = open(out_file, 'w')
        f.write('ID,J2000,ra,dec,Pix_x,Pix_y,peak\n')
        np.savetxt(f, tot, delimiter=",", fmt="%s")
        f.close()
        
        self.logger.info('# List of continuum sources saved on file. #')    
    
        return 0

    def coord_to_pix(self):
        '''
        
        Module called by spec_ex
        Converts ra,dec of sources found loaded by load_src_csv
        into pixel coordinates of the datacube
        
        '''

        #I load the WCS coordinate system:
        #open file
        hdulist = pyfits.open(self.data_cube)  # read input
        
        # read data and header
        #what follows works for wcs, but can be written better
        prihdr = hdulist[0].header
        if prihdr['NAXIS'] == 4:
            del prihdr['CTYPE4']
            del prihdr['CDELT4']    
            del prihdr['CRVAL4']
            del prihdr['CRPIX4']
        del prihdr['CTYPE3']
        del prihdr['CDELT3']
        del prihdr['CRVAL3']
        del prihdr['CRPIX3'] 
        del prihdr['NAXIS3']
        del prihdr['NAXIS']
        prihdr['NAXIS']=2
        w=wcs.WCS(prihdr)    

        
        self.pixels=np.zeros([self.ra_deg.size,2])
        for i in xrange (0,self.ra_deg.size):
            px,py=w.wcs_world2pix(self.ra_deg[i],self.dec_deg[i],0)
            self.pixels[i][0]= round(px,0)
            self.pixels[i][1]= round(py,0)
                    
        return 0

    #######################################################################
    ##### Save spectra                                                #####
    #######################################################################      
    
    def write_spec_csv(self,tot,out_spec):
        '''

        Module called by spec_ex
        Writes extracted spectra in .csv format. 
            Spectra are in flux and optical depth (tau).
            Noise is measured in the datacube for each channel, away from the radio source 
        
        Spectra have the following columns[units]

            frequency[Hz], velocity[km/s], flux[Jy/beam], rms_flux[Jy/beam], tau,  rms_tau
        
        '''

        out_spec = out_spec+'_spec.txt'
        f = open(out_spec, 'w')
        f.write('freq[Hz],vel[km/s],flux[Jy/beam],noise[Jy/beam],tau,tau_noise\n')
        np.savetxt(f, tot, delimiter=",", fmt="%s")
        f.close()
        
        self.logger.info('# Spectrum of source saved on file. #')

        return 0

    def write_spec_fitstab(self,tot,out_spec):
        '''

        Module called by spec_ex
        Writes extracted spectra in .fits format. 
            Spectra are in flux and optical depth (tau).
            Noise is measured in the datacube for each channel, away from the radio source 
        
        Spectra have the following columns[units]

            frequency[Hz] velocity[km/s] flux[Jy/beam] rms_flux[Jy/beam] tau  rms_tau
        
        '''


        out_spec = out_spec+'_spec.fits'

        c1 = pyfits.Column(name='frequency', format='D', unit='Hz', array=tot[:,0])
        c2 = pyfits.Column(name='velocity', format='D', unit='km/s ', array=tot[:,1])
        c3 = pyfits.Column(name='flux', format='D', unit = 'Jy/beam', array=tot[:,2])
        c4 = pyfits.Column(name='rms_flux', format='D', unit = 'Jy/beam', array=tot[:,3])
        c5 = pyfits.Column(name='tau', format='D', array=tot[:,4])        
        c6 = pyfits.Column(name='rms_tau', format='D', array=tot[:,5])        
        
        fits_table = pyfits.BinTableHDU.from_columns([c1, c2, c3, c4, c5, c6])    
        
        fits_table.writeto(out_spec, overwrite = True)
        
        return 0  

    #######################################################################
    ##### Plot spectra                                                #####
    ####################################################################### 
    
    def plot_spec(self):
        '''
        
        Plots spectra of all radio sources found by find_src_imsad 
        saved in basedir/beam/abs/spec.
        Plots are stored in basedir/beam/abs/plot
        
        IN
            Spectra extracted by spec_ex
        
        IN cfga
            abs_ex_plot_xaxis= ' '      #: X-axis units ['velocity','frequency'] 
            abs_ex_plot_yaxis= ' '      #: Y axis units ['flux','optical depth']
            abs_ex_plot_redsrc= True    #: plots line at redshift of source in spectrum
                                           redshift must be stored in table of load_src_csv
            abs_ex_plot_title= True     #: plot title: J2000 name of radio source
            abs_ex_plot_format= ' '     #: format of plot ['.pdf','.jpeg','.png']
        
        OUT
            For each source outputs have the following name:
            J2000_xaxis-unit_yaxis-unit.plot_format = J220919.87+180920.17_vel_flux.pdf

        '''

        os.chdir(self.specdir)
        
        params = {
                  'text.usetex': True,
                  'text.latex.unicode': True
                   }
        rc('font', **{'family': 'serif', 'serif': ['serif']})        
        plt.rcParams.update(params)
        
        for i in xrange(0,len(np.atleast_1d(self.src_id))):
            
            #load data and labels 
            spec_name = self.specdir+self.src_id[i]+'_'+self.J2000_name[i]
            if os.path.isfile(spec_name+'_spec.fits') or os.path.isfile(spec_name+'_spec.csv'):
            
                # Set plot specs
                font_size = 16            
                plt.ioff()
                fig = plt.figure(figsize =(8,6))
                fig.subplots_adjust(hspace=0.0)
                gs = gridspec.GridSpec(1, 1)
                plt.rc('xtick', labelsize=font_size-2)
                plt.rc('ytick', labelsize=font_size-2) 

                # Initialize subplots
                ax1 = fig.add_subplot(gs[0])
                ax1.set_xlabel('')
                ax1.set_ylabel('') 

                if os.path.isfile(spec_name+'_spec.fits'):           

                    t = pyfits.open(spec_name+'_spec.fits')
                    spec_vec = t[1].data
                    cols = t[1].columns

                    if (self.abs_ex_plot_xaxis =='frequency'
                        or self.abs_ex_plot_xaxis =='freq'
                        or self.abs_ex_plot_xaxis =='fr'):

                        xname='fr'
                        x_data = np.array(spec_vec['frequency'],dtype=float)

                        #convert Hz to GHz
                        if cols['frequency'].unit == 'Hz':
                            x_data /= 1e9
                            if self.abs_ex_plot_redsrc == True:
                                self.fsys[i] /=1e9
                        #x_data = np.arange(1,len(x_data)+1,1)

                        ax1.set_xlabel(r'Frequency [GHz]', fontsize=font_size)

                    elif (self.abs_ex_plot_xaxis == 'velocity'
                          or self.abs_ex_plot_xaxis == 'vel'
                          or self.abs_ex_plot_xaxis == 'v'):

                        xname='vel'
                        x_data = np.array(spec_vec['velocity'],dtype=float) 
                        ax1.set_xlabel(r'$cz\,[\mathrm{km}\,\mathrm{s}^{-1}]$', fontsize=font_size)

                    if (self.abs_ex_plot_yaxis == 'flux' 
                        or self.abs_ex_plot_yaxis == 'fl'
                        or self.abs_ex_plot_yaxis == 'f'):
                        yname= 'fl'
                        y_data = np. array(spec_vec['flux'],dtype=float)
                        y_sigma  = self.abs_los_rms[i]
                        #convert Jy to mJy
                        if cols['flux'].unit == 'Jy/beam':
                            y_data *= 1e3  
                            y_sigma *= 1e3

                        ylabh = ax1.set_ylabel(r'S\,$[\mathrm{mJy}\,\mathrm{beam}^{-1}]$', fontsize=font_size)

                    if (self.abs_ex_plot_yaxis == 'optical depth'
                        or self.abs_ex_plot_yaxis == 'opt'
                        or self.abs_ex_plot_yaxis == 'tau'):

                        yname = 'tau'
                        y_data = np. array(spec_vec['tau'],dtype=float)
                        y_sigma = self.tau_los_rms[i]
                        ylabh = ax1.set_ylabel(r'$\tau$', fontsize=font_size+2)                


                elif os.path.isfile(spec_name+'_spec.csv'): 

                    spec_vec = np.genfromtxt(spec_name+'_spec.csv', delimiter=',', names=True, dtype=None)

                    # Load axis and labels
                    if self.abs_ex_plot_xaxis =='frequency':
                        x_data = np.array(spec_vec['freqHz'],dtype=float)/1e9
                        ax1.set_xlabel(r'Frequency [GHz]', fontsize=font_size)

                    elif self.abs_ex_plot_xaxis == 'velocity':

                        x_data = np.array(spec_vec['velkms'],dtype=float)
                        ax1.set_xlabel(r'$cz\,(\mathrm{km}\,\mathrm{s}^{-1})$', fontsize=font_size)

                    if self.abs_ex_plot_yaxis == 'flux':

                        y_data = np. array(spec_vec['fluxJybeam'],dtype=float)*1e3
                        y_sigma = self.abs_los_rms[i]*1e3

                        ylabh = ax1.set_ylabel(r'S\,$[\mathrm{mJy}\,\mathrm{beam}^{-1}]$', fontsize=font_size)

                    if self.abs_ex_plot_yaxis == 'optical depth':

                        y_data = np. array(spec_vec['tau'],dtype=float)
                        y_sigma = self.tau_los_rms[i]

                        ylabh = ax1.set_ylabel(r'$\tau$', fontsize=font_size+2)

                ylabh.set_verticalalignment('center')

                # Calculate axis limits and aspect ratio
                x_min = np.min(x_data)
                x_max = np.max(x_data)
                y1_array = y_data[np.where((x_data>x_min) & (x_data<x_max))]
                y1_min = np.min(y1_array)*1.1
                y1_max = np.max(y1_array)*1.1

                # Set axis limits
                ax1.set_xlim(x_min, x_max)
                ax1.set_ylim(y1_min, y1_max)
                ax1.xaxis.labelpad = 6
                ax1.yaxis.labelpad = 10

                # Plot spectra 
#                if self.abs_ex_plot_linestyle == 'step':
                    #ax1.plot(x_data, y_data, color='black', linestyle='-')

                ax1.step(x_data, y_data, where='mid', color='black', linestyle='-')
                

                # Plot noise
                ax1.fill_between(x_data, -y_sigma, y_sigma, facecolor='grey', alpha=0.5)

                #add vertical line at redshift of source
                if self.abs_ex_plot_redsrc == True:
                    if xname == 'fr':
                        ax1.axvline(self.fsys[i],color='k',linestyle=':')
                    elif xname == 'vel':
                        ax1.axvline(self.vsys[i],color='k',linestyle=':')


                ax1.axhline(color='k', linestyle=':', zorder=0)

                # Add title        
                if self.abs_ex_plot_title == True:
                    ax1.set_title('%s' % (self.J2000_name[i]), fontsize=font_size+2) 
                ax1.axes.titlepad = 8

                # Add minor tick marks
                ax1.minorticks_on()

                # Save figure to file
                plt.savefig(self.plotdir+self.J2000_name[i]+'_'+xname+'_'+yname+self.abs_ex_plot_format,
                            overwrite = True)
                self.logger.info('# Plotted spectrum of source ' +self.src_id[i]+' '+self.J2000_name[i]+'. #')
            else:
                self.logger.warning('# Missing spectrum of source ' +self.src_id[i]+' '+self.J2000_name[i]+'. #')
                pass
    
    #######################################################################
    ##### Extract spectra                                             #####
    #######################################################################     
        
    def spec_ex(self):
        '''
        
        Extract spectrum at the coordinates of each source found by find_src_imsad
        IN
        Arrays stored in memory by load_src_csv
        IN cfga
        abs_ex_spec_format: .csv or .fits
        OUT
        Spectrum in .csv or .fits file format stored in abs/spec/ folder
        New line in abs_table.txt. Each line has the following information:
        
        Obs_ID, Beam, Source_ID, Ra, Dec, Peak Flux [Jy], r.m.s. spectrum
        
        '''
        if self.abs_ex_spec_ex == True:

            self.logger.info('### Extract spectra from the position of the peak of each continuum source ###')
            os.chdir(self.linedir)
            print os.getcwd()
            if os.path.exists(self.data_cube) == False:     
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = self.data_cube_mir
                fits.out = self.data_cube
                fits.go(rmfiles=True)
            #open file
            hdulist = pyfits.open(self.data_cube)  # read input
            # read data and header
            scidata = hdulist[0].data
            # reduce dimensions of the input cube if it his 4-dim
            sci = np.squeeze(scidata)
            prihdr = hdulist[0].header

            if (self.abs_ex_cube_zunit == 'frequency'
                or self.abs_ex_cube_zunit =='freq'
                or self.abs_ex_cube_zunit =='fr'):
                
                #convert frequencies in velocities
                freq = (np.linspace(1, sci.shape[0], sci.shape[0]) - prihdr['CRPIX3']) * prihdr['CDELT3'] + prihdr['CRVAL3']
                v = C * ((HI - freq) / freq)
                freq0 = prihdr['CRVAL3']
                freq_del = prihdr['CDELT3']
            
            elif (self.abs_ex_cube_zunit == 'velocity'
                or self.abs_ex_cube_zunit =='vel'
                or self.abs_ex_cube_zunit =='v'):
                
                v = (np.linspace(1, sci.shape[0], sci.shape[0]) - prihdr['CRPIX3']) * prihdr['CDELT3'] + prihdr['CRVAL3']
                v /= 1e3
                freq = (C*HI) /  (v + C)
                freq0 = (C*HI) /  (prihdr['CRVAL3']/1e3 + C)
                freq_del = (freq0 - freq[-1] )/ len(freq)
            
            #v_wrt_sys.append( C * ((HI - v_sys[j]) )
            #find pixels where to extract the spectra
            self.coord_to_pix()
            
            # Load the list of coordinates in pixels
            self.abs_mean_rms = np.zeros(self.pixels.shape[0])
            self.abs_los_rms = np.zeros(self.pixels.shape[0])
            self.tau_los_rms = np.zeros(self.pixels.shape[0])
            
            for i in xrange(0,self.pixels.shape[0]):

                # extract spectrum from each line of sight
                flux = np.zeros(freq.shape[0])
                madfm = np.zeros(freq.shape[0])
                pix_x_or = int(self.pixels[i][0])
                pix_y_or = int(self.pixels[i][1])
                               
                if (0 < pix_x_or < prihdr['NAXIS1'] and
                    0 < pix_y_or < prihdr['NAXIS2']): 
                    
                
                    for j in xrange(0, prihdr['NAXIS3']):
                        
                        #correct for chromatic aberration
                        if self.abs_ex_chrom_aber == True:
                            #depending if the cube is in velocity or frequency ?
                            if freq_del <=0.:
                                scale = (freq0 + j*freq_del) / freq0
                            elif freq_del >=0 :
                                scale = (freq0 - j*freq_del) / freq0
                                
                            pix_x = (pix_x_or - prihdr['CRPIX1']) * scale + prihdr['CRPIX1']
                            pix_y = (pix_y_or - prihdr['CRPIX2']) * scale + prihdr['CRPIX2']
                            pix_x = int(round(pix_x,0))
                            pix_y = int(round(pix_y,0))
                        else:
                            pix_x = pix_x_or
                            pix_y = pix_y_or
                        if  (0 < pix_x < prihdr['NAXIS1'] and
                             0 < pix_y < prihdr['NAXIS2']): 
                           
                            flux[j] = sci[j, pix_y, pix_x]
                        else:
                            flux[j] = 0.0
                        
                        # determine the noise of the spectrum [Whiting 2012 et al.] in each channel
                        # MADMF: median absolute deviation from the median
                        # extract a region were to determine the noise: A BOX around the l.o.s.
                        if (pix_x+10 < prihdr['NAXIS1'] and
                           pix_y+5 < prihdr['NAXIS2'] and pix_y - 5 > 0 ):
                                rms = np.nanmedian(sci[j, pix_x +5:pix_x + 10, pix_y - 5:pix_y + 5])
                                med2 = abs(sci[j, pix_x, pix_y] - rms)
                                madfm[j] = np.nanmedian(med2) / 0.6744888
                        else:
                            madfm[j] = 0.0

                        self.abs_mean_rms[i] = np.nanmean(madfm) 
                    
                    # measure noise in the spectrum outside of the line
                    end_spec = float(sci.shape[0])
                    end_spec_th = int(end_spec/3.)
                    end_spec = int(end_spec)

                    #print self.src_id[i], self.J2000_name[i], pix_x_or, pix_y_or, pix_x, pix_y
                    tau = self.optical_depth(flux,self.peak_flux[i])
                    tau_noise = self.optical_depth(madfm,self.peak_flux[i])
                    #convert flux in optical depth
                    self.abs_los_rms[i] = (np.std(flux[0:end_spec_th]) +
                                        np.std(flux[end_spec-end_spec_th:end_spec])) / 2.


                    self.tau_los_rms[i] = self.optical_depth(self.abs_los_rms[i],self.peak_flux[i])
                    
                    self.logger.info('# Extracted spectrum of source ' +self.src_id[i]+' '+self.J2000_name[i]+' #')

                     #write spectrum
                    tot = np.column_stack((freq, v, flux, madfm, tau, tau_noise)) 
                    out_spec = str(self.specdir+self.src_id[i]+'_'+self.J2000_name[i])
                
                    #save spectrum
                    if self.abs_ex_spec_format == 'csv':
                        self.write_spec_csv(tot,out_spec)
                    elif self.abs_ex_spec_format == 'fits':
                        self.write_spec_fitstab(tot,out_spec)
                    else:
                        self.write_spec_csv(tot,out_spec)
                        self.write_spec_fitstab(tot,out_spec)                   
                
                else :
                    self.logger.warning('# Source #'+self.src_id[i]+ ' lies outside the fov of the data cube #')
                    pass            
                

        
            self.logger.info('### End of spectrum extraction ###')

        return 0

    
    #######################################################################
    ##### Utilities                                                   #####
    #######################################################################
    
    def show(self, showall=False):
        '''
        
        show: Prints the current settings of the pipeline. 
              Only shows keywords, which are in the default analysis config file apercal/third_party/default.cfga
        
        showall=True : see all current settings of default.cfga instead of only the ones from the current class
        
        '''
        setinit_an.setinitdirs_abs(self)
        config = ConfigParser.ConfigParser()
        config.readfp(open(self.apercaldir + '/third_party/default.cfga'))
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
                if s == 'ABS':
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
        
        Resets the current step and remove all generated data. 
        Be careful! Deletes all data generated in this step!
        
        '''
        self.logger.warning('### Deleting all preflagged data. You might need to copy over the raw data to the raw subdirectory again. ###')
        self.director('ch', self.rawdir)
        self.director('rm', self.rawdir + '/*')
