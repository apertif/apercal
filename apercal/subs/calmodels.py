def is_polarised(source_name):
    return source_name.strip(".MS") in ["3C138", "3C286"]

def get_calparameters(calibrator):
    """
    calibrator(string): Calibrator name to get the values for
    Values are taken from Perley Butler 2017: http://iopscience.iop.org/article/10.3847/1538-4365/aa6df9/pdf
    Values for CTD93 from Bjorn Adebahr's fits

    return(bool, string, string, string, string): Calibrator model available, I,Q,U,V fluxes, parametric model
    coefficients, reference frequency, Rotation Measure
    """
    if calibrator == '3C48':
        av = True
        fluxdensity = '21.149, 0.0, 0.0, 0.0'
        spix = '-0.7553, -0.1914, 0.0498'
        reffreq = '1.0GHz'
        rotmeas = '0.0'
    elif calibrator == '3C138':
        av = True
        fluxdensity = '8.30, 0.630, -0.170, 0.0'
        spix = '-0.4981, -0.1552, -0.0102, 0.0223'
        reffreq = '1.4GHz'
        rotmeas = '0.0'
    elif calibrator == '3C147':
        av = True
        fluxdensity = '28.288, 0.0, 0.0, 0.0'
        spix = '-0.6961, -0.2007, 0.0640, -0.0464, 0.0289'
        reffreq = '1.0GHz'
        rotmeas = '0.0'
    elif calibrator == '3C196':
        av = True
        fluxdensity = '19.373, 0.0, 0.0, 0.0'
        spix = '-0.8520, -0.1534, -0.0200, 0.0201'
        reffreq = '1.0GHz'
        rotmeas = '0.0'
    elif calibrator == '3C286':
        av = True
        fluxdensity = '14.650, 0.560, 1.260, 0.0'
        spix = '-0.4507, -0.1798, 0.0357'
        reffreq = '1.4GHz'
        rotmeas = '0.0'
    elif calibrator == '3C295':
        av = True
        fluxdensity = '29.519, 0.0, 0.0, 0.0'
        spix = '-0.7658, -0.2780, -0.0347, 0.0399'
        reffreq = '1.0GHz'
        rotmeas = '0.0'
    elif calibrator == 'CTD93':
        av = True
        fluxdensity = '5.140, 0.0, 0.0, 0.0'
        spix = '-0.7110, 0.0230, 1.3190, -0.4938'
        reffreq = '1.0GHz'
        rotmeas = '0.0'
    else:
        av = False
        fluxdensity = '1.0, 0.0, 0.0, 0.0'
        spix = '0.0'
        reffreq = '1.2496GHz'
        rotmeas = '0.0'

    return av, fluxdensity, spix, reffreq, rotmeas
