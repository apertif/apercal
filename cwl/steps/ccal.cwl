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
      - entry: $(inputs.target_preflagged)
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

  target_Df:
    type: Directory
    outputBinding:
      glob: $(inputs.target_preflagged.nameroot)Df

  target_Kcross:
    type: Directory
    outputBinding:
      glob: $(inputs.target_preflagged.nameroot)Kcross

  target_Xf:
    type: Directory
    outputBinding:
      glob: $(inputs.target_preflagged.nameroot)Xf

  target_Bscan:
    type: Directory
    outputBinding:
      glob: $(inputs.target_preflagged.nameroot)Bscan

  target_G0ph:
    type: Directory
    outputBinding:
      glob: $(inputs.target_preflagged.nameroot)G0ph

  target_G1ap:
    type: Directory
    outputBinding:
      glob: $(inputs.target_preflagged.nameroot)G1ap

  target_K:
    type: Directory
    outputBinding:
      glob: $(inputs.target_preflagged.nameroot)K


arguments:
  - prefix: '-c'
    valueFrom: |
        import logging
        logging.basicConfig(level=logging.DEBUG)
        from apercal.modules.ccal import ccal

        p = convert()
        p.target = "$(inputs.target_preflagged.path)"
        p.fluxcal = "$(inputs.fluxcal_preflagged.path)"
        p.polcal = "$(inputs.polcal_preflagged.path)"
        p.subdirification = False
        p.go()
