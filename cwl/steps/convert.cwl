$namespaces:
  cwltool: http://commonwl.org/cwltool#

class: CommandLineTool

cwlVersion: v1.0

hints:
  DockerRequirement:
      dockerPull: apertif/apercal

  cwltool:InplaceUpdateRequirement:
    inplaceUpdate: true

requirements:
  InitialWorkDirRequirement:
      listing:
      - entry: $(inputs.target)
        writable: true
      - entry: $(inputs.fluxcal)
        writable: true
      - entry: $(inputs.polcal)
        writable: true

baseCommand: [python]

inputs:
  target:
    type: Directory

  polcal:
    type: Directory

  fluxcal:
    type: Directory

outputs:
  target_converted:
    type: Directory
    outputBinding:
      glob: $(inputs.target.basename)

  polcal_converted:
    type: Directory
    outputBinding:
      glob: $(inputs.polcal.basename)

  fluxcal_converted:
    type: Directory
    outputBinding:
      glob: $(inputs.fluxcal.basename)


arguments:
  - prefix: '-c'
    valueFrom: |
        import logging
        logging.basicConfig(level=logging.DEBUG)
        from apercal.modules.convert import convert
        from os import getcwd

        p = convert()
        p.target = "$(inputs.target.path)"
        p.fluxcal = "$(inputs.fluxcal.path)"
        p.polcal = "$(inputs.polcal.path)"
        p.subdirification = False
        p.crosscalsubdir = "/tmp"
        p.go()
