def setinitdirs_abs(self):
    '''
    Creates the directory names for the subdirectories to make scripting easier
    '''
    self.linedir = self.basedir + self.beam + '/' + self.linesubdir
    self.contdir = self.basedir + self.beam + '/' + self.contsubdir
    self.absdir = self.basedir + self.beam  + '/abs/' 
    self.specdir = self.absdir+'spec/'    
    self.plotdir = self.absdir+'plot/'    
    
def setinitfiles_abs(self):
    '''
    Creates the file names for spectral analisys
    '''
    # Name the datasets -> t
    # !!!! to change according to the final products of previous pipeline
    self.data_cube = self.cubename+'.fits'
    self.data_cube_mir = self.cubename+'.mir'
    self.cont_im = self.contname+'.fits'
    self.cont_im_mir = self.contname+'.mir'
    self.src_imsad_out = 'cont_src_imsad.txt'
    self.src_list_csv = 'cont_src.csv'