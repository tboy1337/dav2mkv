@echo off
setlocal EnableDelayedExpansion
REM ============================================================================
REM DAV Video Converter - Windows Batch Script Version
REM 
REM A robust batch script for converting DAV video files to MKV or MP4
REM while maintaining perfect quality through stream copying using FFmpeg.
REM 
REM Features:
REM - Direct stream copy (no quality loss)
REM - Maintains all original streams (video, audio, subtitles)
REM - Batch processing support
REM - Comprehensive logging and error handling
REM - Cross-platform compatibility
REM 
REM Author: Based on dav2mkv.py Python script
REM Version: 2.0.0
REM ============================================================================

REM Initialize variables
set "SCRIPT_NAME=DAV Video Converter"
set "SCRIPT_VERSION=2.0.0"
set "INPUT_FILE="
set "INPUT_DIR="
set "OUTPUT_PATH="
set "CONTAINER=mkv"
set "OVERWRITE=1"
set "RECURSIVE=0"
set "LOG_LEVEL=INFO"
set "LOG_FILE="
set "MAX_WORKERS=0"
set "HELP_REQUESTED=0"
set "VERSION_REQUESTED=0"

REM Statistics tracking
set /a "TOTAL_FILES=0"
set /a "SUCCESS_COUNT=0"
set /a "FAILED_COUNT=0"
set "START_TIME="

REM Supported video file extensions
set "VIDEO_EXTENSIONS=.dav .avi .mp4 .mkv .mov .wmv .flv .webm .m4v .3gp .3g2 .asf .rm .rmvb .vob .ts"

REM Colors for console output
set "COLOR_RESET="
set "COLOR_INFO=echo"
set "COLOR_SUCCESS=echo"
set "COLOR_WARNING=echo"
set "COLOR_ERROR=echo"

REM Call main function and exit
call :main %*
exit /b %errorlevel%

REM ============================================================================
REM FUNCTION DEFINITIONS
REM ============================================================================

:show_usage
echo.
echo %SCRIPT_NAME% v%SCRIPT_VERSION%
echo Convert video files using direct stream copy for maximum quality.
echo.
echo Usage: %~n0 [OPTIONS]
echo.
echo Input Options (required, mutually exclusive):
echo   -f FILE          Single video file to convert
echo   -d DIRECTORY     Directory containing video files to convert
echo.
echo Output Options:
echo   -o OUTPUT        Output file or directory name
echo.
echo Conversion Options:
echo   --container FORMAT    Output container format (mkv^|mp4, default: mkv)
echo   --overwrite          Overwrite existing output files (default)
echo   --no-overwrite       Do not overwrite existing output files
echo.
echo Processing Options:
echo   --recursive          Process directories recursively
echo   -c NUMBER            Maximum number of files to process (sequential in batch)
echo.
echo Logging Options:
echo   --log-level LEVEL    Set logging level (DEBUG^|INFO^|WARNING^|ERROR, default: INFO)
echo   --log-file FILE      Log file path (optional)
echo.
echo Other Options:
echo   --help               Show this help message
echo   --version            Show version information
echo.
echo Examples:
echo   %~n0 -f input.dav -o output.mkv
echo   %~n0 -d "./videos" --container mp4 --recursive
echo   %~n0 -f video.avi --log-level DEBUG --log-file conversion.log
echo.
goto :eof

:show_version
echo %SCRIPT_NAME% v%SCRIPT_VERSION%
echo Windows Batch Script Implementation
goto :eof

:log_message
REM Parameters: %1=level, %2=message
set "log_level=%~1"
set "log_msg=%~2"
set "timestamp="

REM Get current timestamp
for /f "tokens=2 delims==" %%i in ('wmic OS Get localdatetime /value') do set "dt=%%i"
set "timestamp=%dt:~0,4%-%dt:~4,2%-%dt:~6,2% %dt:~8,2%:%dt:~10,2%:%dt:~12,2%"

REM Format message
set "formatted_msg=%timestamp% - %log_level% - %log_msg%"

REM Display to console based on log level
if /i "%LOG_LEVEL%"=="DEBUG" (
    echo %formatted_msg%
) else if /i "%log_level%"=="INFO" (
    if /i "%LOG_LEVEL%"=="INFO" echo %formatted_msg%
) else if /i "%log_level%"=="WARNING" (
    if /i not "%LOG_LEVEL%"=="ERROR" echo WARNING: %formatted_msg%
) else if /i "%log_level%"=="ERROR" (
    echo ERROR: %formatted_msg% >&2
)

