"""
mplot
An apercal utility to embed MIRIAD plots in an IPython Notebook.
The visualizer functions are:
mplot.uvplt(vis=None, tempdir="~/", **kwargs)
mplot.uvspec(vis=None, tempdir="~/", **kwargs
mplot.imview(im=None, tempdir="~/", **kwargs)
    Uses CGDISP
mplot.gpplt(vis=None, tempdir="~/", **kwargs)
You need to provide the vis and tempdir keywords. 
Additional keyword arguments which are commonly used by these MIRIAD tasks can be passed as follows:
mplot.uvspec(vis=<yourvis>, tempdir=<somedir>, nxy='2,2', options='avall', stokes='xx', interval='10000')
Each argument (even numbers and integers) need to be strings - e.g. the interval keyword.
"""

# Author: Brad Frank

import pylab as pl
import io
from IPython.display import HTML
from IPython.display import Image
from base64 import b64encode
import subprocess
import sys
import os
import lib
import logging

def check_tempdir(tempdir=None):
    '''
    check_tempdir
        Helper function to validate tempdir
    '''
    logger = logging.getLogger()
    if tempdir is None:
        logger.warn("Setting tempdir to /home/<user>/mplot")
        tempdir = os.path.expanduser('~')+'/mplot'
        if not os.path.exists(tempdir):
            answer = lib.query_yes_no("Are you sure you want to continue?")
            if answer:
                lib.basher('mkdir '+tempdir)
        return tempdir
    else:
        check = os.path.isdir(tempdir)
        if not os.path.exists(tempdir):
            logger.warn("tempdir does not exist!")
            lib.basher('mkdir '+tempdir)
        else:
            return tempdir

def check_file(f=None):
    '''
    check_file
        Helper function to check that f exists.
    '''
    if f!=None:
        check = os.path.isdir(f)
        if check==False:
            sys.exit("File not found!")
        else:
            return f
    else:
        sys.exit("File not specified!")
        

def videcon(outname, tempdir = None, r=2.):
    '''
    Uses avconv to make the video!
    '''
    o = lib.basher("avconv -r "+str(r)+" -f image2 -i "+tempdir+"/pgplot%d.gif -vcodec libx264 -y "+outname)

def vidshow(U=None, tempdir=None, vidname="some_vid", r=2):
    '''
    vidshow: merge gifs into m4v and construct the HTML embedder for IPython
    '''
    gifs = []
    
    lib.basher("rm "+tempdir+"/*gif*")
    
    U = lib.basher('ls pgplot.gif*')
    for i in range(0,len(U)):
        uin  = "pgplot.gif_"+str(i+1)
        uout = "pgplot"+str(i+1)+".gif"
        lib.basher('mv '+uin+' '+tempdir+'/'+uout)
    lib.basher("mv pgplot.gif "+tempdir+ "/pgplot1.gif")
    
    videcon(tempdir+"/"+vidname, tempdir=tempdir, r=r)

    # Delete the intermediate gifs
    lib.basher("rm "+tempdir+"/pgplot*.gif")
    video = io.open(tempdir+"/"+vidname, "rb").read()
    video_encoded = b64encode(video)
    video_tag = '<video controls alt="test" src="data:video/x-m4v;base64,{0}">'.format(video_encoded)
    return HTML(data=video_tag)

def vembed(video=None):
	'''
	vembed(video=None) - Video Embedder for IPython Notebooks. Uses the HTML module to embed an
	mp4 encoded video. 
	'''
	if video!=None:
		video = io.open(video, "rb").read()
		video_encoded = b64encode(video)
		video_tag = '<video controls alt="test" src="data:video/x-mp4;base64,{0}">'.format(video_encoded)
		return HTML(data=video_tag)
	else: 
                logger.critical("Please provide video to embed.")
                sys.exit(0)

def uvplt(vis=None, r=2., tempdir = None, **kwargs):
    '''
    IPython Video Embedder for UVPLT. 
    vis = Full path of vis to be plotted
        No Default
    tempdir = temporary directory to store the video and plot files. 
        Default is the ~/, but this is not recommended.
    r = plots per second [2]
        Please specify vis and any of the following:
                2pass,all,avall,average,axis,equal,flagged,hann,hours,inc,
                line,log,mrms,nanosec,nxy,options,rms,run,scalar,seconds,
                select,set,size,source,stokes,unwrap,vis,xrange,yrange
    '''
    # Check that vis exists
    vis = check_file(vis)
    
    # Check that the tempdir exists
    tempdir = check_tempdir(tempdir)
    
    # Switch to the path
    path = os.path.split(vis)
    os.chdir(path[0])
    
    # Use mirrun to run uvplt
    U = lib.masher(task = 'uvplt', vis = path[1], device='/gif', **kwargs)
    # Get the output from vidshow
    HTML = vidshow(U=U, tempdir=tempdir, vidname="uvplt.m4v", r=r)
    
    # Return the HTML object to the IPython Notebook for Embedding
    return HTML
   
