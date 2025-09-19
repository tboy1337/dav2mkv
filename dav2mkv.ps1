#!/usr/bin/env pwsh
<#
.SYNOPSIS
    DAV Video Converter - PowerShell Edition

.DESCRIPTION
    A robust, production-ready tool for converting DAV video files to MKV or MP4
    while maintaining perfect quality through stream copying. This tool uses FFmpeg
    to perform direct stream copy operations, ensuring no quality loss during conversion.

    Features:
    - Direct stream copy (no quality loss)
    - Maintains all original streams (video, audio, subtitles)
    - Batch processing with parallel conversion support
    - Comprehensive logging and error handling
    - Thread-safe operations
    - Cross-platform compatibility

.PARAMETER File
    Single video file to convert

.PARAMETER Directory
    Directory containing video files to convert

.PARAMETER Output
    Output file or directory name

.PARAMETER Container
    Output container format (mkv or mp4). Default: mkv

.PARAMETER Overwrite
    Overwrite existing output files. Default: $true

.PARAMETER NoOverwrite
    Do not overwrite existing output files

.PARAMETER Concurrent
    Maximum number of concurrent conversions for directory processing

.PARAMETER Recursive
    Process directories recursively

.PARAMETER LogLevel
    Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO

.PARAMETER LogFile
    Log file path (optional)

.PARAMETER Version
    Display version information

.EXAMPLE
    .\dav2mkv.ps1 -File input.dav -Output output.mkv

.EXAMPLE
    .\dav2mkv.ps1 -Directory .\videos -Container mp4 -Recursive

.EXAMPLE
    .\dav2mkv.ps1 -File video.avi -LogLevel DEBUG -LogFile conversion.log
#>

[CmdletBinding(DefaultParameterSetName = 'File')]
param(
    [Parameter(ParameterSetName = 'File', Mandatory = $true)]
    [string]$File,
    
    [Parameter(ParameterSetName = 'Directory', Mandatory = $true)]
    [string]$Directory,
    
    [Parameter(ParameterSetName = 'Version', Mandatory = $true)]
    [switch]$Version,
    
    [Parameter(ParameterSetName = 'File')]
    [Parameter(ParameterSetName = 'Directory')]
    [string]$Output,
    
    [Parameter(ParameterSetName = 'File')]
    [Parameter(ParameterSetName = 'Directory')]
    [ValidateSet('mkv', 'mp4')]
    [string]$Container = 'mkv',
    
    [Parameter(ParameterSetName = 'File')]
    [Parameter(ParameterSetName = 'Directory')]
    [switch]$Overwrite,
    
    [Parameter(ParameterSetName = 'File')]
    [Parameter(ParameterSetName = 'Directory')]
    [switch]$NoOverwrite,
    
    [Parameter(ParameterSetName = 'File')]
    [Parameter(ParameterSetName = 'Directory')]
    [int]$Concurrent,
    
    [Parameter(ParameterSetName = 'Directory')]
    [switch]$Recursive,
    
    [Parameter()]
    [ValidateSet('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')]
    [string]$LogLevel = 'INFO',
    
    [Parameter()]
    [string]$LogFile
)

# Script version
$SCRIPT_VERSION = "2.0.0"

# Global variables for thread-safe logging
$Global:LogLock = [System.Threading.Mutex]::new($false, "DAV2MKVLogMutex")
$Global:Logger = $null
$Global:LogLevelValue = 0

# Custom exception classes
class DAVConverterException : System.Exception {
    DAVConverterException([string] $message) : base($message) {}
}

class FFmpegNotFoundException : DAVConverterException {
    FFmpegNotFoundException([string] $message) : base($message) {}
}

class VideoProcessingException : DAVConverterException {
    VideoProcessingException([string] $message) : base($message) {}
}

# Video information class
class VideoInfo {
    [hashtable] $RawData
    [array] $Streams
    [hashtable] $FormatInfo
    [hashtable] $StreamCounts

