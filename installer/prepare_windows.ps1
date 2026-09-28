param([Parameter(Mandatory=$true)][string]$Bundle,[switch]$InspectOnly)
$ErrorActionPreference='Stop'
$Bundle=(Resolve-Path -LiteralPath $Bundle).Path
$settings=Get-Content -LiteralPath (Join-Path $Bundle 'bundle.json') -Raw | ConvertFrom-Json
if($settings.mode -ne 'full'){throw 'Lite package never installs Windows/WSL.'}
if($InspectOnly){Write-Output 'Full Windows stage: local Microsoft WSL MSI + optional Windows features; no forced restart.';exit 0}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator permission required for the Windows WSL stage.'}
$msi=Join-Path $Bundle ('payload\'+$settings.wsl_msi)
$expected=$settings.wsl_sha256
if((Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash.ToLower() -ne $expected){throw 'WSL installer checksum mismatch.'}
$signature=Get-AuthenticodeSignature -LiteralPath $msi
if($signature.Status -ne 'Valid'){throw ('Microsoft WSL signature is not valid: '+$signature.Status)}
$needRestart=$false
foreach($feature in @('VirtualMachinePlatform','Microsoft-Windows-Subsystem-Linux')){
 $state=(Get-WindowsOptionalFeature -Online -FeatureName $feature).State
 if($state -ne 'Enabled'){
  $result=Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart -LimitAccess
  if($result.RestartNeeded){$needRestart=$true}
 }
}
$install=$true
try{
 $current=& wsl.exe --version 2>$null
 $first=($current -join ' ') -replace "`0",''
 if($first -match '(\d+\.\d+\.\d+\.\d+)'){$install=([version]$Matches[1] -lt [version]$settings.wsl_version)}
}catch{}
if($install){
 $log=Join-Path $Bundle 'windows-wsl-install.log'
 $result=Start-Process -FilePath msiexec.exe -ArgumentList @('/i',('"'+$msi+'"'),'/passive','/norestart','/L*v',('"'+$log+'"')) -WindowStyle Hidden -Wait -PassThru
 if($result.ExitCode -notin @(0,3010,1641)){throw ('WSL MSI failed: '+$result.ExitCode)}
 if($result.ExitCode -in @(3010,1641)){$needRestart=$true}
}
$record=@{stage='windows';restart_required=$needRestart;time=(Get-Date).ToString('s')}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Bundle 'windows-stage.json') -Encoding UTF8
if($needRestart){Write-Output 'RESTART REQUIRED. Save work, restart manually, then run Setup.cmd again. No automatic reboot.';exit 3010}
Write-Output 'Windows stage complete. Continue per-user application/Linux installation.'
