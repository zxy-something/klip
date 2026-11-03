$ErrorActionPreference = 'Stop'

$shortcutPath = Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'Klip.lnk'
if (Test-Path $shortcutPath) {
  Remove-Item $shortcutPath -Force
}
