cwlVersion: v1.0
class: Workflow

inputs:
  target: Directory
  polcal: Directory
  fluxcal: Directory


outputs:
  calibrated:
    type: Directory
    outputSource: scal/target_selfcalibrated

steps:

  preflag_target:
    run: steps/preflag.cwl
    in:
      ms: target
    out:
      - preflagged

  preflag_fluxcal:
    run: steps/preflag.cwl
    in:
      ms: fluxcal
    out:
      - preflagged

  preflag_polcal:
    run: steps/preflag.cwl
    in:
      ms: polcal
    out:
      - preflagged

  ccal:
    run: steps/ccal.cwl
    in:
      target_preflagged: preflag_target/preflagged
      fluxcal_preflagged: preflag_fluxcal/preflagged
      polcal_preflagged: preflag_polcal/preflagged
    out:
      - fluxcal_Bscan
      - fluxcal_Df
      - fluxcal_G0ph
      - fluxcal_G1ap
      - fluxcal_K
      - fluxcal_calibrated
      - fluxcal_flagversions
      - polcal_Kcross
      - polcal_calibrated
      - polcal_flagversions
      - target_calibrated
      #- target_Xf

  convert:
    run: steps/convert.cwl
    in:
      target: ccal/target_calibrated
      fluxcal: ccal/fluxcal_calibrated
      polcal: ccal/polcal_calibrated
    out:
      - target_mir
      - fluxcal_mir
      - polcal_mir

  scal:
    run: steps/scal.cwl
    in:
      target_mir: convert/target_mir
      fluxcal_mir: convert/fluxcal_mir
      polcal_mir: convert/polcal_mir
    out:
      - target_selfcalibrated


# next steps:
#continuum
#line
#polarisation
#mosaic
#transfer
