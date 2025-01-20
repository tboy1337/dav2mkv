function Get-VideoInfo {
    param(
        [Parameter(Mandatory)]
        [string]$InputFile
    )
    
    try {
        $cmd = @(
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            $InputFile
        )
        
        $result = & $cmd 2>&1
        return $result | ConvertFrom-Json
    }
    catch {
        Write-Warning "Could not read video info: $_"
        return $null
    }
}

function Convert-Video {
    param(
        [Parameter(Mandatory)]
        [string]$InputFile,
        
        [Parameter()]
        [string]$OutputFile,
        
        [Parameter()]
        [ValidateSet('mkv', 'mp4')]
        [string]$Container = 'mkv'
    )
    
    try {
        if (-not (Test-Path $InputFile)) {
            Write-Error "Input file '$InputFile' not found."
            return $false
        }

        # Create output filename if not provided
        if (-not $OutputFile) {
            $OutputFile = [System.IO.Path]::ChangeExtension($InputFile, $Container)
        }

        # Get video info before conversion
        Write-Host "Analyzing $InputFile..."
        $info = Get-VideoInfo -InputFile $InputFile
        
        if ($info) {
            # Print source video details
            Write-Host "`nSource video details:"
            $streams = @{
                video = 0
                audio = 0
                subtitle = 0
                data = 0
            }
            
            foreach ($stream in $info.streams) {
                $streamType = $stream.codec_type
                $streams[$streamType]++
                
                if ($streamType -eq 'video') {
                    Write-Host "Video: $($stream.codec_name) $($stream.width)x$($stream.height) @ $($stream.r_frame_rate)fps"
                }
                elseif ($streamType -eq 'audio') {
                    Write-Host "Audio: $($stream.codec_name) $($stream.channels) channels @ $($stream.sample_rate)Hz"
                }
            }
            
            Write-Host "`nStreams found: $($streams.video) video, $($streams.audio) audio, $($streams.subtitle) subtitle, $($streams.data) data"
        }

        # Perform the conversion
        Write-Host "`nConverting to $($Container.ToUpper())..."
        $cmd = @(
            'ffmpeg',
            '-i', $InputFile,
            '-c', 'copy',        # Copy all streams without re-encoding
            '-map', '0',         # Include all streams
            '-y',                # Overwrite output if exists
            $OutputFile
        )
        
        # Run conversion
        $process = Start-Process -FilePath $cmd[0] -ArgumentList $cmd[1..($cmd.Length-1)] -Wait -NoNewWindow -PassThru
        
        if ($process.ExitCode -eq 0) {
            Write-Host "Conversion successful! Output saved to: $OutputFile"
            
            # Verify output file exists and has size
            if (Test-Path $OutputFile) {
                $size = (Get-Item $OutputFile).Length / 1MB
                Write-Host "Output file verified ($([math]::Round($size, 1)) MB)"
                return $true
            }
            else {
                Write-Host "Error: Output file is missing or empty"
                return $false
            }
        }
        else {
            Write-Host "Conversion failed with error code: $($process.ExitCode)"
            return $false
        }
            
    }
    catch {
        Write-Error "An error occurred: $_"
        return $false
    }
}

function Convert-VideoDirectory {
    param(
        [Parameter(Mandatory)]
        [string]$InputDirectory,
        
        [Parameter()]
        [ValidateSet('mkv', 'mp4')]
        [string]$Container = 'mkv',
        
        [Parameter()]
        [int]$MaxConcurrent = 0
    )
    
    if (-not (Test-Path $InputDirectory)) {
        Write-Error "Directory '$InputDirectory' not found."
        return
    }

    # Look for common video file extensions
    $videoExtensions = @('.dav', '.avi', '.mp4', '.mkv', '.mov', '.wmv')
    $videoFiles = Get-ChildItem -Path $InputDirectory -File | 
                 Where-Object { $videoExtensions -contains $_.Extension }
    
    if (-not $videoFiles) {
        Write-Host "No video files found in the directory."
        return
    }
    
    if ($MaxConcurrent -le 0) {
        $MaxConcurrent = [Math]::Max(1, (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors - 1)
    }
        
    Write-Host "Found $($videoFiles.Count) video files to convert."
    Write-Host "Processing up to $MaxConcurrent files concurrently"
    
    $jobs = @()
    $completed = 0
    
    foreach ($file in $videoFiles) {
        # Wait if we've reached max concurrent jobs
        while ($jobs.Count -ge $MaxConcurrent) {
            $completed = Wait-ForCompletedJob -Jobs $jobs -Completed $completed -Total $videoFiles.Count
            $jobs = $jobs | Where-Object { $_.State -eq 'Running' }
        }
        
        # Start new conversion job
        $job = Start-Job -ScriptBlock {
            param($file, $container)
            . $using:Convert-Video
            Convert-Video -InputFile $file.FullName -Container $container
        } -ArgumentList $file, $Container
        
        $jobs += $job
    }
    
    # Wait for remaining jobs
    while ($jobs) {
        $completed = Wait-ForCompletedJob -Jobs $jobs -Completed $completed -Total $videoFiles.Count
        $jobs = $jobs | Where-Object { $_.State -eq 'Running' }
    }
}

function Wait-ForCompletedJob {
    param($Jobs, $Completed, $Total)
    
    $finishedJob = $Jobs | Wait-Job -Any
    if ($finishedJob) {
        $result = Receive-Job -Job $finishedJob
        Remove-Job -Job $finishedJob
        $Completed++
        Write-Host "Progress: $Completed/$Total files processed"
    }
    return $Completed
}

# Parse command line arguments
param(
    [Parameter(ParameterSetName='File')]
    [string]$File,
    
    [Parameter(ParameterSetName='Directory')]
    [string]$Directory,
    
    [Parameter(ParameterSetName='File')]
    [string]$Output,
    
    [Parameter()]
    [int]$Concurrent = 0,
    
    [Parameter()]
    [ValidateSet('mkv', 'mp4')]
    [string]$Container = 'mkv'
)

if ($File) {
    Convert-Video -InputFile $File -OutputFile $Output -Container $Container
}
elseif ($Directory) {
    Convert-VideoDirectory -InputDirectory $Directory -Container $Container -MaxConcurrent $Concurrent
}
else {
    Write-Host "Please specify either -File or -Directory parameter."
}