    VideoInfo([hashtable] $data) {
        $this.RawData = $data
        $this.Streams = $data.streams
        $this.FormatInfo = $data.format

        # Initialize stream counts
        $this.StreamCounts = @{
            video = 0
            audio = 0
            subtitle = 0
            data = 0
            unknown = 0
        }

        # Count streams by type
        foreach ($stream in $this.Streams) {
            $streamType = $stream.codec_type
            if ($this.StreamCounts.ContainsKey($streamType)) {
                $this.StreamCounts[$streamType]++
            } else {
                $this.StreamCounts['unknown']++
            }
        }
    }

    [array] GetVideoStreams() {
        return $this.Streams | Where-Object { $_.codec_type -eq 'video' }
    }

    [array] GetAudioStreams() {
        return $this.Streams | Where-Object { $_.codec_type -eq 'audio' }
    }

    [hashtable] GetPrimaryVideoInfo() {
        $videoStreams = $this.GetVideoStreams()
        if ($videoStreams.Count -gt 0) {
            return $videoStreams[0]
        }
        return @{}
    }

    [hashtable] GetPrimaryAudioInfo() {
        $audioStreams = $this.GetAudioStreams()
        if ($audioStreams.Count -gt 0) {
            return $audioStreams[0]
        }
        return @{}
    }
}

# Video converter class
class VideoConverter {
    [object] $Logger
    [System.Threading.Mutex] $ConversionLock
    [hashtable] $Stats
    [System.Threading.Mutex] $StatsLock

    VideoConverter([object] $logger) {
        $this.Logger = $logger
        $this.ConversionLock = [System.Threading.Mutex]::new($false, "ConversionMutex")
        $this.StatsLock = [System.Threading.Mutex]::new($false, "StatsMutex")
        $this.Stats = @{
            conversions_attempted = 0
            conversions_successful = 0
            conversions_failed = 0
            total_processing_time = 0.0
        }
    }

