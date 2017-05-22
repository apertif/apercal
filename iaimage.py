__author__ = "Bjoern Adebahr"
__copyright__ = "ASTRON"
__email__ = "adebahr@astron.nl"

import lib
import os, sys
import ConfigParser
import random
import string
from kapteyn import maputils
from matplotlib import pyplot as plt
import numpy as np
import astropy.io.fits as pyfits
import glob
from matplotlib.widgets import Slider, Button

####################################################################################################

class iaimage:
    '''
    Interactive image class to show images and get statistics
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
        self.selfcaldir = self.basedir + self.selfcalsubdir
        self.finaldir = self.basedir + self.finalsubdir

    ################################################################
    ##### Functions to show and analyse images in the notebook #####
    ################################################################

    def show_image(self, beam=None, step=None, chunk=None, major=None, minor=None, finaltype=None, type=None, imin=None, imax=None):
        '''
        Function to show an image in the notebook
        beam (string): The beam number to show the image for. 'iterate' will iterate over beams.
        step (string): The step of the pipeline to show the image for. No default. selfcal and final are allowed.
        chunk (string): The frequency chunk to show the image for. 'iterate' will iterate over chunks. No default.
        major(string or int): Major iteration of clean to display. Default is last iteration. pm is also possible. Only for selfcal, not for final step. 'iterate' will iterate over images for major cycles.
        minor (string or int): Minor iteration of clean to display. Default is last iteration. 'iterate' will iterate over images for minor cycles.
        finaltype(string): Type of final image to show. mf and stack are possible.
        type(string): Type of image to show. mask, beam, image, residual, and in case of step=final final are possible. 'all' will show image, mask, residual, and model in one plot.
        imin(float): Minimum cutoff in the image.
        imax(float): Maximum cutoff in the image.
        return (string): String with a path and image name to use for displaying.
        '''
        self.manage_tempdir() # Check if the temporary directory exists and if not create it
        self.clean_tempdir() # Remove any temorary files from the temporary directory
        char_set = string.ascii_uppercase + string.digits # Create a charset for random image name generation
        if any(it == 'iterate' for it in [beam, chunk, major, minor]):
            if beam == 'iterate':
                print('### Not implemented yet ###')
            elif chunk == 'iterate':
                imagelist = glob.glob(self.selfcaldir + '/*/' + str(major).zfill(2) + '/' + str(type) + '_' + str(minor).zfill(2))
                plottext = 'Frequency \nchunk'
            elif major == 'iterate':
                imagelist = glob.glob(self.selfcaldir + '/' + str(chunk).zfill(2) + '/*/' + str(type) + '_' + str(minor).zfill(2))
                plottext = 'Major \ncycle'
            elif minor == 'iterate':
                imagelist = glob.glob(self.selfcaldir + '/' + str(chunk).zfill(2) + '/' + str(major).zfill(2) + '/' + str(type) + '_*')
                plottext = 'Minor \ncycle'
            images = []
            for image in imagelist:
                self.fitsimage = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.fits'
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = image
                fits.out = self.fitsimage
                fits.go()
                images.append(maputils.FITSimage(self.fitsimage))

            # Do the autoscaling of the image contrast

            if imin == None or imax == None:
                imagedata = pyfits.open(self.fitsimage)[0].data
                imagestd = np.nanstd(imagedata)
                if imin == None:
                    imin = -1*imagestd
                else:
                    pass
                if imax == None:
                    imax = 3*imagestd
                else:
                    pass
            else:
                pass
            print('Minimum/maximum colour range for image: ' + str(imin) + '/' + str(imax))

            # Draw the plot

            fig = plt.figure(figsize=(12, 10))
            frame = fig.add_axes([0.1, 0.15, 0.85, 0.8])
            frame.set_title(str(type).capitalize())

            # Add the slider for selecting the image

            slider_ax = fig.add_axes([0.103, 0.05, 0.672, 0.03])
            slider = Slider(slider_ax, plottext, 0, len(images)-1, valinit = 0, valfmt='%1.0f', dragging=False, color='black')

            # Define the attributes for the plot

            image_object = images[int(round(slider.val))].Annotatedimage(frame, cmap='gist_gray', clipmin=imin, clipmax=imax)
            image_object.Image()
            image_object.Graticule()
            image_object.Colorbar()
            image_object.interact_toolbarinfo()
            image_object.interact_imagecolors()
            image_object.plot()
            fig.canvas.draw()

            # Update the plot if the slider is clicked

            def slider_on_changed(val):
                image_object = images[int(round(slider.val))].Annotatedimage(frame, cmap='gist_gray', clipmin=imin, clipmax=imax)
                image_object.Image()
                image_object.interact_toolbarinfo()
                image_object.interact_imagecolors()
                image_object.plot()
                fig.canvas.draw()

            slider.on_changed(slider_on_changed)
            plt.show()
        else:
            if type == 'all': # Make a 2x2 plot of image, residual, mask, and model of a cycle
                rawimage = self.get_image(beam, step, chunk, major, minor, finaltype, 'image')
                rawresidual = self.get_image(beam, step, chunk, major, minor, finaltype, 'residual')
                rawmask = self.get_image(beam, step, chunk, major, minor, finaltype, 'mask')
                rawmodel = self.get_image(beam, step, chunk, major, minor, finaltype, 'model')
                self.fitsimage = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.fits'
                self.fitsresidual = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.fits'
                self.fitsmask = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.fits'
                self.fitsmodel = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.fits'
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = rawimage
                fits.out = self.fitsimage
                fits.go()
                fits.in_ = rawresidual
                fits.out = self.fitsresidual
                fits.go()
                fits.in_ = rawmask
                fits.out = self.fitsmask
                fits.go()
                regrid = lib.miriad('regrid')
                regrid.in_ = rawmodel
                tempregrid = self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8))
                regrid.out = tempregrid
                regrid.axes = '1,2'
                regrid.tin = rawimage
                regrid.go()
                fits.in_ = tempregrid
                fits.out = self.fitsmodel
                fits.go()
                im = maputils.FITSimage(self.fitsimage)
                imdata = pyfits.open(self.fitsimage)[0].data
                imstd = np.nanstd(imdata)
                re = maputils.FITSimage(self.fitsresidual)
                redata = pyfits.open(self.fitsresidual)[0].data
                restd = np.nanstd(redata)
                ma = maputils.FITSimage(self.fitsmask)
                madata = pyfits.open(self.fitsmask)[0].data
                mastd = np.nanstd(madata)
                mo = maputils.FITSimage(self.fitsmodel)
                modata = pyfits.open(self.fitsmodel)[0].data
                mostd = np.nanstd(modata)
                fig = plt.figure(figsize=(12, 10))
                frame1 = fig.add_axes([0.1,0.58,0.4,0.4])
                frame1.set_title('Image')
                frame2 = fig.add_axes([0.59,0.58,0.4,0.4])
                frame2.set_title('Residual')
                frame3 = fig.add_axes([0.1, 0.12, 0.4, 0.4])
                frame3.set_title('Mask')
                frame4 = fig.add_axes([0.59, 0.12, 0.4, 0.4])
                frame4.set_title('Model')
                annim1 = im.Annotatedimage(frame1, cmap='gist_gray')
                annim2 = re.Annotatedimage(frame2, cmap='gist_gray')
                annim3 = ma.Annotatedimage(frame3, cmap='gist_gray')
                annim4 = mo.Annotatedimage(frame4, cmap='gist_gray')
                annim1.Image(); annim2.Image(); annim3.Image(); annim4.Image()
                if imin == None:  # Set the displayed colour range if not set
                    immin, remin, mamin, momin = -1*imstd, -1*restd, -1*mastd, -1*mostd
                else:
                    immin, remin, mamin, momin = imin, imin, imin, imin
                if imax == None:
                    immax, remax, mamax, momax = 3*imstd, 3*restd, mastd, mostd
                else:
                    immax, remax, mamax, momax = imax, imax, imax, imax
                print('Minimum colour range for image: ' + str(immin) + ' residual: ' + str(remin) + ' mask: ' + str(mamin) + ' model: ' + str(momin))
                print('Maximum colour range for image: ' + str(immax) + ' residual: ' + str(remax) + ' mask: ' + str(mamax) + ' model: ' + str(momax))
                annim1.set_norm(clipmin=immin, clipmax=immax); annim2.set_norm(clipmin=remin, clipmax=remax); annim3.set_norm(clipmin=0.0, clipmax=mamax); annim4.set_norm(clipmin=0.0, clipmax=momax)
                annim1.Colorbar(); annim2.Colorbar(); annim3.Colorbar(); annim4.Colorbar()
                annim1.Graticule(); annim2.Graticule(); annim3.Graticule(); annim4.Graticule()
                annim1.interact_toolbarinfo(); annim2.interact_toolbarinfo(); annim3.interact_toolbarinfo(); annim4.interact_toolbarinfo()
                annim1.interact_imagecolors(); annim2.interact_imagecolors(); annim3.interact_imagecolors(); annim4.interact_imagecolors()
                tdict = dict(color='g', fontsize=10, va='bottom', ha='left')
                fig.text(0.01, 0.01, annim1.get_colornavigation_info(), tdict)
                maputils.showall()
            else: # Make a simple plot of one specified image
                rawimage = self.get_image(beam, step, chunk, major, minor, finaltype, type)
                self.fitsimage =  self.tempdir + '/' + ''.join(random.sample(char_set * 8, 8)) + '.fits'
                fits = lib.miriad('fits')
                fits.op = 'xyout'
                fits.in_ = rawimage
                fits.out = self.fitsimage
                fits.go()
                f = maputils.FITSimage(self.fitsimage)
                imdata = pyfits.open(self.fitsimage)[0].data
                imstd = np.nanstd(imdata)
                fig = plt.figure(figsize=(12,10))
                frame = fig.add_axes([0.1, 0.15, 0.85, 0.8])
                annim = f.Annotatedimage(frame, cmap='gist_gray')
                annim.Image()
                if imin == None:  # Set the displayed colour range if not set
                    imin = -1*imstd
                if imax == None:
                    imax = 3*imstd
                print('Minimum/maximum colour range for image: ' + str(imin) + '/' + str(imax))
                annim.set_norm(clipmin=imin,clipmax=imax)
                annim.Colorbar()
                annim.Graticule()
                annim.interact_toolbarinfo()
                annim.interact_imagecolors()
                units = 'unknown'
                if 'BUNIT' in f.hdr:
                    units = f.hdr['BUNIT']
                helptext = "File: [%s]  Data units:  [%s]\n" % (rawimage, units)
                helptext += annim.get_colornavigation_info()
                tdict = dict(color='g', fontsize=10, va='bottom', ha='left')
                fig.text(0.01, 0.01, helptext, tdict)
                maputils.showall()

    def show_stats(self, borders=[]):
        '''
        Function to show the stats (rms, min, max) of an image previously loaded or plotted with show_image
        borders (list of 4 int): The bottom left and top right pixel values to use for calculating the stats. No value means the entire image.
        '''
        image = pyfits.open(self.fitsimage)
        image_data = np.squeeze(image[0].data)
        if len(borders) == 0:
            rms = np.nanstd(image_data)
            min = np.nanmin(image_data)
            max = np.nanmax(image_data)
        else:
            rms = np.nanstd(image_data[borders])
            min = np.nanmin(image_data[borders])
            max = np.nanmax(image_data[borders])
        image.close()
        print('### RMS = ' + str(rms) + ' Jy/beam ###')
        print('### MAX = ' + str(max) + ' Jy/beam ###')
        print('### MIN = ' + str(min) + ' Jy/beam ###')
        return rms, min, max

    ###########################################################################
    ##### Helper functions to manage file system, location of images etc. #####
    ###########################################################################

    def get_image(self, beam, step, chunk, major=None, minor=None, finaltype='stack', type='image'):
        '''
        Function to find the location of an image and return a string with an absolute path and image name
        beam (string): The beam number to show the image for.
        step (string): The step of the pipeline to show the image for. No default. selfcal and final are allowed.
        chunk (string): The frequency chunk to show the image for. No default.
        major(string or int): Major iteration of clean to display. Default is last iteration. pm is also possible. Only for selfcal, not for final step.
        minor (string or int): Minor iteration of clean to display. Default is last iteration.
        finaltype(string): Type of final image to show. mf and stack are possible.
        type(string): Type of image to show. mask, beam, image, residual, and in case of step=final final are possible.
        return (string): String with a path and image name to use for displaying.
        '''
        if step == 'selfcal':
            imagestring = self.selfcaldir + '/' + str(chunk).zfill(2) + '/'
            if major == None:
                for n in range(100)[::-1]:
                    if os.path.exists(imagestring + str(n).zfill(2)):
                        imagestring = imagestring + str(n).zfill(2) + '/'
                        break
                    else:
                        continue
            else:
                imagestring = imagestring + str(major).zfill(2) + '/'
            imagestring = imagestring + str(type)
            if minor == None:
                for n in range(100)[::-1]:
                    if os.path.exists(imagestring + '_' + str(n).zfill(2)):
                        imagestring = imagestring + '_' + str(n).zfill(2)
                        break
                    else:
                        continue
            else:
                imagestring = imagestring + '_' + str(minor).zfill(2)
        elif step == 'final':
            imagestring = self.finaldir + '/' + 'continuum/'
            if type == 'final':
                if finaltype == 'stack':
                    imagestring = imagestring + self.target.rstrip('.MS') + '_stack'
                elif finaltype == 'mf':
                    imagestring = imagestring + self.target.rstrip('.MS') + '_mf'
            else:
                imagestring = imagestring + str(finaltype) + '/' + str(chunk).zfill(2) + '/' + str(type)
                if minor == None:
                    for n in range(100)[::-1]:
                        if os.path.exists(imagestring + '_' + str(n).zfill(2)):
                            imagestring = imagestring + '_' + str(n).zfill(2)
                            break
                        else:
                            continue
                else:
                    imagestring = imagestring + '_' + str(minor).zfill(2)
        else:
            print('### Step not accepted! Only selfcal and final are allowed! ###')
        if os.path.exists(imagestring): # Check if file exists
            return(imagestring)
        else:
            print('### Image ' + str(imagestring) + ' does not exist) ###')
            sys.exit(1)

    def manage_tempdir(self):
        '''
        Function to create and clean the temporary directory
        return: The temporary directory at $HOME/apercal/temp/iaimage
        '''
        self.tempdir = os.path.expanduser('~') + '/apercal/temp/iaimage'
        if not os.path.exists(self.tempdir):
            os.system('mkdir -p ' + self.tempdir)
        return self.tempdir

    def clean_tempdir(self):
        '''
        Function to clean the temporary directory from any temporary files
        '''
        self.tempdir = os.path.expanduser('~') + '/apercal/temp/iaimage'
        print('### Cleaning temporary directory! ###')
        os.system('rm -rf ' + self.tempdir + '/*')
