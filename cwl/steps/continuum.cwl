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
      - entry: $(inputs.target_mir)
        writable: true

baseCommand: [python]

inputs:
  target_mir:
    type: Directory
  target_amp:
    type: Directory

outputs:
  target_selfcalibrated:
    type: Directory
    outputBinding:
      glob: $(inputs.target_mir.basename)

arguments:
  - prefix: '-c'
    valueFrom: |
        import logging
        logging.basicConfig(level=logging.DEBUG)
        from apercal.modules.continuum import continuum

        p = continuum()
        p.target = "$(inputs.target_mir.path)"
        p.subdirification = False
        p.go()
