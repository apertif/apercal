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
  target:
    type: Directory
    outputSource: getdata_target/ms

  fluxcal:
    type: Directory
    outputSource: getdata_fluxcal/ms

  polcal:
    type: Directory
    outputSource: getdata_polcal/ms


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

