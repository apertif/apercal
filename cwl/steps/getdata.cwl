$namespaces:
  cwltool: http://commonwl.org/cwltool#

class: CommandLineTool

cwlVersion: v1.0

hints:
  DockerRequirement:
      dockerPull: apertif/apercal

baseCommand: [python]

requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement:
    listing:
      - entry: $(inputs.irods)
        entryname: .irods
        writable: true

inputs:
  obsdate: string
  obsnum: int
  beamnum: int
  name: string
  irods: Directory

outputs:
  ms:
    type: Directory
    outputBinding:
      glob: "*.MS"

arguments:
  - prefix: '-c'
    valueFrom: |
        from os import path, getcwd
        import logging
        logging.basicConfig(level=logging.INFO)
        from apercal.subs.getdata_alta import getdata_alta
        beamnum = $(inputs.beamnum)
        name = "$(inputs.name)"
        obsdate = "$(inputs.obsdate)"
        obsnum = $(inputs.obsnum)
        outputname = "{name}_B{beamnum:02d}.MS".format(
                        name=name, beamnum=beamnum)
        outputpath = path.join(getcwd(), outputname)

        getdata_alta(obsdate, obsnum, beamnum, targetdir=outputname)