    [VideoInfo] GetVideoInfo([string] $inputFile) {
        Write-LogMessage "DEBUG" "Getting video info for: $inputFile"

        if (-not (Test-Path $inputFile -PathType Leaf)) {
            Write-LogMessage "ERROR" "Input file does not exist: $inputFile"
            return $null
        }

        $cmd = @(
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            $inputFile
        )

        try {
            Write-LogMessage "DEBUG" "Running command: $($cmd -join ' ')"
            
            $result = Start-Process -FilePath 'ffprobe' -ArgumentList $cmd[1..($cmd.Length-1)] `
                -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) `
                -RedirectStandardError ([System.IO.Path]::GetTempFileName()) `
                -Wait -PassThru -NoNewWindow

            $stdoutFile = $result.StartInfo.RedirectStandardOutput
            $stderrFile = $result.StartInfo.RedirectStandardError

            if ($result.ExitCode -ne 0) {
                $errorOutput = Get-Content $stderrFile -Raw
                Write-LogMessage "ERROR" "ffprobe failed with return code $($result.ExitCode): $errorOutput"
                Remove-Item $stdoutFile, $stderrFile -ErrorAction SilentlyContinue
                return $null
            }

            $jsonOutput = Get-Content $stdoutFile -Raw
            Remove-Item $stdoutFile, $stderrFile -ErrorAction SilentlyContinue

            $data = $jsonOutput | ConvertFrom-Json -AsHashtable
            $videoInfo = [VideoInfo]::new($data)

            Write-LogMessage "DEBUG" "Successfully parsed video info for $inputFile"
            return $videoInfo

        } catch {
            Write-LogMessage "ERROR" "Unexpected error getting video info: $($_.Exception.Message)"
            return $null
        }
    }

    [void] UpdateStats([bool] $attempted, [bool] $successful, [double] $processingTime) {
        $null = $this.StatsLock.WaitOne()
        try {
            if ($attempted) {
                $this.Stats.conversions_attempted++
            }
            if ($successful) {
                $this.Stats.conversions_successful++
            } else {
                $this.Stats.conversions_failed++
            }
            $this.Stats.total_processing_time += $processingTime
        } finally {
            $this.StatsLock.ReleaseMutex()
        }
    }

    [bool] ConvertVideo([string] $inputFile, [string] $outputFile, [string] $container, [bool] $overwrite) {
        $startTime = Get-Date
        
        # Thread-safe logging of conversion attempt
        $null = $this.ConversionLock.WaitOne()
        try {
            Write-LogMessage "INFO" "Starting conversion of: $inputFile"
        } finally {
            $this.ConversionLock.ReleaseMutex()
        }

        $this.UpdateStats($true, $false, 0.0)

        try {
            # Validate input
            if (-not (Test-Path $inputFile -PathType Leaf)) {
                throw [VideoProcessingException]::new("Input file not found: $inputFile")
            }

            # Validate container format
            if ($container -notin @('mkv', 'mp4')) {
                throw [VideoProcessingException]::new("Unsupported container format: $container")
            }

            # Create output filename if not provided
            if (-not $outputFile) {
                $outputFile = [System.IO.Path]::ChangeExtension($inputFile, $container)
            }

            # Check if output already exists
            if ((Test-Path $outputFile) -and (-not $overwrite)) {
                Write-LogMessage "WARNING" "Output file exists and overwrite disabled: $outputFile"
                return $false
            }

            # Get and log video information
            Write-LogMessage "INFO" "Analyzing video file: $inputFile"
            $videoInfo = $this.GetVideoInfo($inputFile)

            if ($videoInfo) {
                $this.LogVideoInfo($videoInfo)
            } else {
                Write-LogMessage "WARNING" "Could not retrieve video information"
            }

            # Ensure output directory exists
            $outputDir = Split-Path $outputFile -Parent
            if ($outputDir -and (-not (Test-Path $outputDir))) {
                New-Item -Path $outputDir -ItemType Directory -Force | Out-Null
            }

            # Perform the conversion
            Write-LogMessage "INFO" "Converting to $($container.ToUpper()): $inputFile -> $outputFile"

            $ffmpegArgs = @(
                '-i', $inputFile,
                '-c', 'copy',  # Copy all streams without re-encoding
                '-map', '0',   # Include all streams from input
                '-avoid_negative_ts', 'make_zero',  # Handle timestamp issues
                '-fflags', '+genpts'  # Generate presentation timestamps
            )

            if ($overwrite) {
                $ffmpegArgs += '-y'  # Overwrite output if exists
            } else {
                $ffmpegArgs += '-n'  # Never overwrite
            }

            $ffmpegArgs += $outputFile

            Write-LogMessage "DEBUG" "Running FFmpeg command: ffmpeg $($ffmpegArgs -join ' ')"

            # Run conversion
            $process = Start-Process -FilePath 'ffmpeg' -ArgumentList $ffmpegArgs `
                -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) `
                -RedirectStandardError ([System.IO.Path]::GetTempFileName()) `
                -Wait -PassThru -NoNewWindow

            $processingTime = ((Get-Date) - $startTime).TotalSeconds
            
            $stderrFile = $process.StartInfo.RedirectStandardError

            if ($process.ExitCode -eq 0) {
                # Verify output file
                if ($this.VerifyOutputFile($outputFile, $inputFile)) {
                    Write-LogMessage "INFO" "Conversion successful: $outputFile ($([math]::Round($processingTime, 2))s)"
                    $this.UpdateStats($false, $true, $processingTime)
                    Remove-Item $process.StartInfo.RedirectStandardOutput, $stderrFile -ErrorAction SilentlyContinue
                    return $true
                } else {
                    Write-LogMessage "ERROR" "Output file verification failed"
                    $this.UpdateStats($false, $false, $processingTime)
                    Remove-Item $process.StartInfo.RedirectStandardOutput, $stderrFile -ErrorAction SilentlyContinue
                    return $false
                }
            } else {
                $errorMsg = Get-Content $stderrFile -Raw
                Write-LogMessage "ERROR" "FFmpeg conversion failed (code $($process.ExitCode)): $errorMsg"
                $this.UpdateStats($false, $false, $processingTime)
                Remove-Item $process.StartInfo.RedirectStandardOutput, $stderrFile -ErrorAction SilentlyContinue
                return $false
            }

        } catch {
            $processingTime = ((Get-Date) - $startTime).TotalSeconds
            Write-LogMessage "ERROR" "Conversion failed with exception: $($_.Exception.Message)"
            $this.UpdateStats($false, $false, $processingTime)
            return $false
        }
    }

    [void] LogVideoInfo([VideoInfo] $videoInfo) {
        Write-LogMessage "INFO" "=== Source Video Details ==="

        # Primary video stream info
        $videoStream = $videoInfo.GetPrimaryVideoInfo()
        if ($videoStream.Count -gt 0) {
            $codec = if ($videoStream.codec_name) { $videoStream.codec_name } else { 'unknown' }
            $width = if ($videoStream.width) { $videoStream.width } else { '?' }
            $height = if ($videoStream.height) { $videoStream.height } else { '?' }
            $fps = if ($videoStream.r_frame_rate) { $videoStream.r_frame_rate } else { '?' }
            $bitrate = if ($videoStream.bit_rate) { $videoStream.bit_rate } else { 'unknown' }

            Write-LogMessage "INFO" "Video: $codec ${width}x${height} @ ${fps}fps, bitrate: $bitrate"
        }

        # Primary audio stream info
        $audioStream = $videoInfo.GetPrimaryAudioInfo()
        if ($audioStream.Count -gt 0) {
            $codec = if ($audioStream.codec_name) { $audioStream.codec_name } else { 'unknown' }
            $channels = if ($audioStream.channels) { $audioStream.channels } else { '?' }
            $sampleRate = if ($audioStream.sample_rate) { $audioStream.sample_rate } else { '?' }
            $bitrate = if ($audioStream.bit_rate) { $audioStream.bit_rate } else { 'unknown' }

            Write-LogMessage "INFO" "Audio: $codec $channels channels @ ${sampleRate}Hz, bitrate: $bitrate"
        }

        # Stream summary
        $counts = $videoInfo.StreamCounts
        Write-LogMessage "INFO" "Streams: $($counts.video) video, $($counts.audio) audio, $($counts.subtitle) subtitle, $($counts.data) data"

        # File info
        $formatInfo = $videoInfo.FormatInfo
        $duration = if ($formatInfo.duration) { $formatInfo.duration } else { 'unknown' }
        $size = if ($formatInfo.size) { $formatInfo.size } else { 'unknown' }
        
        if ($size -ne 'unknown' -and $size -match '^\d+$') {
            try {
                $sizeMB = [math]::Round([long]$size / (1024 * 1024), 1)
                Write-LogMessage "INFO" "Duration: ${duration}s, Size: $sizeMB MB"
            } catch {
                Write-LogMessage "INFO" "Duration: ${duration}s, Size: $size"
            }
        } else {
            Write-LogMessage "INFO" "Duration: ${duration}s, Size: $size"
        }

        Write-LogMessage "INFO" "=== End Video Details ==="
    }

    [bool] VerifyOutputFile([string] $outputFile, [string] $inputFile) {
        try {
            if (-not (Test-Path $outputFile -PathType Leaf)) {
                Write-LogMessage "ERROR" "Output file does not exist: $outputFile"
                return $false
            }

            $outputSize = (Get-Item $outputFile).Length
            if ($outputSize -eq 0) {
                Write-LogMessage "ERROR" "Output file is empty: $outputFile"
                return $false
            }

            $inputSize = (Get-Item $inputFile).Length
            $sizeRatio = if ($inputSize -gt 0) { $outputSize / $inputSize } else { 0 }

            # Output should be within reasonable size range (stream copy should be similar size)
            if ($sizeRatio -lt 0.8 -or $sizeRatio -gt 1.2) {
                Write-LogMessage "WARNING" "Output file size differs significantly from input (ratio: $([math]::Round($sizeRatio, 2)))"
            }

            $outputSizeMB = [math]::Round($outputSize / (1024 * 1024), 1)
            Write-LogMessage "INFO" "Output verified: $outputSizeMB MB"
            return $true

        } catch {
            Write-LogMessage "ERROR" "Output file verification failed: $($_.Exception.Message)"
            return $false
        }
    }

    [hashtable] GetStats() {
        $null = $this.StatsLock.WaitOne()
        try {
            return $this.Stats.Clone()
        } finally {
            $this.StatsLock.ReleaseMutex()
        }
    }
}

