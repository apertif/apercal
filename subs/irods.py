import os
from getdata_alta import getdata_alta

def getstatus_alta(date, ID, beam):
    '''
    Funtion to check if the data is on ALTA.
    date (int): Date of the observing weekend of the data. Usually the first day of the weekend (Friday). Format: YYMMDD
    ID (int): ID number of the observation. Format: NNN
    beam (int): Beam number to copy. Format: NN
    return (bool): True if the file is available, False if not
    '''
    if int(date) <= 180216:
        cmd = "ils /altaZone/home/apertif_main/wcudata/WSRTA%s%.2d/WSRTA%s%.2d_B%.3d.MS " % (int(date), int(ID), int(date), int(ID), int(beam))
    else:
        cmd = "ils /altaZone/home/apertif_main/wcudata/WSRTA%s%.3d/WSRTA%s%.3d_B%.3d.MS " % (int(date), int(ID), int(date), int(ID), int(beam))
    errorcode = os.system(cmd)
    if errorcode == 0:
        status = True
    else:
        status = False
    return status
