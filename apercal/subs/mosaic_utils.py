import numpy as np
from apercal.libs import lib
import logging

logger = logging.getLogger(__name__)

"""
Module with functions to support the mosaic module. 
Based on Beam_Functions.ipnyb by D.J. Pisano available 
in the Apertif-comissioning repository
"""


# ++++++++++++++++++++++++++++++++++++++++
# Functions to create the beam maps
# ++++++++++++++++++++++++++++++++++++++++
def create_beam(beam_list, beam_map_dir, type = 'Gaussian'):
    """
    Function to create beam maps with miriad
    
    In contrast to the notebook, this function gets a 
    list of beams and creates the beam maps for these
    specific beams.

    Args:
        beam_list (list(str)): list of beams
        beam_map_dir (str): output directory for the beam maps
        type (str): 'Gaussian' (simple case from notebook) or 'Correct' (final use case)
    """


# ++++++++++++++++++++++++++++++++++++++++
# Functions to create a correlation matrix
# ++++++++++++++++++++++++++++++++++++++++

def correlation_matrix_symmetrize(a):
    """
    Helper function for creating the correlation matrix
    """

    return a + a.T - np.diag(a.diagonal())

def create_correlation_matrix(output_dir):
    """
    This function creates a correlation matrix for 39 independent beams (i.e. an identity matrix)
    and writes it out to a file
    """
    # This needs to be multiplied by the variance for each beam still.
    C=np.identity(40,dtype=float)
    # Fill array with estimated correlation coefficients (r in the nomenclature)
    # These are eyeballed based on ASKAP measurements.
    C[0,17]=0.7
    C[0,24]=0.7
    C[0,18]=0.25
    C[0,23]=0.25
    C[1,2]=0.11
    C[1,8]=0.11
    C[2,3]=0.11
    C[2,8]=0.11
    C[2,9]=0.11
    C[3,4]=0.11
    C[3,9]=0.11
    C[3,10]=0.11
    C[4,5]=0.11
    C[4,10]=0.11
    C[4,11]=0.11
    C[5,6]=0.11
    C[5,11]=0.11
    C[5,12]=0.11
    C[6,7]=0.11
    C[6,12]=0.11
    C[6,13]=0.11
    C[7,13]=0.11
    C[7,14]=0.11
    C[8,9]=0.11
    C[8,15]=0.11
    C[9,10]=0.11
    C[9,15]=0.11
    C[9,16]=0.11
    C[10,11]=0.11
    C[10,16]=0.11
    C[10,17]=0.11
    C[11,12]=0.11
    C[11,17]=0.11
    C[11,18]=0.11
    C[12,13]=0.11
    C[12,18]=0.11
    C[12,19]=0.11
    C[13,14]=0.11
    C[13,19]=0.11
    C[13,20]=0.11
    C[14,20]=0.11
    C[15,16]=0.11
    C[15,21]=0.11
    C[15,22]=0.11
    C[16,17]=0.11
    C[16,22]=0.11
    C[16,23]=0.11
    C[17,18]=0.11
    C[17,23]=0.11
    C[17,24]=0.11
    C[18,19]=0.11
    C[18,24]=0.11
    C[18,25]=0.11
    C[19,20]=0.11
    C[19,25]=0.11
    C[19,26]=0.11
    C[20,26]=0.11
    C[21,22]=0.11
    C[21,27]=0.11
    C[22,23]=0.11
    C[22,27]=0.11
    C[22,28]=0.11
    C[23,24]=0.11
    C[23,28]=0.11
    C[23,29]=0.11
    C[24,25]=0.11
    C[24,29]=0.11
    C[24,30]=0.11
    C[25,26]=0.11
    C[25,30]=0.11
    C[25,31]=0.11
    C[26,31]=0.11
    C[26,32]=0.11
    C[27,28]=0.11
    C[27,33]=0.11
    C[27,34]=0.11
    C[28,29]=0.11
    C[28,34]=0.11
    C[28,35]=0.11
    C[29,30]=0.11
    C[29,35]=0.11
    C[29,36]=0.11
    C[30,31]=0.11
    C[30,36]=0.11
    C[30,37]=0.11
    C[31,32]=0.11
    C[31,37]=0.11
    C[31,38]=0.11
    C[32,38]=0.11
    C[32,39]=0.11
    C[33,34]=0.11
    C[34,35]=0.11
    C[35,36]=0.11
    C[36,37]=0.11
    C[37,38]=0.11
    C[38,39]=0.11
    C=symmetrize(C)
    np.savetxt(os.path.join(output_dir,'correlation.txt'),C,fmt='%f')