REM Write to log file if specified
if defined LOG_FILE (
    echo %formatted_msg% >> "%LOG_FILE%" 2>nul
)
goto :eof

:check_ffmpeg
call :log_message "INFO" "Checking FFmpeg availability..."

REM Check if ffmpeg is available
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    call :log_message "ERROR" "FFmpeg is not available in system PATH"
    call :log_message "ERROR" "Please install FFmpeg and ensure it's accessible from command line"
    exit /b 1
)

REM Get FFmpeg version
for /f "tokens=*" %%i in ('ffmpeg -version 2^>^&1 ^| findstr "ffmpeg version"') do (
    call :log_message "INFO" "Found: %%i"
    goto :check_ffprobe
)

:check_ffprobe
REM Check if ffprobe is available
ffprobe -version >nul 2>&1
if errorlevel 1 (
    call :log_message "ERROR" "FFprobe is not available in system PATH"
    call :log_message "ERROR" "FFprobe is required for video analysis"
    exit /b 1
)

call :log_message "INFO" "FFmpeg and FFprobe are available"
exit /b 0

:get_video_info
REM Parameters: %1=input_file
set "input_file=%~1"
call :log_message "DEBUG" "Getting video info for: %input_file%"

if not exist "%input_file%" (
    call :log_message "ERROR" "Input file does not exist: %input_file%"
    exit /b 1
)

REM Use ffprobe to get video information
ffprobe -v quiet -print_format json -show_format -show_streams "%input_file%" >nul 2>&1
if errorlevel 1 (
    call :log_message "WARNING" "Could not retrieve video information for: %input_file%"
    exit /b 1
)

call :log_message "DEBUG" "Successfully retrieved video info"
exit /b 0

:convert_single_file
REM Parameters: %1=input_file, %2=output_file
set "input_file=%~1"
set "output_file=%~2"
set "start_convert_time="

call :log_message "INFO" "Starting conversion: %input_file%"

REM Validate input file
if not exist "%input_file%" (
    call :log_message "ERROR" "Input file not found: %input_file%"
    exit /b 1
)

REM Create output directory if needed
for %%d in ("%output_file%") do (
    if not exist "%%~dpd" (
        mkdir "%%~dpd" 2>nul
        if errorlevel 1 (
            call :log_message "ERROR" "Failed to create output directory: %%~dpd"
            exit /b 1
        )
    )
)

REM Check if output exists and handle overwrite
if exist "%output_file%" (
    if "%OVERWRITE%"=="0" (
        call :log_message "WARNING" "Output file exists and overwrite disabled: %output_file%"
        exit /b 2
    )
)

REM Get video information
call :get_video_info "%input_file%"

REM Record start time
set "start_convert_time=%time%"

REM Build FFmpeg command
set "ffmpeg_cmd=ffmpeg -i "%input_file%" -c copy -map 0 -avoid_negative_ts make_zero -fflags +genpts"

if "%OVERWRITE%"=="1" (
    set "ffmpeg_cmd=!ffmpeg_cmd! -y"
) else (
    set "ffmpeg_cmd=!ffmpeg_cmd! -n"
)

set "ffmpeg_cmd=!ffmpeg_cmd! "%output_file%""

call :log_message "INFO" "Converting to %CONTAINER%: %input_file% -> %output_file%"
call :log_message "DEBUG" "FFmpeg command: !ffmpeg_cmd!"

REM Execute conversion
!ffmpeg_cmd! >nul 2>&1
set "conversion_result=!errorlevel!"

if !conversion_result! equ 0 (
    call :verify_output_file "%output_file%" "%input_file%"
    if !errorlevel! equ 0 (
        call :log_message "INFO" "Conversion successful: %output_file%"
        set /a "SUCCESS_COUNT+=1"
        exit /b 0
    ) else (
        call :log_message "ERROR" "Output file verification failed"
        set /a "FAILED_COUNT+=1"
        exit /b 1
    )
) else (
    call :log_message "ERROR" "FFmpeg conversion failed with error code: !conversion_result!"
    set /a "FAILED_COUNT+=1"
    exit /b 1
)

