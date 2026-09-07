param(
    [string]$Destination = "benchmarks\raw\official",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "."
$destinationPath = Join-Path $root $Destination
New-Item -ItemType Directory -Force -Path $destinationPath | Out-Null
$destinationFullPath = [IO.Path]::GetFullPath($destinationPath).TrimEnd([IO.Path]::DirectorySeparatorChar)

function Assert-ChildPath([string]$Candidate) {
    $candidateFullPath = [IO.Path]::GetFullPath($Candidate).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $prefix = $destinationFullPath + [IO.Path]::DirectorySeparatorChar
    if (-not $candidateFullPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing recursive operation outside benchmark cache: $candidateFullPath"
    }
}

$archives = @(
    @{ Year = 2021; Name = "CUMCM2021Problems.rar"; Url = "https://www.mcm.edu.cn/upload_cn/node/669/HtbJEt9Nb655e46bebfa2a66ec63f940e2da156b.rar" },
    @{ Year = 2022; Name = "CUMCM2022Problems.rar"; Url = "https://www.mcm.edu.cn/upload_cn/node/670/5eWlbmTt28f88a0815a79d555da8b7072f971633.rar" },
    @{ Year = 2023; Name = "CUMCM2023Problems.rar"; Url = "https://www.mcm.edu.cn/upload_cn/node/690/Y20WPner9fa62862794e6dc82731a5561ce1132f.rar" },
    @{ Year = 2024; Name = "CUMCM2024Problems.zip"; Url = "https://www.mcm.edu.cn/upload_cn/node/725/pmkWxf8H9cfe9984c1a1a5b1263e5dd3b5596ed5.zip" },
    @{ Year = 2025; Name = "CUMCM2025Problems.zip"; Url = "https://www.mcm.edu.cn/upload_cn/node/759/SvpohSGacdffe718bcaa3b6e835c03ae3461cab1.zip" }
)

$checksums = @()
foreach ($archive in $archives) {
    $archivePath = Join-Path $destinationPath $archive.Name
    if ($Force -or -not (Test-Path -LiteralPath $archivePath)) {
        Write-Host "Downloading $($archive.Year): $($archive.Url)"
        Invoke-WebRequest -Uri $archive.Url -OutFile $archivePath
    }
    else {
        Write-Host "Using cached archive: $archivePath"
    }

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
    $checksums += [ordered]@{
        year = $archive.Year
        file = $archive.Name
        source_url = $archive.Url
        bytes = (Get-Item -LiteralPath $archivePath).Length
        sha256 = $hash
    }

    if ([IO.Path]::GetExtension($archivePath).ToLowerInvariant() -eq ".zip") {
        $extractPath = Join-Path $destinationPath ([string]$archive.Year)
        if ($Force -and (Test-Path -LiteralPath $extractPath)) {
            Assert-ChildPath $extractPath
            Remove-Item -Recurse -Force -LiteralPath $extractPath
        }
        if (-not (Test-Path -LiteralPath $extractPath)) {
            Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath
        }
    }
}

$checksumPath = Join-Path $destinationPath "checksums.json"
$checksums | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -LiteralPath $checksumPath
Write-Host "Saved checksums: $checksumPath"

$rarArchives = $archives | Where-Object { $_.Name.EndsWith(".rar") }
$sevenZip = Get-Command 7z,7zz -ErrorAction SilentlyContinue | Select-Object -First 1
if ($sevenZip) {
    foreach ($archive in $rarArchives) {
        $archivePath = Join-Path $destinationPath $archive.Name
        $extractPath = Join-Path $destinationPath ([string]$archive.Year)
        New-Item -ItemType Directory -Force -Path $extractPath | Out-Null
        & $sevenZip.Source x "-o$extractPath" -y $archivePath | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "7-Zip failed to extract $archivePath" }
    }
}
else {
    $tar = Get-Command tar -ErrorAction SilentlyContinue
    if ($tar) {
        foreach ($archive in $rarArchives) {
            $archivePath = Join-Path $destinationPath $archive.Name
            $extractPath = Join-Path $destinationPath ([string]$archive.Year)
            New-Item -ItemType Directory -Force -Path $extractPath | Out-Null
            & $tar.Source -xf $archivePath -C $extractPath
            if ($LASTEXITCODE -ne 0) { throw "tar failed to extract $archivePath" }
        }
    }
    else {
        Write-Warning "2021-2023 RAR archives are downloaded but not extracted because neither 7-Zip nor tar is available."
    }
}

# The 2022 and 2023 official bundles contain a second C-problem RAR layer.
$tarForNested = Get-Command tar -ErrorAction SilentlyContinue
$sevenZipForNested = Get-Command 7z,7zz -ErrorAction SilentlyContinue | Select-Object -First 1
foreach ($year in 2022,2023) {
    $yearPath = Join-Path $destinationPath ([string]$year)
    $nestedArchive = Get-ChildItem -LiteralPath $yearPath -Filter "C*.rar" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $nestedArchive) { continue }
    $nestedDestination = Join-Path $yearPath "C_problem"
    if (-not (Test-Path -LiteralPath $nestedDestination)) {
        New-Item -ItemType Directory -Force -Path $nestedDestination | Out-Null
        if ($sevenZipForNested) {
            & $sevenZipForNested.Source x "-o$nestedDestination" -y $nestedArchive.FullName | Out-Null
        }
        elseif ($tarForNested) {
            & $tarForNested.Source -xf $nestedArchive.FullName -C $nestedDestination
        }
        else {
            throw "Cannot extract nested C-problem archive for $year"
        }
        if ($LASTEXITCODE -ne 0) { throw "Failed to extract nested C-problem archive for $year" }
    }
}
