__author__ = "Filippo Maccagni"
__copyright__ = "ASTRON"
__email__ = "maccagni@astron.nl"

import ConfigParser
import logging

import astropy.io.fits as pyfits
import numpy as np
import os
import string
from astropy.io import ascii
from matplotlib import gridspec
from matplotlib import pyplot as plt

C=2.99792458e5 #km/s
HI=1.420405751e9 #Hz

####################################################################################################


class abstack:
    '''
    Class for absorption studies (find continuum sources, extract spectra, analyze spectra)
    '''
    def __init__(self, file=None, **kwargs):
        self.logger = logging.getLogger('STACK')
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            self.logger.info('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('abstack.pyc') + 'default.cfg'))
            self.logger.info('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        self.default = config # Save the loaded config file as defaults for later usage

        #outputs
        self.abstack_srctab=self.basedir+self.abstack_srctab

        self.outstack_dir = self.basedir+'stacking/'
        if os.path.exists(self.outstack_dir) == False:
            os.makedirs(self.outstack_dir)

        self.plotdir = self.outstack_dir+'plot/'    
        if os.path.exists(self.plotdir) == False:
             os.makedirs(self.plotdir)

        self.stackdir = self.outstack_dir+'spec/'    
        if os.path.exists(self.stackdir) == False:
             os.makedirs(self.stackdir)


              
    def go(self):
        '''
        Executes stacking analysis
        '''
        self.logger.info("########## STARTING STACKING of spectra ##########")
        self.load_table()
        self.logger.info("### sources to stack loaded")
        self.stack()
        self.logger.info("### stacking done")
        self.plot_stack()
        self.logger.info("### plotting stacked spectrum done")
        self.logger.info("########## END STACKING ##########")   


    #######################################################################
    ##### Functions to analyse spectra                                #####
    ####################################################################### 

    def red_to_hi(self,redshift):

        HI_sys=np.divide(HI,(1.+redshift))

        return HI_sys

    def freq_to_vel(self,frequency):

        v = C * ((HI - frequency) / frequency)

        return v

    def res_spec(self):

        for i in xrange (0, len(self.J2000)):

            infile = self.specdir[i]+self.J2000[i]+'_spec.fits'
        

            if os.path.exists(infile) == True:
                freq_spec,flux_spec,noise_spec = self.load_spectrum(infile,'freq')
                freq_spec = self.freq_to_vel(freq_spec)
                self.resolution = np.abs(freq_spec[0] - freq_spec[-1])/len(freq_spec)

            else: 
                continue         
            

        
        self.mean_resolution = np.mean(self.resolution)

        return 0

    #def predicted_noise_stack(self):



    #######################################################################
    ##### Functions to write & convert spectra                        #####
    #######################################################################

    def load_spectrum(self,infile,flag1):

        t = pyfits.open(infile)
        spec_vec = t[1].data
        cols = t[1].columns
        
        if flag1 == 'freq':
            freq_spec = np.array(spec_vec['frequency'],dtype=float)
            noise_spec = np.array(spec_vec['rms_tau'],dtype=float)
        elif flag1 == 'vel':
            freq_spec = np.array(spec_vec['velocity'],dtype=float)
            noise_spec = np.array(spec_vec['rms_tau'],dtype=float)

        flux_spec = np.array(spec_vec['tau'],dtype=float)
        
        return freq_spec,flux_spec,noise_spec

    def make_stack_vec(self):

        self.stack_freqs=np.arange(-self.abstack_velrange,self.abstack_velrange+self.mean_resolution,self.mean_resolution)
        self.len_stack_spec=len(self.stack_freqs)
        self.stack_spec = np.zeros([self.len_stack_spec,3])
        self.stack_spec[:,0] = self.stack_freqs

        return 0

    def write_stack(self,tot):
        
        self.out_stack_spec = self.stackdir+self.abstack_sample+'_stack.fits'


        c1 = pyfits.Column(name='velocity', format='D', unit='km/s', array=tot[:,0])
        c2 = pyfits.Column(name='tau', format='D', array=tot[:,1])        
        c3 = pyfits.Column(name='rms_tau', format='D', array=tot[:,2])        
        
        fits_table = pyfits.BinTableHDU.from_columns([c1, c2, c3])    
        
        fits_table.writeto(self.out_stack_spec, overwrite = True)
        
        return 0  
    
    def write_spec_fitstab(self,tot,out_spec):
        
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

    def from_txt_to_fits(self,infile):
        outfile = infile
        outfile = string.split(outfile,'_')
        infile = infile+'.txt'

        if os.path.exists(infile) == True:
            
            data = ascii.read(infile)
            freq= np.array(data['col1'],dtype=float)
            flux= np.array(data['col2'],dtype=float)
            flux_noise= np.array(data['col3'],dtype=float)   
            tau = np.array(data['col4'],dtype=float) 
            tau_noise= np.array(data['col5'],dtype=float) 

            #freq in Safari is in GHz
            freq *= 1e9
            vel = self.freq_to_vel(freq)

            tot = np.column_stack((freq, vel, flux, flux_noise, tau, tau_noise)) 
            
            #write_spec_fitstab(self,tot,out_spec)
            self.write_spec_fitstab(tot,outfile[0])

        else:
            infile_tmp = string.split(infile,'/')
            self.logger.info('### Spectrum of source '+infile_tmp[-1]+' not found. ###')
           

    #######################################################################
    ##### Functions to plot spectra                                   #####
    #######################################################################         
    
    def plot_stack(self):
        
        self.out_stack_spec = self.stackdir+self.abstack_sample+'_stack.fits'
        x_data,y_data,y_sigma = self.load_spectrum(self.out_stack_spec,'vel')
        
        params = {  'axes.linewidth'      :2,
                    'axes.labelsize'      :22,
                    'lines.linewidth'     :2,
                    'xtick.labelsize'     :20,
                    'ytick.labelsize'     :20,   
                    'xtick.major.size' : 5,
                    'xtick.major.width' : 2,
                    'xtick.minor.size' : 3,
                    'xtick.minor.width' : 1,
                    'ytick.major.size' : 5,
                    'ytick.major.width' : 2,
                    'ytick.minor.size' : 3,
                    'ytick.minor.width' : 1,     
                    'font.size'           : 22.0,
                    'text.usetex'         : True,
                    'text.latex.unicode'  : True,
                    'font.family'         :' serif',
                    'font.style'          : 'normal',
                    'font.weight'         : 'medium'
                   }
        plt.rcParams.update(params)
        
        line_size = 2

          # initialize figure
        fig = plt.figure(figsize =(12,8))
        fig.subplots_adjust(hspace=0.0)
        gs = gridspec.GridSpec(1, 1)
        plt.rc('xtick')
        plt.rc('ytick') 
        
        # Initialize subplots
        ax1 = fig.add_subplot(gs[0])

        ax1.set_xlabel(r'Velocity$\,[\mathrm{km}\,\mathrm{s}^{-1}]$', fontsize=params['font.size'])                
        
        # set y-label
        ylabh = ax1.set_ylabel(r'$\tau$', fontsize=params['font.size']+2)          
        ylabh.set_verticalalignment('center')

        # Calculate axis limits and aspect ratio
        x_min = np.min(x_data)
        x_max = np.max(x_data)
        y1_array = y_data[np.where((x_data>x_min) & (x_data<x_max))]
        y1_min = np.min(y1_array)*1.1
        y1_max = np.max(y1_array)*1.1

        # Set axis limits
        ax1.set_xlim(-1500, 1500)
        ax1.set_ylim(y1_min, y1_max)
        ax1.xaxis.labelpad = 6
        ax1.yaxis.labelpad = 10

        # Plot spectra 
        if self.abstack_plot_linestyle == 'step':
            ax1.step(x_data, y_data, where='mid', color='black', linestyle='-')
        else:
            ax1.plot(x_data, y_data, color='black', linestyle='-')

        # Plot noise
        ax1.fill_between(x_data, -y_sigma, y_sigma, facecolor='grey', alpha=0.5)

        #add vertical line at redshift of source
        ax1.axvline(color='k',linestyle=':', zorder = 0, lw=params['lines.linewidth']-1)
        ax1.axhline(color='k', linestyle=':', zorder=0, lw=params['lines.linewidth']-1)

        # Add title        
        if self.abstack_plot_title != 'None':
            ax1.set_title(self.abstack_plot_title, fontsize=params['font.size']+2) 
        ax1.axes.titlepad = 8

        # Add minor tick marks
        ax1.minorticks_on()

        # Save figure to file
        self.out_stack_spec_plot= self.plotdir+self.abstack_sample+'_stack'       
        plt.savefig(self.out_stack_spec_plot, overwrite = True)

        return 0

    #######################################################################
    ##### Stacking                                                    #####
    ####################################################################### 

    def load_table(self):

        t = pyfits.open(self.abstack_srctab)
        table = t[1].data
        cols = t[1].columns
        
        self.J2000 = np.array(table['J2000'],dtype=str)
        self.redshift = np.array(table['z'],dtype=float)
        
        # filter names according to abstack_filter_name (column name of input table)
        if self.abstack_filter_name != 'all':

            #define boolean arrays of filters
            filter_tf = np.zeros([len(self.J2000),len(self.abstack_filter_name)],dtype = bool)
            filter_vec = np.zeros([len(self.J2000),len(self.abstack_filter_name)])
            filter_last = np.zeros([len(self.J2000)],dtype = bool)
            
            for i in xrange (0, len(self.abstack_filter_name)):
                filter_vec[:,i] = np.array(table[self.abstack_filter_name[i]],dtype=float)

            for i in xrange (0, len(self.abstack_filter_name)):

                if self.abstack_filter_switch[i] == '>':            
                    index  = (filter_vec[:,i]>self.abstack_filter[i])
                    filter_tf[index,i] = True 
                if self.abstack_filter_switch[i] == '<':
                    index  = (filter_vec[:,i]<self.abstack_filter[i])
                    filter_tf[index,i] = True 
                if self.abstack_filter_switch[i] == '=':
                    index  = (filter_vec[:,i]==self.abstack_filter[i])
                    filter_tf[index,i] = True
                if self.abstack_filter_switch[i] == '!=':
                    filter_tf[index,i] = True   

            filter_last= np.all(filter_tf,axis=1)
   
        self.J2000 = np.array(self.J2000[np.where(filter_last==True)])
        self.redshift = np.array(self.redshift[np.where(filter_last==True)])
 
        #convert redshift to frequency
        self.HI_sys_spec = self.red_to_hi(self.redshift)

        # Create the directory & subdirectory names
        abstackdir_vec = np.array([self.abstack_dir]*len(self.J2000), dtype=object)

        self.absdir = abstackdir_vec +self.J2000+'/abs/'
        print self.absdir
        self.specdir = self.absdir+'spec/' 
        self.spec_names = self.specdir+self.J2000+'_spec'
        self.logger.info('### '+str(len(self.absdir))+' spectra will be stacked ###')  

        return 0   

    def stack(self):
        self.logger.info('### STACKING of '+str(self.abstack_sample)+' sample ###')

        # Define final array of stacked spectrum     
        self.res_spec()
        self.make_stack_vec()

        # Define temporary array of stacked spectrum and noise
        cen_index= self.len_stack_spec/2
        SummaSpect=np.zeros([self.len_stack_spec,2])

        self.noise_mean=np.zeros([len(self.J2000)])
        self.noise_mean[self.noise_mean == 0] = np.nan
        count_missing = 0
        for i in xrange(0,len(self.J2000)):

            #load spectrum
            in_spec= self.spec_names[i]+'.fits'
            if os.path.exists(in_spec) == True:
                freq_spec,flux_spec,noise_spec = self.load_spectrum(in_spec,'freq')
                # shift
                freq_spec[::-1]
                noise_spec[::-1]
                flux_spec[::-1]

                shift=np.abs(freq_spec - self.HI_sys_spec[i]).argmin() 
                shift= np.asscalar(np.array(shift))
              
                #shift spectrum to HI frequency
                left=cen_index-shift         
                right=left+len(freq_spec)

                #set final shifted array to stack
                stack_vec=np.zeros([self.len_stack_spec,3])
                stack_vec[left:right,1]=flux_spec
                stack_vec[left:right,2]=noise_spec

                #stack and weight spectrum for its noise
                for j in xrange (0,self.len_stack_spec):
                    if (stack_vec[j,1] != 0.0 and stack_vec[j,2] != 0.0):  
                        SummaSpect[j,0] += (stack_vec[j,1])/(np.power(stack_vec[j,2],2))
                        SummaSpect[j,1] +=  1./(np.power(stack_vec[j,2],2))        
                    else:
                        pass
                #determine mean noise spectra
                noise_spec[noise_spec == 0] = np.nan
                self.noise_mean[i] = np.nanmean(noise_spec)

            else: 
                in_spec_tmp=string.split(in_spec,'/')
                self.logger.info('### Spectrum of source '+in_spec_tmp[-1]+' not found. ###')
                count_missing+=1
                continue

        #Weight final stacked spectrum                             
        for i in xrange (0,self.len_stack_spec):              
            if (SummaSpect[i,1] != 0.): 
                self.stack_spec[i,1] = (SummaSpect[i,0])/SummaSpect[i,1]
                self.stack_spec[i,2] = (SummaSpect[i,1]/(SummaSpect[i,1])**2 )**0.5
            else:
                self.stack_spec[i,1] = 0.0
                self.stack_spec[i,2] = 0.0

        self.numstack = len(self.noise_mean)-count_missing
        self.pred_noise =  np.divide(np.nanmean(self.noise_mean),np.sqrt(self.numstack))
        
        self.logger.info('--> Stacked spectra = '+str(self.numstack))
        self.logger.info('--> Mean noise single spectra= '+str(np.nanmean(self.noise_mean)))
        self.logger.info('--> Expected noise STACKED spectrum  = '+str(self.pred_noise))

        self.write_stack(self.stack_spec)

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
                if s == 'STACK':
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



