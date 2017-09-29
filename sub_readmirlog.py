import string
import random
import datetime
import lib
import os
import time
import numpy as np
import re
import math as m
from astropy.table import Table

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
        joiner = range(0, len(gainlines), int(m.ceil(nants / 6) + 1))
        for num, line in enumerate(gainlines):
            if num in joiner:
                joinedline = re.sub('\s+', ' ', ''.join(gainlines[num:num + 3])).strip() + '\n'
                joinedline = re.sub(':', ' ', joinedline)
                gainstring = gainstring + joinedline
    gainfile = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.txt'
    with open(gainfile, 'w') as gainreformated:
        gainreformated.write(gainstring)
    with open(gainfile, 'r') as gainarrayfile:
        gainarray = np.loadtxt(gainarrayfile)
    starttime = datetime.datetime(int('20' + obsdate[0:2]), int(time.strptime(obsdate[2:5], '%b').tm_mon), int(obsdate[5:7]))
    timearray = [starttime + datetime.timedelta(days=gainarray[gain, 0], hours=gainarray[gain, 1], minutes=gainarray[gain, 2], seconds=gainarray[gain, 3]) for gain in range(len(gainarray))]
    gainarray = gainarray[:, 4:]
    return timearray, gainarray

def get_bp(file):
    '''
    Function to create a python array from a bandpass calibrated dataset to analyse
    file (str): u,v file with the bandpass calibration
    return(array, array): The bandpass array in the following order (antenna, frequencies, solution intervals) and a list of the frequencies
    '''
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
    tempdir = os.path.expanduser('~') + '/apercal/temp/mirlog'
    bp_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file
    gpplt.log = tempdir + '/' + bp_string
    gpplt.options = 'bandpass'
    gpplt.go()
    t = Table.read(tempdir + '/' + bp_string, format='ascii')
    freqs = np.array(np.unique(t['col1']))
    nfreq = len(freqs)
    nint = len(t['col1'])/nfreq
    nant = int(len(t[0])-1)
    bp_array = np.zeros((nant, nfreq, nint))
    for ant in range(nant):
        bp_array[ant,:,:] = np.swapaxes(t['col' + str(ant+2)].reshape(nint, nfreq),0,1)
    return bp_array, freqs