:verify_output_file
REM Parameters: %1=output_file, %2=input_file
set "output_file=%~1"
set "input_file=%~2"

if not exist "%output_file%" (
    call :log_message "ERROR" "Output file does not exist: %output_file%"
    exit /b 1
)

REM Check if output file has size > 0
for %%f in ("%output_file%") do (
    if %%~zf equ 0 (
        call :log_message "ERROR" "Output file is empty: %output_file%"
        exit /b 1
    )
    set "output_size=%%~zf"
)

REM Get input file size for comparison
for %%f in ("%input_file%") do set "input_size=%%~zf"

REM Calculate size in MB for display
set /a "output_mb=%output_size% / 1048576"
call :log_message "INFO" "Output verified: %output_mb% MB"

exit /b 0

:is_video_file
REM Parameters: %1=file_path
set "file_path=%~1"
set "file_ext=%~x1"

for %%e in (%VIDEO_EXTENSIONS%) do (
    if /i "%file_ext%"=="%%e" exit /b 0
)
exit /b 1

:find_video_files
REM Parameters: %1=directory, %2=recursive_flag
set "search_dir=%~1"
set "recursive_flag=%~2"
set "found_files="

if not exist "%search_dir%" (
    call :log_message "ERROR" "Directory does not exist: %search_dir%"
    exit /b 1
)

call :log_message "INFO" "Scanning for video files in: %search_dir%"

if "%recursive_flag%"=="1" (
    REM Recursive search
    for /r "%search_dir%" %%f in (*.*) do (
        call :is_video_file "%%f"
        if !errorlevel! equ 0 (
            set /a "TOTAL_FILES+=1"
            call :log_message "DEBUG" "Found video file: %%f"
            call :convert_single_file "%%f" "%%~dpnf.%CONTAINER%"
        )
    )
) else (
    REM Non-recursive search
    for %%f in ("%search_dir%\*.*") do (
        if exist "%%f" (
            call :is_video_file "%%f"
            if !errorlevel! equ 0 (
                set /a "TOTAL_FILES+=1"
                call :log_message "DEBUG" "Found video file: %%f"
                call :convert_single_file "%%f" "%%~dpnf.%CONTAINER%"
            )
        )
    )
)

exit /b 0

:convert_directory
REM Parameters: %1=input_directory
set "input_dir=%~1"

call :log_message "INFO" "Starting batch conversion in: %input_dir%"
call :log_message "INFO" "Container format: %CONTAINER%"
call :log_message "INFO" "Recursive: %RECURSIVE%"

call :find_video_files "%input_dir%" "%RECURSIVE%"

call :log_message "INFO" "Batch conversion completed"
call :log_message "INFO" "Total files processed: %TOTAL_FILES%"
call :log_message "INFO" "Successful conversions: %SUCCESS_COUNT%"
call :log_message "INFO" "Failed conversions: %FAILED_COUNT%"

exit /b 0

REM ============================================================================
REM ARGUMENT PARSING
REM ============================================================================

:parse_args
if "%~1"=="" goto :args_parsed

set "arg=%~1"

if /i "%arg%"=="-h" set "HELP_REQUESTED=1" & goto :next_arg
if /i "%arg%"=="--help" set "HELP_REQUESTED=1" & goto :next_arg
if /i "%arg%"=="--version" set "VERSION_REQUESTED=1" & goto :next_arg

if /i "%arg%"=="-f" (
    set "INPUT_FILE=%~2"
    shift
    goto :next_arg
)

if /i "%arg%"=="-d" (
    set "INPUT_DIR=%~2"
    shift
    goto :next_arg
)

if /i "%arg%"=="-o" (
    set "OUTPUT_PATH=%~2"
    shift
    goto :next_arg
)

if /i "%arg%"=="--container" (
    set "CONTAINER=%~2"
    shift
    goto :next_arg
)

if /i "%arg%"=="--overwrite" (
    set "OVERWRITE=1"
    goto :next_arg
)

if /i "%arg%"=="--no-overwrite" (
    set "OVERWRITE=0"
    goto :next_arg
)

if /i "%arg%"=="--recursive" (
    set "RECURSIVE=1"
    goto :next_arg
)

if /i "%arg%"=="-c" (
    set "MAX_WORKERS=%~2"
    shift
    goto :next_arg
)

