class: CommandLineTool

cwlVersion: v1.0

hints:
  DockerRequirement:
      dockerPull: apertif/apercal

baseCommand: [python]

requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement:
    listing: |
      ${
         return [{"class": "Directory",
                  "basename": ".irodsA",
                  "listing": [ inputs.irodsA ] }
               ]
       }

  EnvVarRequirement:
    envDef:
      IRODS_HOST: alta-icat.astron.nl
      IRODS_PORT: "1247"
      IRODS_USER_NAME: dijkema
      IRODS_ZONE_NAME: altaZone

inputs:
  obsdate: string
  obsnum: int
  beamnum: int
  name: string
  irodsA: File
  irodsenvironment: File

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
