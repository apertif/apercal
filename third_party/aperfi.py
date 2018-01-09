__author__ = "Filippo Maccagni, Tom Osterloo"
__copyright__ = "ASTRON"
__email__ = "maccagni@astron.nl"

import ConfigParser
import logging

import aipy
import aplpy
import astropy.io.fits as pyfits
import astropy.time as time
import matplotlib
import numpy as np
import os
import string
from matplotlib import gridspec
from matplotlib import pyplot as plt

from libs import lib

C=2.99792458e8 #m/s
HI=1.420405751e9 #Hz

####################################################################################################


class aperfi:
    '''
    Class for rfi studies.

    Parameters:
    -----------
    According to the parameters specified in an apercal-like parameter file

    Returns:
    --------
    In the folder /rfi/ in the directory of the uv-dataset 
    the following outputs are given:
    '''

    def __init__(self, file=None, **kwargs):
        '''
        Read parameter file
        '''

        self.logger = logging.getLogger('RFI')
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('aperfi.pyc') +'default_analysis.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        self.default = config # Save the loaded config file as defaults for later usage

        self.rfiinp = self.basedir + self.rawsubdir
        
        # Create the directory of oututs in basedir            
        self.rfidir = self.basedir +'rfi/'
        if os.path.exists(self.rfidir) == False:
             os.makedirs(self.rfidir)      

        # Create the directory of oututs in basedir            
        self.plotdir = self.rfidir +'plot/'
        if os.path.exists(self.plotdir) == False:
             os.makedirs(self.plotdir)       

        # Create the directory of oututs in basedir            
        self.analdir = self.rfidir +'analysis/'
        if os.path.exists(self.analdir) == False:
             os.makedirs(self.analdir)    
        


    def go(self):
        '''
        Executes the whole process automatically in the following order
        '''
        self.logger.info("########## STARTING RFI analysis ##########")
        self.write_baselines()
        self.logger.info("---- Baselines written -----")
        self.sort_ant()
        self.logger.info("---- Visbilities sorted in frequency vs baseline length -----")
        self.rfi_im()
        self.logger.info("---- RFI image done -----")
        self.plot_rfi_im()
        self.logger.info("---- Plot rfi frequency vs baseline done -----")      
        self.rfi_frequency()
        self.logger.info("---- RFI per frequency channel done -----")      
        self.plot_noise_frequency()
        self.aperfi_long_short = True
        self.plot_noise_frequency()
        self.logger.info("---- Plot factor of noise increase per frequency done -----")    
        self.aperfi_long_short = False
        self.aperfi_noise = 'flag'
        self.plot_noise_frequency()
        self.aperfi_noise = 'noise'
        self.plot_noise_frequency()        
        self.logger.info("---- Plot noise increase per frequency done -----")     
        self.write_log()
        self.logger.info("---- Table of summary edited ----- ")                   
        self.logger.info("########## END RFI ANALYSIS ##########")

    #######################################################################
    ##### Modules to convert units                                    #####
    #######################################################################        
        
    # HMS -> degrees
    def ra2deg(self,ra_hms):

        ra = string.split(ra_hms, ':')

        hh = float(ra[0])*15
        mm = (float(ra[1])/60)*15
        ss = (float(ra[2])/3600)*15

        return hh+mm+ss
    
    # DMS -> degrees
    
    def dec2deg(self,dec_dms):

        dec = string.split(dec_dms, ':')

        hh = abs(float(dec[0]))
        mm = float(dec[1])/60
        ss = float(dec[2])/3600

        return hh+mm+ss

 
    def deg2hms(self, ra):
        
        RA, rs = '', ''

        if str(ra)[0] == '-':
          rs, ra = '-', abs(ra)
        raH = int(ra/15.)
        raM = int(((ra/15)-raH)*60)
        raS = round(((((ra/15)-raH)*60)-raM)*60,2)
        
        RA = str(rs)+str(raH)+':'+str(raM)+':'+str(raS)

        return RA

    def deg2dms(self,dec):
        
        DEC, ds = '', ''

        if str(dec)[0] == '-':
          ds, dec = '-', abs(dec)
        deg = int(dec)
        decM = abs(int((dec-deg)*60))
        decS = round((abs((dec-deg)*60)-decM)*60,1)
  
        DEC = str(ds)+str(deg)+':'+str(decM)+':'+str(decS)

        return DEC


    #######################################################################
    ##### Modules to write outputs                                    #####
    ####################################################################### 
    def write_freq_base_time(self) :
        '''
        Writes a cube of visibilities ordered by frequency, baseline, time.
        Baselines are ordered by their length.
        '''

        if self.sdf < 0:
            self.datacube = self.datacube[:,:,::-1]
        #set fits file
        hdu = pyfits.PrimaryHDU(self.datacube)
        hdulist = pyfits.HDUList([hdu])
        header = hdulist[0].header

        #write header
        header['crpix1'] = 1
        header['cdelt1'] = np.abs(self.sdf*1000.)
        header['crval1'] = (self.aperfi_startfreq)
        header['ctype1'] = ('MHz')
        header['crpix2'] = 1
        header['crval2'] = 1
        header['cdelt2'] = 1
        header['ctype2'] =  ('Baseline')
        header['crpix3'] = 1
        header['crval3'] = self.in_time
        header['cdelt3'] = self.del_time        
        header['ctype3'] = ('Time')
        header['polar'] =  (self.aperfi_pol)


        #write file
        hdulist.writeto(self.out_cube,overwrite=True)
        hdulist.close()

        return 0
        
    def write_freq_base(self) :
        '''
        Writes an image.fits of visibilities ordered by frequency, baseline.
        Baselines are ordered by their length.
        '''
        #reverse frequencies if going from high-to-low         
        
        #set fits file
        hdu = pyfits.PrimaryHDU(self.rms)
        hdulist = pyfits.HDUList([hdu])
        header = hdulist[0].header

        #write header keywords               
        header['crpix1'] = 1
        header['cdelt1'] = np.abs(self.sdf*1000.)
        header['crval1'] = self.aperfi_startfreq
        header['ctype1'] = ('MHz')
        header['crpix2'] = 1
        header['crval2'] = 1
        header['cdelt2'] = 1
        header['ctype2'] =  ('Baseline')
        header['polar'] =  (self.aperfi_pol)
        header['bunit'] = ('% > '+str(self.aperfi_rmsclip)+'*rms')
        header['btype'] = ('intensity')

        #write file
        hdulist.writeto(self.out_image_freqbase,overwrite=True)
        hdulist.close()

        return 0     

    def write_baselines(self):
        '''
        Write baselines sorted by baseline length on .csv file
        Prints baselines and their length in m 
        Baselines are ordered by their length.
        '''
        
        #load uv file and sort baselines
        self.load_uvfile()

        # write the baselines on file
        f = open(self.out_baselines, 'w')
        line = '#Number\t Baseline\t Length[m]\n'
        f.write(line)
        for i in xrange(0,len(self.sortedants)):
            line = str(i+1)+'\t'+str(self.sortedants[i][0])+'\t' \
                        +str(round(self.distances[i],2))
            f.write(line+'\n')

        f.close()
        
        return 0
 

    def write_log(self):
        '''
        Appends table of RFI study with a new line and important info
        '''
        
        #load uv file and sort baselines
        self.load_uvfile()
        print self.out_table

        if os.path.exists(self.out_table):
            f = open(self.out_table, 'aw')
        else: 
            f = open(self.out_table, 'w')
            line = 'ID,RA,DEC,Date,StartTime,EndTime,StartFreq,EndFreq,Nants,MinBase,MaxBase\n'
            f.write(line)

        datein = string.split(self.aperfi_startime, ' ')
        dateout = string.split(self.aperfi_endtime, ' ')

        ra = self.deg2hms(self.uv['ra']*180./np.pi)
        dec = self.deg2dms(self.uv['dec']*180./np.pi)

        line1 = self.target+','+ra+','+dec+','+datein[0]+','+datein[1]+','+dateout[1]+','+str(self.aperfi_startfreq)+','
        line2 = str(self.aperfi_endfreq)+','+str(self.nant)+','+str(round(self.distances[0],2))+','+str(round(self.distances[-1],2))+'\n'
        line = line1+line2

        f.write(line)

        f.close


        
        return 0

    #######################################################################
    ##### Modules for antenna selection and sorting                   #####
    #######################################################################      

    def no_auto_corr(self,ant1,ant2) :
        '''
        Exclude autocorrelations and bad antennas.

        Parameters
        ----------
        aperfi_badant : True if there are bad antennas
        aperfi_bant : List of bad antenna numbers
        ant1 : number of first antenna of baseline
        ant2 : number of second antenna of baseline
        '''  

        # Exclude bad antenna set in config file
        if self.aperfi_badant == True:
            for i in xrange(0,len(self.aperfi_bant)):

                if (str(ant1) == str(self.aperfi_bant[i])) :
                    return False
                if (str(ant2) == str(self.aperfi_bant[i])) :
                    return False

        # Exclude autocorrelations
        if (ant1 == ant2) :

            return False

        return True 

    #-------------------------------------------------#
    
    def sort_baselines(self):
        '''
        Sort baselines by baseline lenght
        '''  

        # Load baselines and baseline lengths in meters
        ants = []
        self.distances =[]
        for i in range(0,self.nant-1) :
            for j in range(i+1,self.nant) :

                # Exclude anticorrelations
                if (self.no_auto_corr(i,j) ) :

                    # Sort baselines by length
                    #distances are in units of nanoseconds (as antpos)
                    dist = (self.antpos[i]-self.antpos[j])*(self.antpos[i]-self.antpos[j])
                    dist = dist + (self.antpos[i+self.nant]-self.antpos[j+self.nant])\
                                *(self.antpos[i+self.nant]-self.antpos[j+self.nant])
                    dist = dist + (self.antpos[i+self.nant*2]-self.antpos[j+self.nant*2])\
                                *(self.antpos[i+self.nant*2]-self.antpos[j+self.nant*2])
                    #dist = dist#/((self.aperfi_endfreq-self.tot_bw/2.)*1e6))
                    ants.append(([i,j],dist))
                    self.distances.append(dist)
        #Upload variables of baselines lenght and list_like baseline ([ant1, ant2], baseline_length)            
        self.distances =  np.sort(self.distances)
        self.sortedants = sorted(ants,key=lambda ants: ants[1])  

        return 0

    #-------------------------------------------------#
   
    def count_visibilities(self):

        self.uv.rewind()
        ant1=0
        ant2=1
        self.uvindex=0

        #self.uv.select('antennae', 0, 1, include=True)

        for preamble, data, flags in self.uv.all(raw=True):
            #select polarization of interest
               #if (self.pol == self.aperfi_pol)  :            
            #    #count number of visibilities per baseline
                    if ( (preamble[2][0] == ant1) and (preamble[2][1]==ant2)) :
                        self.uvindex+=1

        return 0
     
     #-------------------------------------------------#

    def predicted_noise_channel(self):
        '''
        Determines the predicted noise per frequency channel.
        '''   

        self.load_uvfile()
        coreta = 0.88

        #open file
        if self.aperfi_badant == True:
            self.nant -= len(self.aperfi_bant)
        
        # predicted noise
        self.tsys = self.uv['systemp']
        self.jyperk = self.uv['jyperk']

        self.bw = np.abs(self.sdf) * 1e9 #bandwidth resolution in Hz
        self.tsys = self.tsys*coreta
        self.noise_freq = self.tsys*self.jyperk /\
                        np.sqrt(2.*self.nant*(self.nant-1)/2.*np.abs(self.bw)*self.totdel_time.sec)

        self.noise_freq *= 1e3 #mJy/beam

        print 'Predicted noise per channel = '+str(round(self.noise_freq,3))+' mJy/beam'
         
        return 0         

    def average_dataset(self):

        os.chdir(self.rfiinp)

        uvaver = lib.miriad('uvaver')
        logger = logging.getLogger('RFI')
        logger.info('# Average in time #')
        uvaver.vis = self.target
        uvaver.line = self.aperfi_uvaver_line
        uvaver.stokes = self.aperfi_pol
        uvaver.out = self.uvfilename
        uvaver.go(rmfiles=True)

        return 0

    def copy_pol(self):

        uvcat = lib.miriad('uvcat')
        logger = logging.getLogger('RFI')
        logger.info('### copy right polarization ###')
        uvcat.vis = self.target
        uvcat.stokes = self.aperfi_pol
        uvcat.out = self.uvfilename
        uvcat.go(rmfiles=True)

        return 0

    #######################################################################
    ##### Modules for the analysis of the RFI                         #####
    ####################################################################### 
 
    def load_uvfile(self):
        '''
        Read miriad uv-dataset and save important header keywords in self.
        Sort baselines by baseline length using module: sort_baselines 
        '''  
        os.chdir(self.rfiinp)

        # Name the output datasets
        # !!!! to be changed according to the final products of previous pipeline
        if self.aperfi_uvaver == False:
            self.uvfilename = self.target+'_'+self.aperfi_pol
        if self.aperfi_uvaver == True:
            self.uvfilename = self.target+'_av_'+self.aperfi_pol
        self.out_cube = self.rfidir+self.uvfilename+'_sortedbaselines_cube_.fits'
        self.out_image_freqbase = self.rfidir+self.uvfilename+'_rfi_freqbase_.fits'
        self.out_plot_freqbase = self.plotdir+self.uvfilename+'_rfi_freqbase_'+self.aperfi_plot_format
        self.out_baselines = self.analdir+self.uvfilename+'_baselines.txt'
        self.out_rfi_analysis = self.analdir+self.uvfilename+'_rfitable.fits' 
        
        self.out_table = self.basedir+'../'+'rfi_archive.csv'
                         
        if (self.aperfi_uvaver == True and os.path.exists(self.uvfilename) == False):
                
            self.average_dataset()

        if (self.aperfi_uvaver == False and os.path.exists(self.uvfilename) == False):
            
            self.copy_pol()

        # Read uvfile and important parameters        
        self.uv=aipy.miriad.UV(self.uvfilename)
        self.antpos = self.uv['antpos']
        self.nchan = self.uv['nchan']
        self.nant = self.uv['nants']
        self.sfreq= self.uv['sfreq']
        self.sdf= self.uv['sdf']
        self.nspect = self.uv['nspect']        
        self.in_time = self.uv['time']        #julian date
        self.del_time = self.uv['inttime']    #s
        self.lst = self.uv['lst']
        self.base = self.uv['baseline']
       
        # count visibilities
        self.count_visibilities()
        
        # starting / ending frequencies
        self.aperfi_startfreq = (self.sfreq)*1000.
        self.tot_bw = (self.nchan/self.nspect)*self.sdf*1000. 
        self.aperfi_endfreq = self.aperfi_startfreq+self.tot_bw
        if self.aperfi_startfreq>self.aperfi_endfreq:
                tmp = self.aperfi_startfreq
                self.aperfi_startfreq = self.aperfi_endfreq
                self.aperfi_endfreq = tmp

        self.aperfi_startfreq_str = str(int(self.aperfi_startfreq))
        self.aperfi_endfreq_str = str(int(self.aperfi_endfreq))
        
        # starting / ending observing times and total observing time
        start_time = time.Time(self.in_time, format='jd')
        self.totdel_time = time.TimeDelta(self.del_time*self.uvindex, format='sec')
        end_time = start_time+self.totdel_time
        self.aperfi_startime = str(start_time.iso)
        self.aperfi_endtime = str(end_time.iso)
        self.aperfi_lst = time.Time(self.lst,format='jd')
        self.sort_baselines() 

        return 0

    
    #-------------------------------------------------#

    def sort_ant(self):
        '''
        Sorts antennas by baseline lenght
        Uploads lengths and baseline lenghts on self
        '''    

        #load header of uvdataset
        self.load_uvfile()
         
        # Define variables                                         
        blMatrix=np.zeros((self.nant,self.nant),dtype=int)
        baseline_counter=np.zeros((self.nant,self.nant),dtype=int)

        num_baselines  = len(self.sortedants)

        # Matrix for indices of baselines                  
        for i in range(0,len(self.sortedants)) :

            ant1 = self.sortedants[i][0][0]
            ant2 = self.sortedants[i][0][1]
            blMatrix[ant1,ant2] = i
            blMatrix[ant2,ant1] = i

        # Count number of visibilities per baseline
        #self.count_visibilities()

        # Set datacube 
        self.datacube=np.zeros([num_baselines,self.uvindex,self.nchan])   

        # Sort visibilities by baseline length            
        self.uv.rewind()

        for preamble, spec, flags in self.uv.all(raw=True) :
            #replace masked values with none
            spec[flags]=np.nan
            # Set the antenna
            ant1 = preamble[2][0]
            ant2 = preamble[2][1]

            # Exclude autocorrelations
            if (self.no_auto_corr(ant1,ant2) ) :            
                    # Determine which baseline the data belongs to
                    indice=blMatrix[ant1,ant2]
                    # Count how many visibilities per baseline
                    counter=baseline_counter[ant1,ant2]
                    # Put amplitude of visibility
                    # In the right place in the new array
                    self.datacube[indice,counter,:]=abs(spec)
                    # Update the number of visibility in that baseline
                    baseline_counter[ant1,ant2]+=1

        #put axes in the right places
        self.datacube = np.transpose(self.datacube, (1, 0, 2)) 



        # Write cube
        self.write_freq_base_time()

        return 0

    #-------------------------------------------------#

    def rfi_im(self):
        '''
        Reads cube of visibilities sorted by frequency, baseline lenght, time
        Creates imagea of % of visibilities with amplitude >aperfi_rmsclip*rms.
        Rms is the frequency interval of the   
        x-axis: frequency
        y-axis: baseline (sorted by baseline length)
        '''    

        #open file
        if os.path.exists(self.out_cube) == False:
            self.logger.error('### Cube of visibilities sorted by baseline length does not exist ###')    
            self.logger.error('### Run aperfi.sort_an() first ###')    

        else:    
            
            self.load_uvfile()

            hdulist = pyfits.open(self.out_cube)  # read input
            # read data and header
            datacube = hdulist[0].data
            prihdr = hdulist[0].header

            self.rms=np.zeros([datacube.shape[1],datacube.shape[2]])

            self.freqs = (np.linspace(1, datacube.shape[2], datacube.shape[2])\
                         - prihdr['CRPIX1'])*prihdr['CDELT1'] + prihdr['CRVAL1']

            if self.freqs[0]<self.freqs[-1]:
                chan_min= np.argmin(np.abs(self.freqs - self.aperfi_rfifree_min))
                chan_max = np.argmin(np.abs(self.freqs - self.aperfi_rfifree_max))
            else:
                chan_max= np.argmin(np.abs(self.freqs - self.aperfi_rfifree_min))
                chan_min = np.argmin(np.abs(self.freqs - self.aperfi_rfifree_max))            

            time_ax_len = int(datacube.shape[0])

            for i in xrange(0,datacube.shape[1]):

                tmp_rms = np.nanmedian(datacube[:, i, chan_min:chan_max])
                med2 = abs(datacube[:, i, chan_min:chan_max] - tmp_rms)
                madfm = np.ma.median(med2) / 0.6744888
                flag_lim = self.aperfi_rmsclip*madfm        

                for j in xrange(0,datacube.shape[2]):

                    tmpar = datacube[:,i,j]
                    mean = np.nanmean(tmpar)
                    tmpar=tmpar-mean
                    tmpar = abs(tmpar)
                    #change masked values to very high number
                    inds = np.where(np.isnan(tmpar))
                    tmpar[inds]=np.inf
                    tmpar.sort()
                    index_rms = np.argmin(np.abs(tmpar - flag_lim))
                    tmp_over = len(tmpar[index_rms:-1])+1
                    if tmp_over == 1 :
                        tmp_over = 0
                    self.rms[i,j] = 100.*tmp_over/time_ax_len
     

            # Write fits image
            self.write_freq_base()            

        return 0   

    #######################################################################
    ##### Modules for plotting the results                            #####
    ####################################################################### 
    
    def plot_rfi_im(self):
        '''
        Plots the .fits image output of rfi_im jpg format.
        '''        
        #check if image exists

        self.load_uvfile()

        if os.path.exists(self.out_image_freqbase) == False:
            self.logger.error('### Image of RFI sorted by frequency over baseline lenght does not exist ###')    
            self.logger.error('### Run aperfi.rfi_im() first ###')    
        else:        
            #plot image
            fig = aplpy.FITSFigure(self.out_image_freqbase,figsize=(12,8))

            #plot colorscale & colorbar
            fig.show_colorscale(aspect='auto', cmap='nipy_spectral_r',vmin=0,vmax=100)
            fig.show_colorbar()
            fig.colorbar.set_width(0.2)
            fig.colorbar.set_font(size=20, weight='medium', \
                                  stretch='normal', family='sans-serif', \
                                  style='normal', variant='normal')
            fig.colorbar.set_axis_label_font(size=20)
            fig.colorbar.set_axis_label_text(r'$\% > 5 \times$ r.m.s.')

            #set axis
            fig.axis_labels.set_font(size=20, weight='medium', \
                                     stretch='normal', family='sans-serif', \
                                     style='normal', variant='normal')
            fig.tick_labels.set_font(size=20, weight='medium', \
                                     stretch='normal', family='sans-serif', \
                                     style='normal', variant='normal') 
            titleplot = self.target+': '+self.aperfi_startime+' - '+self.aperfi_endtime
            #fig.set_title(titleplot, size=20)
            #ancillary plotting features 
            #fig.add_grid()
            #fig.grid.show()
            #fig.ticks.show()
            #fig.ticks.set_color('k')
            #fig.ticks.set_length(6)  # points
            #fig.ticks.set_linewidth(2)  # points
            #fig.ticks.set_minor_frequency(1)
            #fig.show_contour(levels=val, colors='white',ls=1)
            fig.savefig(self.out_plot_freqbase,format='jpg')
    
        return 0

    
    def rfi_frequency(self):
        '''
        Determines the % of visibilities with amplitude > aperfi_rmsclip*rms
        for each frequency channel.
        Rms computed as in rfi_im.
        Determines the factor for which the predicted noise per channel increases
        because of RFI.
        '''

        #open file
        if os.path.exists(self.out_image_freqbase) == False:
            self.logger.error('### Image of RFI sorted by frequency over baseline lenght does not exist ###')    
            self.logger.error('### Run aperfi.rfi_im() first ###')  
        else:    
            
            # read data and header
            hdulist = pyfits.open(self.out_image_freqbase)  # read input                
            datacube = hdulist[0].data    
            prihdr = hdulist[0].header

            #set array of frequencies
            self.freqs = (np.linspace(1, datacube.shape[1], datacube.shape[1])\
                         - prihdr['CRPIX1'])*prihdr['CDELT1'] + prihdr['CRVAL1']
            
            # set y-array
            rms_lin = np.zeros([datacube.shape[1]])    
            flag_lin = np.zeros([datacube.shape[1]])    
            rms_lin_long = np.zeros([datacube.shape[1]]) + np.sqrt(2.)          
            rms_lin_short = np.zeros([datacube.shape[1]]) + np.sqrt(2.)   
            flag_lin_long = np.zeros([datacube.shape[1]]) + 50.          
            flag_lin_short = np.zeros([datacube.shape[1]]) + 50.

            for i in xrange(0,datacube.shape[1]):
                
                flag_lin_tmp = np.divide(np.sum(datacube[:,i]),datacube.shape[0])
                flag_lin[i] = flag_lin_tmp

                shortbase=datacube[:int(datacube.shape[0]/2),i]
                longbase = datacube[int(datacube.shape[0]/2):,i]               
                
                rms_lin_tmp = 1.-np.divide(np.divide(np.sum(datacube[:,i]),datacube.shape[0]),100.)
                rms_lin[i] = np.divide(1.,np.sqrt(rms_lin_tmp))

                flag_lin_tmp = np.divide(np.sum(shortbase),len(shortbase))
                flag_lin_short[i] = flag_lin_tmp
                rms_lin_tmp_short = 1.-np.divide(np.divide(np.sum(shortbase),len(shortbase)),100.)
                rms_lin_short[i] *= np.divide(1.,np.sqrt(rms_lin_tmp_short))

                flag_lin_tmp = np.divide(np.sum(longbase),len(longbase))
                flag_lin_long[i] = flag_lin_tmp
                rms_lin_tmp_long = 1.-np.divide(np.divide(np.sum(longbase),len(longbase)),100.)
                rms_lin_long[i] *= np.divide(1.,np.sqrt(rms_lin_tmp_long))
        
            # save fits table        
            c1 = pyfits.Column(name='frequency', format='D', unit='MHz', array=self.freqs)
            c2 = pyfits.Column(name='flag', format='D', unit='-', array=flag_lin)
            c3 = pyfits.Column(name='noise_factor', format='D', unit = '-', array=rms_lin)
            c4 = pyfits.Column(name='flag_short', format='D', unit='-', array=flag_lin_short)
            c5 = pyfits.Column(name='noise_factor_short', format='D', unit = '-', array=rms_lin_short)
            c6 = pyfits.Column(name='flag_long', format='D', unit='-', array=flag_lin_long)
            c7 = pyfits.Column(name='noise_factor_long', format='D', array=rms_lin_long)        

            fits_table = pyfits.BinTableHDU.from_columns([c1, c2, c3, c4, c5, c6, c7])    
            
            fits_table.writeto(self.out_rfi_analysis, overwrite = True)
            
        return 0


    
    def plot_noise_frequency(self):
        '''
        Plots the % of visibilities with amplitude > aperfi_rmsclip*rms
        Input is the fits table saved by aperfi.write_rfi_frequency.
        '''
        self.load_uvfile()

        #open file
        if os.path.exists(self.out_rfi_analysis) == False:
            self.logger.error('### Table of RFI and flags of visibilities does not exist ###')    
            self.logger.error('### Run aperfi.rfi_frequency() first ###')  
        else:  


            t = pyfits.open(self.out_rfi_analysis)
            data_vec = t[1].data
            cols = t[1].columns
            
            freqs = np.array(data_vec['frequency'],dtype=float)
            flags = np.array(data_vec['flag'],dtype=float)
            noise_factor = np.array(data_vec['noise_factor'],dtype=float)
            noise_factor_long = np.array(data_vec['noise_factor_long'],dtype=float)
            flags_long = np.array(data_vec['flag_long'],dtype=float)
            noise_factor_short = np.array(data_vec['noise_factor_short'],dtype=float)
            flags_short = np.array(data_vec['flag_short'],dtype=float)

           
            if self.aperfi_noise == 'noise':
                self.predicted_noise_channel()
                noise_all = noise_factor*self.noise_freq
                noise_short = noise_factor_short*self.noise_freq
                noise_long = noise_factor_long*self.noise_freq
            if self.aperfi_noise == 'rfi':
                noise_all = noise_factor
                noise_short = noise_factor_short
                noise_long = noise_factor_long          
            if self.aperfi_noise == 'flag':
                noise_all = flags
                noise_long = flags_long
                noise_short = flags_short


            # initialize plotting parameters
            params = {'font.family'         :' serif',
                      'font.style'          : 'normal',
                      'font.weight'         : 'medium',
                      'font.size'           : 20.0,
                      'text.usetex': True,
                      'text.latex.unicode': True
                       }
            plt.rcParams.update(params)
            
            # initialize figure
            fig = plt.figure(figsize =(14,8))
            fig.subplots_adjust(hspace=0.0)
            gs = gridspec.GridSpec(1, 1)
            plt.rc('xtick', labelsize=20)

            # Initialize subplots
            ax1 = fig.add_subplot(gs[0])
            ax1.set_xlabel(r'Frequency [MHz]',fontsize=20)
            
            if self.aperfi_noise != 'flag':
                ax1.set_yscale('log', basey=10)
        
            #define title output
            out_plot = self.plotdir+self.uvfilename+'_freq_'+self.aperfi_pol
                     
            #plot
            label_all = 'All baselines' 
            label_long = 'Long baselines' 
            label_short = 'Short baselines' 

            if self.aperfi_long_short == True:
                ax1.step(freqs,noise_short, where= 'pre', color='red', linestyle='-',label=label_short)
                ax1.step(freqs,noise_long, where= 'pre', color='blue', linestyle='-',label=label_long)
                out_plot = out_plot+'_sl_'

            ax1.step(freqs,noise_all, where= 'pre', color='black', linestyle='-',label=label_all)

            titleplot = self.target+': '+self.aperfi_startime+' - '+self.aperfi_endtime
            #ax1.set_title(titleplot)
            
            # set axis, legend ticks

            ax1.set_xlim([np.min(freqs)-5,np.max(freqs)+5])
            xticks_num = np.linspace(int(self.aperfi_endfreq),int(self.aperfi_startfreq),10,dtype=int)
            ax1.set_xticks(xticks_num)

            if self.aperfi_noise == 'rfi':
                ax1.set_yticks([1,round(np.sqrt(2),2),2,3,5,10,50]) 
                ax1.set_ylabel(r'Factor of noise increase')
                ax1.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
                out_plot = out_plot+'_rfi'+self.aperfi_plot_format

            if self.aperfi_noise == 'noise':
                ax1.set_yticks([1,2,3,5,10,50]) 
                ax1.set_ylabel(r'Predicted noise [mJy beam$^{-1}$]')     
                out_plot = out_plot+'_noise'+self.aperfi_plot_format    
                ax1.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())

            if self.aperfi_noise == 'flag':
                ax1.set_ylabel(r'$\% >$ '+str(self.aperfi_rmsclip)+'*rms') 
                out_plot = out_plot+'_flag'+self.aperfi_plot_format
            
            legend = plt.legend()
            legend.get_frame().set_edgecolor('black')

            # Save figure to file
            plt.savefig(out_plot,overwrite = True)
                            
            return 0            

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
                if s == 'RFI':
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
        self.logger.warning('### Deleting all preflagged data. You might need to copy over the raw data to the raw subdirectory again. ###')
        self.director('ch', self.rawdir)
        self.director('rm', self.rawdir + '/*')  
        
        
