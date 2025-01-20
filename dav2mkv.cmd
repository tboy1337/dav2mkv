@echo off
setlocal enabledelayedexpansion

:: Parse command line arguments
set "INPUT_FILE="
set "INPUT_DIR="
set "OUTPUT_FILE="
set "CONTAINER=mkv"
set "MAX_CONCURRENT="

:parse_args
if "%~1"=="" goto :end_parse
if /i "%~1"=="-f" (
    set "INPUT_FILE=%~2"
    shift
) else if /i "%~1"=="--file" (
    set "INPUT_FILE=%~2"
    shift
) else if /i "%~1"=="-d" (
    set "INPUT_DIR=%~2"
    shift
) else if /i "%~1"=="--directory" (
    set "INPUT_DIR=%~2"
    shift
) else if /i "%~1"=="-o" (
    set "OUTPUT_FILE=%~2"
    shift
) else if /i "%~1"=="--output" (
    set "OUTPUT_FILE=%~2"
    shift
) else if /i "%~1"=="--container" (
    if /i "%~2"=="mp4" (
        set "CONTAINER=mp4"
    ) else if /i "%~2"=="mkv" (
        set "CONTAINER=mkv"
    ) else (
        echo Error: Invalid container format. Use mkv or mp4.
        exit /b 1
    )
    shift
) else if /i "%~1"=="-c" (
    set "MAX_CONCURRENT=%~2"
    shift
) else if /i "%~1"=="--concurrent" (
    set "MAX_CONCURRENT=%~2"
    shift
)
shift
goto :parse_args
:end_parse

:: Validate input arguments
if not defined INPUT_FILE if not defined INPUT_DIR (
    echo Error: Either -f/--file or -d/--directory must be specified.
    echo Usage:
    echo   %~nx0 -f ^<file^> [-o output] [--container mkv^|mp4]
    echo   %~nx0 -d ^<directory^> [-c concurrent] [--container mkv^|mp4]
    exit /b 1
)

if defined INPUT_FILE if defined INPUT_DIR (
    echo Error: Cannot specify both file and directory.
    exit /b 1
)

:: Function to get video information using ffprobe
:get_video_info
set "video_file=%~1"
echo Analyzing %video_file%...
echo.
echo Source video details:

for /f "tokens=* usebackq" %%a in (`ffprobe -v quiet -print_format json -show_format -show_streams "%video_file%" 2^>nul`) do (
    set "json_output=%%a"
    
    :: Basic parsing of the JSON output to display stream info
    echo !json_output! | findstr /i "codec_type.*video" >nul && (
        for /f "tokens=* usebackq" %%b in (`echo !json_output! ^| findstr /i "width height r_frame_rate codec_name"`) do (
            echo Video stream found: %%b
        )
    )
    
    echo !json_output! | findstr /i "codec_type.*audio" >nul && (
        for /f "tokens=* usebackq" %%b in (`echo !json_output! ^| findstr /i "channels sample_rate codec_name"`) do (
            echo Audio stream found: %%b
        )
    )
)
echo.
goto :eof

:: Function to convert a single video
:convert_video
set "input_file=%~1"
set "output_file=%~2"

if not exist "%input_file%" (
    echo Error: Input file '%input_file%' not found.
    exit /b 1
)

:: Create output filename if not provided
if not defined output_file (
    set "output_file=%~dpn1.%CONTAINER%"
)

:: Get video info
call :get_video_info "%input_file%"

:: Perform the conversion
echo Converting to %CONTAINER%...
ffmpeg -i "%input_file%" -c copy -map 0 -y "%output_file%"

if %errorlevel% equ 0 (
    echo Conversion successful! Output saved to: %output_file%
    
    :: Verify output file exists and has size
    if exist "%output_file%" (
        for %%I in ("%output_file%") do set "size=%%~zI"
        set /a "size_mb=!size! / 1048576"
        echo Output file verified (!size_mb! MB^)
        exit /b 0
    ) else (
        echo Error: Output file is missing or empty
        exit /b 1
    )
) else (
    echo Conversion failed
    exit /b 1
)
goto :eof

:: Main processing logic
if defined INPUT_FILE (
    call :convert_video "%INPUT_FILE%" "%OUTPUT_FILE%"
) else (
    :: Process directory
    if not exist "%INPUT_DIR%" (
        echo Error: Directory '%INPUT_DIR%' not found.
        exit /b 1
    )
    
    :: Count video files
    set "count=0"
    for %%F in ("%INPUT_DIR%\*.dav" "%INPUT_DIR%\*.avi" "%INPUT_DIR%\*.mp4" "%INPUT_DIR%\*.mkv" "%INPUT_DIR%\*.mov" "%INPUT_DIR%\*.wmv") do (
        set /a "count+=1"
    )
    
    if !count! equ 0 (
        echo No video files found in the directory.
        exit /b 0
    )
    
    echo Found !count! video files to convert.
    
    :: Process each video file
    set "processed=0"
    for %%F in ("%INPUT_DIR%\*.dav" "%INPUT_DIR%\*.avi" "%INPUT_DIR%\*.mp4" "%INPUT_DIR%\*.mkv" "%INPUT_DIR%\*.mov" "%INPUT_DIR%\*.wmv") do (
        if exist "%%F" (
            call :convert_video "%%F"
            set /a "processed+=1"
            echo Progress: !processed!/!count! files processed
        )
    )
)

endlocal