if /i "%arg%"=="--log-level" (
    set "LOG_LEVEL=%~2"
    shift
    goto :next_arg
)

if /i "%arg%"=="--log-file" (
    set "LOG_FILE=%~2"
    shift
    goto :next_arg
)

REM Unknown argument
call :log_message "WARNING" "Unknown argument: %arg%"

:next_arg
shift
goto :parse_args

:args_parsed

REM Arguments will be validated in main function

REM Validate container format
if /i not "%CONTAINER%"=="mkv" if /i not "%CONTAINER%"=="mp4" (
    call :log_message "ERROR" "Invalid container format: %CONTAINER% (must be mkv or mp4)"
    exit /b 1
)

REM Validate input (file or directory required, unless help/version requested)
if "%HELP_REQUESTED%"=="0" if "%VERSION_REQUESTED%"=="0" (
    if not defined INPUT_FILE if not defined INPUT_DIR (
        call :log_message "ERROR" "Either input file (-f) or input directory (-d) is required"
        call :show_usage
        exit /b 1
    )

    if defined INPUT_FILE if defined INPUT_DIR (
        call :log_message "ERROR" "Cannot specify both input file and input directory"
        exit /b 1
    )
)

REM Validate log level
set "valid_levels=DEBUG INFO WARNING ERROR"
set "level_valid=0"
for %%l in (%valid_levels%) do (
    if /i "%LOG_LEVEL%"=="%%l" set "level_valid=1"
)
if "%level_valid%"=="0" (
    call :log_message "WARNING" "Invalid log level: %LOG_LEVEL%, using INFO"
    set "LOG_LEVEL=INFO"
)

exit /b 0

REM ============================================================================
REM MAIN EXECUTION
REM ============================================================================

:main
REM Parse command line arguments
call :parse_args %*
if errorlevel 1 exit /b 1

REM Check if help or version was requested
if "%HELP_REQUESTED%"=="1" (
    call :show_usage
    exit /b 0
)
if "%VERSION_REQUESTED%"=="1" (
    call :show_version
    exit /b 0
)

REM Initialize logging
if defined LOG_FILE (
    echo. > "%LOG_FILE%" 2>nul
    if errorlevel 1 (
        call :log_message "WARNING" "Could not initialize log file: %LOG_FILE%"
        set "LOG_FILE="
    )
)

call :log_message "INFO" "=== %SCRIPT_NAME% v%SCRIPT_VERSION% Starting ==="

REM Log system information  
call :log_message "INFO" "Platform: Windows %OS%"
call :log_message "INFO" "Processor: %PROCESSOR_ARCHITECTURE%"
if defined NUMBER_OF_PROCESSORS call :log_message "INFO" "CPU count: %NUMBER_OF_PROCESSORS%"

REM Check FFmpeg availability
call :check_ffmpeg
if errorlevel 1 exit /b 127

REM Process based on input type
if defined INPUT_FILE (
    REM Single file conversion
    set /a "TOTAL_FILES=1"
    
    if not defined OUTPUT_PATH (
        for %%f in ("%INPUT_FILE%") do set "OUTPUT_PATH=%%~dpnf.%CONTAINER%"
    )
    
    call :log_message "INFO" "Converting single file: %INPUT_FILE%"
    call :convert_single_file "%INPUT_FILE%" "%OUTPUT_PATH%"
    set "conversion_result=!errorlevel!"
    
    if !conversion_result! equ 0 (
        call :log_message "INFO" "Conversion completed successfully"
        set "final_exit_code=0"
    ) else (
        call :log_message "ERROR" "Conversion failed"
        set "final_exit_code=1"
    )
) else if defined INPUT_DIR (
    REM Directory batch conversion
    call :convert_directory "%INPUT_DIR%"
    
    if %FAILED_COUNT% equ 0 (
        call :log_message "INFO" "All conversions completed successfully"
        set "final_exit_code=0"
    ) else if %SUCCESS_COUNT% gtr 0 (
        call :log_message "WARNING" "Partial success: %SUCCESS_COUNT% succeeded, %FAILED_COUNT% failed"
        set "final_exit_code=2"
    ) else (
        call :log_message "ERROR" "All conversions failed"
        set "final_exit_code=1"
    )
)

call :log_message "INFO" "=== %SCRIPT_NAME% Finished ==="
exit /b %final_exit_code%

REM End of script
