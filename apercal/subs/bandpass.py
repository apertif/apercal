import numpy as np
import casacore.tables as pt
from apercal.subs import misc
from apercal.subs.msutils import get_nchan

np.set_printoptions(threshold=np.nan)

 
def create_bandpass(dataset, bp_file):
    bandpass=np.array([0.45, 0.62820563, 0.76009189, 0.8742484 , 0.95191308,
       0.99451883, 1.        , 0.98220764, 0.94912129, 0.92026621,
       0.90678901, 0.90600373, 0.91779495, 0.93071503, 0.94855349,
       0.95174723, 0.94731742, 0.93790802, 0.92318556, 0.91899994,
       0.91769283, 0.92277471, 0.93253455, 0.93826658, 0.93983332,
       0.93576765, 0.92806379, 0.92185001, 0.9233473 , 0.92640165,
       0.9291979 , 0.93471146, 0.9438049 , 0.94114222, 0.933553  ,
       0.92695906, 0.92560307, 0.92957955, 0.93430431, 0.93999952,
       0.94421266, 0.94298122, 0.93695875, 0.92719097, 0.92251599,
       0.91936509, 0.92553444, 0.93787559, 0.94731164, 0.95282789,
       0.94697576, 0.93459375, 0.91551182, 0.90368698, 0.90314634,
       0.91738173, 0.94488256, 0.97868364, 0.99836631, 0.98996378,
       0.94776365, 0.86937775, 0.75473572, 0.62672583])
    # Get the number of channels of the dataset
    nchannels = get_nchan(dataset)
    channels = range(nchannels)
    ants = np.array(misc.create_antnames())
    nants = len(ants)
    feeds = np.array(misc.create_feednames())
    nfeeds = len(feeds)
    nbandpass = len(bandpass)
    niterbandpass = (nchannels / nbandpass)
    # Create the single arrays with all the numbers
    antarray = np.repeat(ants, nchannels * nfeeds)
    feedarray = np.tile(np.repeat(feeds, nchannels), nants)
    chanarray = (np.tile(channels, nfeeds * nants)).astype('S5')
    valuearray = (np.tile(bandpass, niterbandpass * nfeeds * nants)).astype('S6')
    # Combine the different arrays
    concatarray = np.stack((antarray, feedarray, chanarray, valuearray), axis=1)
    # Save the array to file
    np.savetxt(bp_file, concatarray, fmt='%s %s %s %s', delimiter='\t')