# Batch converter class
class BatchConverter {
    [VideoConverter] $Converter
    [object] $Logger
    [int] $MaxWorkers
    [string[]] $VideoExtensions

    BatchConverter([VideoConverter] $converter, [int] $maxWorkers) {
        $this.Converter = $converter
        $this.Logger = $converter.Logger
        $this.MaxWorkers = if ($maxWorkers -gt 0) { $maxWorkers } else { [System.Environment]::ProcessorCount - 1 }
        $this.MaxWorkers = [Math]::Max(1, $this.MaxWorkers)

        # Supported video file extensions
        $this.VideoExtensions = @(
            '.dav', '.avi', '.mp4', '.mkv', '.mov', '.wmv', '.flv', '.webm',
            '.m4v', '.3gp', '.3g2', '.asf', '.rm', '.rmvb', '.vob', '.ts'
        )
    }

    [string[]] FindVideoFiles([string] $directory, [bool] $recursive) {
        if (-not (Test-Path $directory -PathType Container)) {
            Write-LogMessage "ERROR" "Directory does not exist: $directory"
            return @()
        }

        $videoFiles = @()

        try {
            if ($recursive) {
                $files = Get-ChildItem -Path $directory -File -Recurse
            } else {
                $files = Get-ChildItem -Path $directory -File
            }

            foreach ($file in $files) {
                if ($file.Extension.ToLower() -in $this.VideoExtensions) {
                    $videoFiles += $file.FullName
                    Write-LogMessage "DEBUG" "Found video file: $($file.FullName)"
                }
            }

            Write-LogMessage "INFO" "Found $($videoFiles.Count) video files in $directory"
            return $videoFiles | Sort-Object

        } catch {
            Write-LogMessage "ERROR" "Error scanning directory ${directory}: $($_.Exception.Message)"
            return @()
        }
    }

