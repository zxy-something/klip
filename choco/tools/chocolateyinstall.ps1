$ErrorActionPreference = 'Stop'

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$exePath = Join-Path $toolsDir 'Klip.exe'

Get-ChocolateyWebFile `
  -PackageName $env:ChocolateyPackageName `
  -FileFullPath $exePath `
  -Url64bit 'https://github.com/zxy-something/klip/releases/download/v1.0.0/Klip.exe' `
  -Checksum64 'b79e2c9ad12c61e7cc4b8ec51b913bef23d687af88d31f6e767a79ca11d531a6' `
  -ChecksumType64 'sha256'

$shortcutPath = Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'Klip.lnk'
Install-ChocolateyShortcut `
  -ShortcutFilePath $shortcutPath `
  -TargetPath $exePath `
  -WorkingDirectory $toolsDir `
  -IconLocation $exePath `
  -Description 'Klip screen recorder'
