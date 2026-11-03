$ErrorActionPreference = 'Stop'

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$exePath = Join-Path $toolsDir 'Klip.exe'

Get-ChocolateyWebFile `
  -PackageName $env:ChocolateyPackageName `
  -FileFullPath $exePath `
  -Url64bit 'https://github.com/zxy-something/klip/releases/download/v1.1.0/Klip.exe' `
  -Checksum64 '7a0b45ba07d1c3bb20a95a8d5ccfe2e287c25076af9e4d3b587f4e26050c45f4' `
  -ChecksumType64 'sha256'

$shortcutPath = Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'Klip.lnk'
Install-ChocolateyShortcut `
  -ShortcutFilePath $shortcutPath `
  -TargetPath $exePath `
  -WorkingDirectory $toolsDir `
  -IconLocation $exePath `
  -Description 'Klip screen recorder'