    [hashtable] ConvertDirectory([string] $inputDir, [string] $outputDir, [string] $container, [bool] $recursive, [bool] $overwrite, [string] $logLevel, [string] $logFile) {
        if (-not $outputDir) {
            $outputDir = $inputDir
        } elseif (-not (Test-Path $outputDir)) {
            New-Item -Path $outputDir -ItemType Directory -Force | Out-Null
        }

        Write-LogMessage "INFO" "Starting batch conversion: $inputDir -> $outputDir"
        Write-LogMessage "INFO" "Container: $container, Workers: $($this.MaxWorkers)"

        # Find all video files
        $videoFiles = $this.FindVideoFiles($inputDir, $recursive)

        if ($videoFiles.Count -eq 0) {
            Write-LogMessage "WARNING" "No video files found to convert"
            return @{ total = 0; successful = 0; failed = 0 }
        }

        # Process files with parallel jobs
        $results = @{ total = $videoFiles.Count; successful = 0; failed = 0 }

        Write-LogMessage "INFO" "Processing $($videoFiles.Count) files with $($this.MaxWorkers) workers"

        # Create script block for parallel processing
        $scriptBlock = {
            param($videoFile, $inputDir, $outputDir, $container, $overwrite, $LogLevel, $LogFile)
            
            # Re-initialize logging in job context
            Initialize-Logging -LogLevel $LogLevel -LogFile $LogFile
            
            # Create converter instance
            $converter = [VideoConverter]::new($Global:Logger)
            
            # Calculate output path
            if ($outputDir -ne $inputDir) {
                $relativePath = $videoFile.Substring($inputDir.Length).TrimStart('\', '/')
                $outputFile = Join-Path $outputDir ([System.IO.Path]::ChangeExtension($relativePath, $container))
            } else {
                $outputFile = [System.IO.Path]::ChangeExtension($videoFile, $container)
            }
            
            # Perform conversion
            $success = $converter.ConvertVideo($videoFile, $outputFile, $container, $overwrite)
            
            return @{
                File = $videoFile
                Success = $success
            }
        }

        # Process files in batches to avoid overwhelming the system
        $batchSize = $this.MaxWorkers
        $completed = 0

        for ($i = 0; $i -lt $videoFiles.Count; $i += $batchSize) {
            $batch = $videoFiles[$i..[Math]::Min($i + $batchSize - 1, $videoFiles.Count - 1)]
            
            $jobs = foreach ($videoFile in $batch) {
                Start-Job -ScriptBlock $scriptBlock -ArgumentList $videoFile, $inputDir, $outputDir, $container, $overwrite, $logLevel, $logFile
            }

            # Wait for batch to complete
            $jobs | Wait-Job | ForEach-Object {
                $result = $_ | Receive-Job
                $completed++

                if ($result.Success) {
                    $results.successful++
                } else {
                    $results.failed++
                }

                Write-LogMessage "INFO" "Progress: $completed/$($videoFiles.Count) files processed ($($results.successful) successful, $($results.failed) failed)"
                
                Remove-Job $_
            }
        }

        Write-LogMessage "INFO" "Batch conversion completed: $results"
        return $results
    }
}

# Logging functions
function Initialize-Logging {
    param(
        [string] $LogLevel = 'INFO',
        [string] $LogFile = $null
    )

    $Global:LogLevelValue = switch ($LogLevel.ToUpper()) {
        'DEBUG' { 0 }
        'INFO' { 1 }
        'WARNING' { 2 }
        'ERROR' { 3 }
        'CRITICAL' { 4 }
        default { 1 }
    }

    if ($LogFile) {
        $logDir = Split-Path $LogFile -Parent
        if ($logDir -and (-not (Test-Path $logDir))) {
            New-Item -Path $logDir -ItemType Directory -Force | Out-Null
        }
    }

    $Global:Logger = @{
        LogLevel = $LogLevel
        LogFile = $LogFile
    }

    Write-LogMessage "INFO" "Logging initialized with level: $LogLevel"
    if ($LogFile) {
        Write-LogMessage "INFO" "Logging to file: $LogFile"
    }
}

function Write-LogMessage {
    param(
        [string] $Level,
        [string] $Message
    )

    $levelValue = switch ($Level.ToUpper()) {
        'DEBUG' { 0 }
        'INFO' { 1 }
        'WARNING' { 2 }
        'ERROR' { 3 }
        'CRITICAL' { 4 }
        default { 1 }
    }

    if ($levelValue -lt $Global:LogLevelValue) {
        return
    }

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "$timestamp - $Level - $Message"

    # Thread-safe logging
    $null = $Global:LogLock.WaitOne()
    try {
        # Console output
        switch ($Level.ToUpper()) {
            'DEBUG' { Write-Host $logMessage -ForegroundColor Gray }
            'INFO' { Write-Host $logMessage -ForegroundColor White }
            'WARNING' { Write-Host $logMessage -ForegroundColor Yellow }
            'ERROR' { Write-Host $logMessage -ForegroundColor Red }
            'CRITICAL' { Write-Host $logMessage -ForegroundColor Magenta }
        }

        # File output
        if ($Global:Logger.LogFile) {
            try {
                $detailedMessage = "$timestamp - dav2mkv - $Level - [dav2mkv.ps1] - $Message"
                Add-Content -Path $Global:Logger.LogFile -Value $detailedMessage -Encoding UTF8
            } catch {
                Write-Warning "Failed to write to log file: $($_.Exception.Message)"
            }
        }
    } finally {
        $Global:LogLock.ReleaseMutex()
    }
}

function Test-FFmpegAvailability {
    try {
        # Check ffmpeg
        $ffmpegResult = & ffmpeg -version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $versionLine = ($ffmpegResult -split "`n")[0]
            Write-LogMessage "INFO" "FFmpeg found: $versionLine"

            # Also check ffprobe
            & ffprobe -version 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return @{ Available = $true; Version = $versionLine }
            } else {
                Write-LogMessage "ERROR" "FFprobe not found, but FFmpeg is available"
                return @{ Available = $false; Version = $null }
            }
        } else {
            Write-LogMessage "ERROR" "FFmpeg check failed"
            return @{ Available = $false; Version = $null }
        }
    } catch {
        Write-LogMessage "ERROR" "FFmpeg not found in system PATH: $($_.Exception.Message)"
        return @{ Available = $false; Version = $null }
    }
}

