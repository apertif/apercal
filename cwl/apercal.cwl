cwlVersion: v1.0
class: Workflow

inputs:
  target: Directory
  fluxcal: Directory
  polcal: Directory

outputs:
  calibrated:
    type: Directory
    outputSource: ccal/target_calibrated

steps:
  preflag:
    run: steps/preflag.cwl
    in:
      target: target
      fluxcal: fluxcal
      polcal: polcal
    out:
      - target_preflagged
      - fluxcal_preflagged
      - polcal_preflagged

  ccal:
    run: steps/ccal.cwl
    in:
      target_preflagged: preflag/target_preflagged
      fluxcal_preflagged: preflag/fluxcal_preflagged
      polcal_preflagged: preflag/polcal_preflagged
    out:
      - target_calibrated
      - target_Df
      - target_Kcross
      - target_Xf
      - target_Bscan
      - target_G0ph
      - target_G1ap
      - target_K


  convert:
    run: steps/convert.cwl
    in:
      target: preflag/target_calibrated
    out:
      - target_converted


#scal
#continuum
#line
#polarisation
#mosaic
#transfer
#convert



# convert
# ccal
# scal
# line
# transfer
# continuum
# mosaic
