$ErrorActionPreference = 'Stop'
$appDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$entryPoint = Join-Path $appDirectory 'timer_note.pyw'
$scheduleFile = Join-Path $appDirectory 'schedule.json'
$settingsFile = Join-Path $appDirectory 'settings.json'
$soundDirectory = Join-Path $appDirectory 'assets\sounds'
$pythonCommand = Get-Command python.exe -ErrorAction Stop
$pythonPath = $pythonCommand.Source
$releaseDirectory = Join-Path $appDirectory 'release'
$stageRoot = Join-Path $env:TEMP ('DailyPlanner-Stage-' + [guid]::NewGuid().ToString('N'))
$stageDist = Join-Path $stageRoot 'dist'
$workDirectory = Join-Path $stageRoot 'work'

& $pythonPath -m pip install --user pyinstaller pystray pillow
if ($LASTEXITCODE -ne 0) { throw 'Could not install packaging dependencies.' }

New-Item -ItemType Directory -Path $releaseDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $stageDist -Force | Out-Null

& $pythonPath -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name DailyPlanner `
    --icon (Join-Path $appDirectory 'dailyplanner.ico') `
    --distpath $stageDist `
    --workpath $workDirectory `
    --specpath $workDirectory `
    --collect-all pystray `
    --collect-all PIL `
    --hidden-import pystray._win32 `
    --add-data "$scheduleFile;." `
    --add-data "$settingsFile;." `
    --add-data "$soundDirectory;assets\sounds" `
    $entryPoint
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

$bundleSource = Join-Path $stageDist 'DailyPlanner'
$releaseBundle = Join-Path $releaseDirectory 'DailyPlanner'
if (Test-Path -LiteralPath $releaseBundle) {
    $resolvedRelease = (Resolve-Path -LiteralPath $releaseDirectory).Path
    $resolvedBundle = (Resolve-Path -LiteralPath $releaseBundle).Path
    if (-not $resolvedBundle.StartsWith($resolvedRelease + [IO.Path]::DirectorySeparatorChar,
                                         [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace a bundle outside the release directory: $resolvedBundle"
    }
    Remove-Item -LiteralPath $resolvedBundle -Recurse -Force
}
Copy-Item -Path $bundleSource -Destination $releaseBundle -Recurse -Force
Write-Output "Packaged app files: $releaseBundle"



