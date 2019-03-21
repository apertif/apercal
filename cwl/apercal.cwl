cwlVersion: v1.0
class: Workflow

inputs:
  target_obsdate: string
  target_obsnum: int
  target_beamnum: int
  target_name: string
  fluxcal_obsdate: string
  fluxcal_obsnum: int
  fluxcal_beamnum: int
  fluxcal_name: string
  polcal_obsdate: string
  polcal_obsnum: int
  polcal_beamnum: int
  polcal_name: string
  irods: Directory


outputs:
  calibrated:
    type: Directory
    outputSource: scal/target_selfcalibrated

steps:
  getdata_target:
    run: steps/getdata.cwl
    in:
      obsdate: target_obsdate
      obsnum: target_obsnum
      beamnum: target_beamnum
      name: target_name
      irods: irods
    out:
      - ms

  getdata_fluxcal:
    run: steps/getdata.cwl
    in:
      obsdate: fluxcal_obsdate
      obsnum: fluxcal_obsnum
      beamnum: fluxcal_beamnum
      name: fluxcal_name
      irods: irods
    out:
      - ms

  getdata_polcal:
    run: steps/getdata.cwl
    in:
      obsdate: polcal_obsdate
      obsnum: polcal_obsnum
      beamnum: polcal_beamnum
      name: polcal_name
      irods: irods
    out:
      - ms


  preflag:
    run: steps/preflag.cwl
    in:
      target: getdata_target/ms
      fluxcal: getdata_fluxcal/ms
      polcal: getdata_polcal/ms
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
