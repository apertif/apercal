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
  InlineJavascriptRequirement: {}

  InitialWorkDirRequirement:
      listing:
      - entry: $(inputs.target_preflagged)
        writable: true
      - entry: $(inputs.polcal_preflagged)
        writable: true
      - entry: $(inputs.fluxcal_preflagged)
        writable: true

baseCommand: [python]

inputs:
  target_preflagged:
    type: Directory

  polcal_preflagged:
    type: Directory

  fluxcal_preflagged:
    type: Directory


outputs:
  target_calibrated:
    type: Directory
    outputBinding:
      glob: $(inputs.target_preflagged.basename)

  polcal_Kcross:
    type: Directory
    outputBinding:
      glob: $(inputs.polcal_preflagged.basename.split('.').slice(0,-1).join('.')).Kcross

  polcal_flagversions:
    type: Directory
    outputBinding:
      glob: $(inputs.polcal_preflagged.basename).flagversions

  polcal_Xf:
    type: Directory
    outputBinding:
      glob: $(inputs.polcal_preflagged.basename.split('.').slice(0,-1).join('.')).Xf

  fluxcal_Df:
    type: Directory
    outputBinding:
      glob: $(inputs.fluxcal_preflagged.basename.split('.').slice(0,-1).join('.')).Df

  fluxcal_Bscan:
    type: Directory
    outputBinding:
      glob: $(inputs.fluxcal_preflagged.basename.split('.').slice(0,-1).join('.')).Bscan

  fluxcal_G0ph:
    type: Directory
    outputBinding:
      glob: $(inputs.fluxcal_preflagged.basename.split('.').slice(0,-1).join('.')).G0ph

  fluxcal_G1ap:
    type: Directory
    outputBinding:
      glob: $(inputs.fluxcal_preflagged.basename.split('.').slice(0,-1).join('.')).G1ap

  fluxcal_K:
    type: Directory
    outputBinding:
      glob: $(inputs.fluxcal_preflagged.basename.split('.').slice(0,-1).join('.')).K

  fluxcal_flagversions:
    type: Directory
    outputBinding:
      glob: $(inputs.fluxcal_preflagged.basename).flagversions


arguments:
  - prefix: '-c'
    valueFrom: |
        import logging
        logging.basicConfig(level=logging.DEBUG)
        from apercal.modules.ccal import ccal

        p = ccal()
        p.target = "$(inputs.target_preflagged.path)"
        p.fluxcal = "$(inputs.fluxcal_preflagged.path)"
        p.polcal = "$(inputs.polcal_preflagged.path)"
        p.subdirification = False
        p.go()
