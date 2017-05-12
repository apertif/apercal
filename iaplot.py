__author__ = "Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "adebahr@astron.nl"

import lib
import os, sys
import ConfigParser
import random
import string
import math as m
import re
import datetime
import time
from matplotlib import pyplot as plt
import numpy as np
import matplotlib.cm as cm
import astropy.io.fits as pyfits
import glob
from matplotlib.widgets import Slider, Button

####################################################################################################

class iaplot:
    '''
    Interactive plotting class to plot gains and get statistics
    '''
    def __init__(self, file=None, **kwargs):
        config = ConfigParser.ConfigParser() # Initialise the config parser
        if file != None:
            config.readfp(open(file))
            print('### Configuration file ' + file + ' successfully read! ###')
        else:
            config.readfp(open(os.path.realpath(__file__).rstrip('calibrate.pyc') + 'default.cfg'))
            print('### No configuration file given or file not found! Using default values! ###')
        for s in config.sections():
            for o in config.items(s):
                setattr(self, o[0], eval(o[1]))
        self.default = config # Save the loaded config file as defaults for later usage

        # Create the directory names
        self.crosscaldir = self.basedir + self.crosscalsubdir
        self.selfcaldir = self.basedir + self.selfcalsubdir
        self.finaldir = self.basedir + self.finalsubdir

    ############################################################################
    ##### Functions to show and analyse calibration tables in the notebook #####
    ############################################################################

    def plot_gains(self, source='target', beam=None, step='selfcal', chunk='subplot', antenna='all', yaxis='phase'):
        '''
        Function to show gains in the notebook
        source (string): For step selfcal only target is possible and default.
        beam (string): The beam number to show the gains for. No effect up to now.
        step (string): The step of the pipeline to show the gains for. Default is 'selfcal'. Only this option is implemented up to now.
        chunk (int or string): The frequency chunk to show the gains for. Possible options are the number of a freqeucny chunk, 'all', and 'subplot'. Not two parameters with the 'all' keyword can be used at the same time.
        antenna (int or string): The antenna to show the gains for. Possible options are the number of the antenna, 'all', and 'subplot'. Not two parameters with the 'all' keyword can be used at the same time.
        yaxis(string): 'amp', 'phase', 'real', and 'imag' are possible. 'phase' is default.
        '''
        if all(param == 'all' for param in [chunk, antenna]): # Check if two of the parameters are 'all'
            print('### No two parameters can be all ###')
            sys.exit(1)
        elif all(param == 'subplot' for param in [chunk, antenna]): # Check if two of the parameters are 'subplot'
            print('### No two parameters can be subplot ###')
            sys.exit(1)
        else:
            pass
        self.manage_tempdir() # Check if the temporary directory exists and if not create it
        self.clean_tempdir() # Remove any temorary files from the temporary directory
        fig = plt.figure(figsize=(12, 10))
        if antenna == 'all' and type(chunk) == int:
            timearray, gainarray = self.get_gains(chunk, yaxis)
            colour = cm.viridis(np.linspace(0, 1, len(gainarray[0])))
            for ant in range(len(gainarray[0])):
                plt.scatter(timearray, gainarray[:, ant], color=colour[ant], marker='.', s=1, label='Antenna ' + str(ant))
            plt.xlabel('Time')
            plt.ylabel(yaxis.title())
            plt.legend(fontsize=8)
            plt.xlim(timearray[0],timearray[-1])
            plt.gcf().autofmt_xdate()
        elif antenna == 'all' and chunk == 'subplot':
            chunklist = glob.glob(self.selfcaldir + '/*/*.mir/gains')
            ax = fig.add_subplot(111)
            for n, chunk in enumerate(chunklist):
                timearray, gainarray = self.get_gains(n, yaxis)
                colour = cm.viridis(np.linspace(0, 1, len(gainarray[0])))
                ax_sub = fig.add_subplot(int(m.ceil(len(chunklist) / 3.0)), 3, n + 1)
                for ant in range(len(gainarray[0])):
                    ax_sub.scatter(timearray, gainarray[:, ant], color=colour[ant], marker='.', s=1, label='Antenna ' + str(ant))
                ax_sub.set_xlim(timearray[0], timearray[-1])
                ax_sub.legend(fontsize=6)
                ax_sub.set_title('Chunk ' + str(n))
                plt.setp(plt.xticks()[1], rotation=25, fontsize=6)
                plt.setp(plt.yticks()[1], fontsize=6)
            ax.spines['top'].set_color('none')  # Switch off the lines and labels from the big subplot
            ax.spines['bottom'].set_color('none')
            ax.spines['left'].set_color('none')
            ax.spines['right'].set_color('none')
            ax.tick_params(labelcolor='w', top='off', bottom='off', left='off', right='off')
            ax.set_xlabel('Time')
            ax.set_ylabel(yaxis.title())
        elif antenna == 'subplot' and type(chunk) == int:
            timearray, gainarray = self.get_gains(chunk, yaxis)
            colour = cm.viridis(np.linspace(0, 1, len(gainarray[0])))
            ax = fig.add_subplot(111)
            for ant in range(len(gainarray[0])):
                ax_sub = fig.add_subplot(int(m.ceil(len(gainarray[0])/3.0)),3,ant+1)
                ax_sub.scatter(timearray, gainarray[:, ant], color=colour[ant], marker='.', s=1, label='Antenna ' + str(ant))
                ax_sub.set_xlim(timearray[0], timearray[-1])
                ax_sub.legend(fontsize=6)
                ax_sub.set_title('Antenna ' + str(ant))
                plt.setp(plt.xticks()[1], rotation=25, fontsize=6)
                plt.setp(plt.yticks()[1], fontsize=6)
            ax.spines['top'].set_color('none') # Switch off the lines and labels from the big subplot
            ax.spines['bottom'].set_color('none')
            ax.spines['left'].set_color('none')
            ax.spines['right'].set_color('none')
            ax.tick_params(labelcolor='w', top='off', bottom='off', left='off', right='off')
            ax.set_xlabel('Time')
            ax.set_ylabel(yaxis.title())
        elif type(antenna) == int and type(chunk) == int:
            timearray, gainarray = self.get_gains(chunk, yaxis)
            colour = cm.viridis(np.linspace(0, 1, len(gainarray[0])))
            plt.scatter(timearray, gainarray[:, antenna], color=colour[antenna], marker='.', s=1, label='Antenna ' + str(antenna))
            plt.xlabel('Time')
            plt.ylabel(yaxis.title())
            plt.legend(fontsize=8)
            plt.xlim(timearray[0],timearray[-1])
            plt.gcf().autofmt_xdate()
        elif type(antenna) == int and chunk == 'subplot':
            chunklist = glob.glob(self.selfcaldir + '/*/*.mir/gains')
            ax = fig.add_subplot(111)
            for n, chunk in enumerate(chunklist):
                timearray, gainarray = self.get_gains(n, yaxis)
                colour = cm.viridis(np.linspace(0, 1, len(chunklist)))
                ax_sub = fig.add_subplot(int(m.ceil(len(chunklist) / 3.0)), 3, n + 1)
                ax_sub.scatter(timearray, gainarray[:, antenna], color=colour[n], marker='.', s=1, label='Chunk ' + str(n))
                ax_sub.set_xlim(timearray[0], timearray[-1])
                ax_sub.legend(fontsize=6)
                ax_sub.set_title('Chunk ' + str(n))
                plt.setp(plt.xticks()[1], rotation=25, fontsize=6)
                plt.setp(plt.yticks()[1], fontsize=6)
            ax.spines['top'].set_color('none')  # Switch off the lines and labels from the big subplot
            ax.spines['bottom'].set_color('none')
            ax.spines['left'].set_color('none')
            ax.spines['right'].set_color('none')
            ax.tick_params(labelcolor='w', top='off', bottom='off', left='off', right='off')
            ax.set_xlabel('Time')
            ax.set_ylabel(yaxis.title())
        elif type(antenna) == int and chunk == 'all':
            chunklist = glob.glob(self.selfcaldir + '/*/*.mir/gains')
            for n,chunk in enumerate(chunklist):
                timearray, gainarray = self.get_gains(n, yaxis)
                colour = cm.viridis(np.linspace(0, 1, len(chunklist)))
                plt.scatter(timearray, gainarray[:, antenna], color=colour[n], marker='.', s=1, label='Chunk ' + str(n))
                plt.xlabel('Time')
                plt.ylabel(yaxis.title())
                plt.legend(fontsize=8)
                plt.xlim(timearray[0], timearray[-1])
                plt.gcf().autofmt_xdate()
        elif antenna == 'subplot' and chunk == 'all':
            timearray, gainarray = self.get_gains(0, yaxis) # Load the gains from the first chunk to set some initial parameters
            chunklist = glob.glob(self.selfcaldir + '/*/*.mir/gains')
            colour = cm.viridis(np.linspace(0, 1, len(chunklist)))
            ax = fig.add_subplot(111)
            for ant in range(len(gainarray[0])):
                ax_sub = fig.add_subplot(int(m.ceil(len(gainarray[0]) / 3.0)), 3, ant + 1)
                for n, chunk in enumerate(chunklist):
                    timearray, gainarray = self.get_gains(n, yaxis)
                    ax_sub.scatter(timearray, gainarray[:, ant], color=colour[n], marker='.', s=1, label='Chunk ' + str(n))
                ax_sub.set_xlim(timearray[0], timearray[-1])
                ax_sub.legend(fontsize=6)
                ax_sub.set_title('Antenna ' + str(ant))
                plt.setp(plt.xticks()[1], rotation=25, fontsize=6)
                plt.setp(plt.yticks()[1], fontsize=6)
            ax.spines['top'].set_color('none')  # Switch off the lines and labels from the big subplot
            ax.spines['bottom'].set_color('none')
            ax.spines['left'].set_color('none')
            ax.spines['right'].set_color('none')
            ax.tick_params(labelcolor='w', top='off', bottom='off', left='off', right='off')
            ax.set_xlabel('Time')
            ax.set_ylabel(yaxis.title())
        fig.tight_layout()
        plt.show()

    ###################################################################################
    ##### Helper functions to manage file system, location of plot log files etc. #####
    ###################################################################################

    def get_gains(self, chunk, yaxis):
        '''
        Function to write and return the plot txt file
        chunk (int): The chunk to return the arrays for.
        yaxis (string): The axis you want to show the gains for.
        return (array, array): The array with the timestep information, the array with the gains for all antennas of a chunk.
        '''
        char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
        self.tempdir = os.path.expanduser('~') + '/apercal/temp/iaplot'
        gpplt = lib.miriad('gpplt')
        gpplt.vis = self.selfcaldir + '/' + str(chunk).zfill(2) + '/' + str(chunk).zfill(2) + '.mir'
        gpplt.log = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.txt'
        gpplt.yaxis = yaxis
        gpplt.options = 'gains'
        gpplt.go()
        gainstring = ''
        with open(gpplt.log, 'r') as gaintxt:
            gainlines = gaintxt.readlines()
            nants = int(gainlines[3][-3:-1])
            obsdate = gainlines[1][-19:-12]
            gainlines = gainlines[4:]
            joiner = range(0,len(gainlines),int(m.ceil(nants/6)+1))
            for num, line in enumerate(gainlines):
                if num in joiner:
                    joinedline = re.sub('\s+', ' ', ''.join(gainlines[num:num+3])).strip() + '\n'
                    joinedline = re.sub(':',' ',joinedline)
                    gainstring = gainstring + joinedline
        gainfile = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.txt'
        with open(gainfile, 'w') as gainreformated:
            gainreformated.write(gainstring)
        with open(gainfile, 'r') as gainarrayfile:
            gainarray = np.loadtxt(gainarrayfile)
        starttime = datetime.datetime(int('20' + obsdate[0:2]),int(time.strptime(obsdate[2:5],'%b').tm_mon),int(obsdate[5:7]))
        timearray = [starttime + datetime.timedelta(days=gainarray[gain,0],hours=gainarray[gain,1],minutes=gainarray[gain,2],seconds=gainarray[gain,3]) for gain in range(len(gainarray))]
        gainarray = gainarray[:,4:]
        return timearray, gainarray

    def manage_tempdir(self):
        '''
        Function to create and clean the temporary directory
        return (string): The temporary directory at $HOME/apercal/temp/iaplot
        '''
        self.tempdir = os.path.expanduser('~') + '/apercal/temp/iaplot'
        if not os.path.exists(self.tempdir):
            os.system('mkdir -p ' + self.tempdir)
        return self.tempdir

    def clean_tempdir(self):
        '''
        Function to clean the temporary directory from any temporary files
        '''
        self.tempdir = os.path.expanduser('~') + '/apercal/temp/iaplot'
        print('### Cleaning temporary directory! ###')
        os.system('rm -rf ' + self.tempdir + '/*')