# Main execution function
function Invoke-Main {
    param(
        [string] $File,
        [string] $Directory, 
        [string] $Output,
        [string] $Container,
        [bool] $Overwrite,
        [bool] $NoOverwrite,
        [int] $Concurrent,
        [bool] $Recursive,
        [string] $LogLevel,
        [string] $LogFile,
        [bool] $Version,
        [string] $ParameterSetName
    )
    
    try {
        # Handle version request
        if ($Version) {
            Write-Host "DAV Video Converter (PowerShell Edition) $SCRIPT_VERSION"
            return 0
        }

        # Handle Overwrite parameter logic
        if ($NoOverwrite) {
            $Overwrite = $false
        } elseif (-not $PSBoundParameters.ContainsKey('Overwrite')) {
            $Overwrite = $true  # Default to true if neither switch is specified
        }

        # Initialize logging
        Initialize-Logging -LogLevel $LogLevel -LogFile $LogFile

        # Log system information
        Write-LogMessage "INFO" "=== DAV Video Converter Starting ==="
        Write-LogMessage "INFO" "PowerShell version: $($PSVersionTable.PSVersion)"
        Write-LogMessage "INFO" "Platform: $([System.Environment]::OSVersion)"
        Write-LogMessage "INFO" "Architecture: $([System.Environment]::GetEnvironmentVariable('PROCESSOR_ARCHITECTURE'))"
        Write-LogMessage "INFO" "CPU count: $([System.Environment]::ProcessorCount)"

        # Check FFmpeg availability
        $ffmpegCheck = Test-FFmpegAvailability
        if (-not $ffmpegCheck.Available) {
            Write-LogMessage "CRITICAL" "FFmpeg is not available. Please install FFmpeg and ensure it's in your PATH."
            throw [FFmpegNotFoundException]::new("FFmpeg not found in system PATH")
        }

        Write-LogMessage "INFO" "Using $($ffmpegCheck.Version)"

        # Initialize converter
        $converter = [VideoConverter]::new($Global:Logger)

        # Process based on parameter set
        if ($ParameterSetName -eq 'File') {
            # Single file conversion
            Write-LogMessage "INFO" "Converting single file: $File"
            $success = $converter.ConvertVideo($File, $Output, $Container, $Overwrite)

            # Log final stats
            $stats = $converter.GetStats()
            Write-LogMessage "INFO" "Conversion stats: $($stats | ConvertTo-Json -Compress)"

            return if ($success) { 0 } else { 1 }
        } else {
            # Directory batch conversion
            $maxWorkers = if ($Concurrent -gt 0) { $Concurrent } else { 0 }
            if ($maxWorkers -gt 0) {
                Write-LogMessage "INFO" "Using $maxWorkers worker threads"
            }

            $batchConverter = [BatchConverter]::new($converter, $maxWorkers)

            $results = $batchConverter.ConvertDirectory($Directory, $Output, $Container, $Recursive, $Overwrite, $LogLevel, $LogFile)

            # Log final stats
            $converterStats = $converter.GetStats()
            Write-LogMessage "INFO" "Final results: $($results | ConvertTo-Json -Compress)"
            Write-LogMessage "INFO" "Converter stats: $($converterStats | ConvertTo-Json -Compress)"

            # Return appropriate exit code
            if ($results.failed -eq 0) {
                Write-LogMessage "INFO" "All conversions completed successfully"
                return 0
            } elseif ($results.successful -gt 0) {
                Write-LogMessage "WARNING" "Partial success: $($results.successful) succeeded, $($results.failed) failed"
                return 2
            } else {
                Write-LogMessage "ERROR" "All conversions failed"
                return 1
            }
        }

    } catch [FFmpegNotFoundException] {
        return 127
    } catch {
        Write-LogMessage "CRITICAL" "Unexpected error: $($_.Exception.Message)"
        Write-LogMessage "DEBUG" $_.ScriptStackTrace
        return 1
    } finally {
        Write-LogMessage "INFO" "=== DAV Video Converter Finished ==="
        
        # Clean up mutexes
        if ($Global:LogLock) {
            $Global:LogLock.Dispose()
        }
    }
}

# Script entry point
if ($MyInvocation.InvocationName -ne '.') {
    exit (Invoke-Main -File $File -Directory $Directory -Output $Output -Container $Container `
        -Overwrite $Overwrite -NoOverwrite $NoOverwrite -Concurrent $Concurrent `
        -Recursive $Recursive -LogLevel $LogLevel -LogFile $LogFile -Version $Version `
        -ParameterSetName $PSCmdlet.ParameterSetName)
}