def uvspec(vis=None, r=2., tempdir = None, **kwargs):
    '''
    IPython Video Embedder for UVSPEC. 
    vis = Full path of vis to be plotted
    r = plots per second [2]
        Please specify vis and any of the following:
                2pass,all,avall,average,axis,equal,flagged,hann,hours,inc,
                line,log,mrms,nanosec,nxy,options,rms,run,scalar,seconds,
                select,set,size,source,stokes,unwrap,vis,xrange,yrange
    '''
    # Check that vis exists
    vis = check_file(vis)
    
    # Validate the tempdir
    tempdir = check_tempdir(tempdir)
    
    # Switch to the path
    path = os.path.split(vis)
    os.chdir(path[0])
    
    # Make the plots using uvspec
    U = lib.masher(task = 'uvspec', vis=path[1], device='/gif', **kwargs)
    
    # Embed the plots
    HTML = vidshow(U=U, tempdir=tempdir, vidname="uvspec.m4v", r=r)
    
    return HTML

def gpplt(vis=None, r=2, tempdir = None, **kwargs):
    '''
    IPython Video Embedder for GPPLT. 
    vis = Full path of vis to be plotted
    r = plots per second [2]
        Please specify vis and any of the following:
         log yaxis options nxy select yrange 
         yaxis: amp, phase, real, imag
         options: gains, xygains, xbyygains, polarization, 
            2polarization, delays, speccor, bandpass, dots, 
            dtime, wra
    
    '''
    # First, check that vis exists
    vis = check_file(vis)
    
    # Check that tempdir exists
    tempdir = check_tempdir(tempdir)
    
    # Switch to the path
    path = os.path.split(vis)
    os.chdir(path[0])
    
    # Use GPPLT to make the plots
    U = lib.masher(task = 'gpplt', device='/gif', vis = path[1], **kwargs)
   
    # Get the output from vidshow
    HTML = vidshow(U=U, tempdir=tempdir, vidname="gpplt.m4v", r=r)
    
    # Return the HTML object to IPython Notebook for Embedding
    return HTML
        
def imview(im=None, r=2, tempdir = None, typ='pixel', slev = "p,1", levs="2e-3", 
        rang="0,2e-3,lin", nxy="1,1", labtyp = "hms,dms", options="wedge,3pixel", **kwargs):
    '''
    IPython Video Embedder for CGDISP.
    im = Full path of image to be plotted
    r = plots per second [2]
        Please specify vis and any of the following:
         
        type slev levs rang (not range!) nxy labtyp options
    '''
    # Check that the image exists
    im = check_file(im)
    
    # Check that the tempdir exists
    tempdir = check_tempdir(tempdir)
    
    # If we've gotten this far, then it means that we've passed the test.
    
    # Switch to the path
    path = os.path.split(im)
    os.chdir(path[0])
    
    # Use CGDISP to make the plots
    # This uses the generic lib.mirrun() method, so you don't need anything special to run this.
    U = lib.masher(task='cgdisp', device='/gif', in_ = path[1], type=typ, slev=slev, levs=levs, range=rang,
                   nxy=nxy, labtyp=labtyp, **kwargs)

    # Get the output from vidshow!
    HTML = vidshow(tempdir=tempdir, vidname="imview.m4v", r=r)

    # Return the HTML object to IPython Notebook for Embedding!
    return HTML

def imhist(im=None, tempdir = None, device='/gif'):
	'''
	Pops up an histogram of the image.
	'''
        logger = logging.getLogger()
	if im is None:

		out = lib.basher("imhist in="+im+" device="+device)
		lib.basher("mv pgplot.gif "+tempdir+'imhist.gif')
		i = Image(filename = tempdir + 'imhist.gif')
		out = lib.basher("imhist in="+im)
                logger.info(out)
		return i
	else:
		logger.critical("Error: im argument missing.")
                sys.exit(0)
