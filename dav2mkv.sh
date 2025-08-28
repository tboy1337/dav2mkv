#!/bin/bash
#
# DAV Video Converter - Bash Version
#
# A robust, production-ready tool for converting DAV video files to MKV or MP4
# while maintaining perfect quality through stream copying. This tool uses FFmpeg
# to perform direct stream copy operations, ensuring no quality loss during conversion.
#
# Features:
# - Direct stream copy (no quality loss)
# - Maintains all original streams (video, audio, subtitles)
# - Batch processing with parallel conversion support
# - Comprehensive logging and error handling
# - Cross-platform compatibility
#

set -euo pipefail

# Script version
readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_NAME="dav2mkv"

# Global variables
VERBOSE=false
DEBUG=false
LOG_FILE=""
LOG_LEVEL="INFO"
CONTAINER="mkv"
OVERWRITE=true
RECURSIVE=false
MAX_WORKERS=0
INPUT_FILE=""
INPUT_DIR=""
OUTPUT=""

# Statistics
CONVERSIONS_ATTEMPTED=0
CONVERSIONS_SUCCESSFUL=0
CONVERSIONS_FAILED=0
START_TIME=""

# Supported video extensions
readonly VIDEO_EXTENSIONS="dav avi mp4 mkv mov wmv flv webm m4v 3gp 3g2 asf rm rmvb vob ts"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Lock file for thread-safe logging
readonly LOCK_FILE="/tmp/${SCRIPT_NAME}_$$.lock"

# Cleanup function
cleanup() {
    local exit_code=$?
    [[ -f "$LOCK_FILE" ]] && rm -f "$LOCK_FILE"
    log_info "=== DAV Video Converter Finished ==="
    exit $exit_code
}

trap cleanup EXIT

# Logging functions
log_with_lock() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Thread-safe logging using flock
    (
        flock -x 200
        local output="${timestamp} - ${level} - ${message}"
        
        # Console output with colors
        case "$level" in
            "ERROR"|"CRITICAL")
                echo -e "${RED}${output}${NC}" >&2
                ;;
            "WARNING")
                echo -e "${YELLOW}${output}${NC}" >&2
                ;;
            "INFO")
                echo -e "${GREEN}${output}${NC}"
                ;;
            "DEBUG")
                if [[ "$DEBUG" == "true" ]]; then
                    echo -e "${BLUE}${output}${NC}"
                fi
                ;;
            *)
                echo "$output"
                ;;
        esac
        
        # File logging if enabled
        if [[ -n "$LOG_FILE" ]]; then
            echo "$output" >> "$LOG_FILE"
        fi
    ) 200>"$LOCK_FILE"
}

log_debug() { log_with_lock "DEBUG" "$1"; }
log_info() { log_with_lock "INFO" "$1"; }
log_warning() { log_with_lock "WARNING" "$1"; }
log_error() { log_with_lock "ERROR" "$1"; }
log_critical() { log_with_lock "CRITICAL" "$1"; }

# Error handling
die() {
    log_critical "$1"
    exit "${2:-1}"
}

# Show usage information
show_usage() {
    cat << 'EOF'
Usage: dav2mkv.sh [OPTIONS]

Convert video files using direct stream copy for maximum quality.

Options:
    -f, --file FILE             Single video file to convert
    -d, --directory DIR         Directory containing video files to convert
    -o, --output PATH           Output file or directory name
    --container FORMAT          Output container format (mkv, mp4) [default: mkv]
    --overwrite                 Overwrite existing output files [default: true]
    --no-overwrite              Do not overwrite existing output files
    -c, --concurrent N          Maximum number of concurrent conversions
    --recursive                 Process directories recursively
    --log-level LEVEL           Set logging level (DEBUG,INFO,WARNING,ERROR,CRITICAL) [default: INFO]
    --log-file FILE             Log file path (optional)
    --verbose                   Enable verbose output
    --debug                     Enable debug output
    -h, --help                  Show this help message
    --version                   Show version information

Examples:
    dav2mkv.sh -f input.dav -o output.mkv
    dav2mkv.sh -d ./videos --container mp4 --recursive
    dav2mkv.sh -f video.avi --log-level DEBUG --log-file conversion.log

EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--file)
                [[ -z "${2:-}" ]] && die "Option $1 requires an argument"
                INPUT_FILE="$2"
                shift 2
                ;;
            -d|--directory)
                [[ -z "${2:-}" ]] && die "Option $1 requires an argument"
                INPUT_DIR="$2"
                shift 2
                ;;
            -o|--output)
                [[ -z "${2:-}" ]] && die "Option $1 requires an argument"
                OUTPUT="$2"
                shift 2
                ;;
            --container)
                [[ -z "${2:-}" ]] && die "Option $1 requires an argument"
                case "$2" in
                    mkv|mp4)
                        CONTAINER="$2"
                        ;;
                    *)
                        die "Unsupported container format: $2. Use 'mkv' or 'mp4'"
                        ;;
                esac
                shift 2
                ;;
            --overwrite)
                OVERWRITE=true
                shift
                ;;
            --no-overwrite)
                OVERWRITE=false
                shift
                ;;
            -c|--concurrent)
                [[ -z "${2:-}" ]] && die "Option $1 requires an argument"
                if [[ "$2" =~ ^[0-9]+$ ]] && [[ "$2" -gt 0 ]]; then
                    MAX_WORKERS="$2"
                else
                    die "Concurrent value must be a positive integer"
                fi
                shift 2
                ;;
            --recursive)
                RECURSIVE=true
                shift
                ;;
            --log-level)
                [[ -z "${2:-}" ]] && die "Option $1 requires an argument"
                case "$2" in
                    DEBUG|INFO|WARNING|ERROR|CRITICAL)
                        LOG_LEVEL="$2"
                        [[ "$LOG_LEVEL" == "DEBUG" ]] && DEBUG=true
                        ;;
                    *)
                        die "Invalid log level: $2"
                        ;;
                esac
                shift 2
                ;;
            --log-file)
                [[ -z "${2:-}" ]] && die "Option $1 requires an argument"
                LOG_FILE="$2"
                # Create log directory if it doesn't exist
                mkdir -p "$(dirname "$LOG_FILE")"
                shift 2
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --debug)
                DEBUG=true
                LOG_LEVEL="DEBUG"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            --version)
                echo "DAV Video Converter $SCRIPT_VERSION"
                exit 0
                ;;
            *)
                die "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done

    # Validate input arguments
    if [[ -z "$INPUT_FILE" && -z "$INPUT_DIR" ]]; then
        die "Either --file or --directory must be specified. Use --help for usage information."
    fi

    if [[ -n "$INPUT_FILE" && -n "$INPUT_DIR" ]]; then
        die "Cannot specify both --file and --directory. Use --help for usage information."
    fi
}

# Check if FFmpeg is available
check_ffmpeg_availability() {
    log_info "Checking FFmpeg availability..."
    
    if ! command -v ffmpeg >/dev/null 2>&1; then
        die "FFmpeg is not available. Please install FFmpeg and ensure it's in your PATH." 127
    fi
    
    if ! command -v ffprobe >/dev/null 2>&1; then
        die "FFprobe is not available. Please install FFmpeg and ensure it's in your PATH." 127
    fi
    
    local ffmpeg_version
    ffmpeg_version=$(ffmpeg -version 2>/dev/null | head -n1 || echo "Unknown version")
    log_info "FFmpeg found: $ffmpeg_version"
    
    return 0
}

# Get video information using ffprobe
get_video_info() {
    local input_file="$1"
    local temp_json
    temp_json=$(mktemp)
    
    if [[ ! -f "$input_file" ]]; then
        log_error "Input file does not exist: $input_file"
        rm -f "$temp_json"
        return 1
    fi
    
    log_debug "Getting video info for: $input_file"
    
    if ! ffprobe -v quiet -print_format json -show_format -show_streams "$input_file" > "$temp_json" 2>/dev/null; then
        log_error "Failed to get video information for: $input_file"
        rm -f "$temp_json"
        return 1
    fi
    
    # Log video information if successful
    if [[ -s "$temp_json" ]]; then
        log_video_info "$temp_json"
    fi
    
    rm -f "$temp_json"
    return 0
}

# Log detailed video information
log_video_info() {
    local json_file="$1"
    
    if ! command -v jq >/dev/null 2>&1; then
        log_debug "jq not available, skipping detailed video info logging"
        return 0
    fi
    
    log_info "=== Source Video Details ==="
    
    # Get video stream info
    local video_codec video_width video_height video_fps video_bitrate
    video_codec=$(jq -r '.streams[] | select(.codec_type=="video") | .codec_name // "unknown"' "$json_file" 2>/dev/null | head -n1)
    video_width=$(jq -r '.streams[] | select(.codec_type=="video") | .width // "?"' "$json_file" 2>/dev/null | head -n1)
    video_height=$(jq -r '.streams[] | select(.codec_type=="video") | .height // "?"' "$json_file" 2>/dev/null | head -n1)
    video_fps=$(jq -r '.streams[] | select(.codec_type=="video") | .r_frame_rate // "?"' "$json_file" 2>/dev/null | head -n1)
    video_bitrate=$(jq -r '.streams[] | select(.codec_type=="video") | .bit_rate // "unknown"' "$json_file" 2>/dev/null | head -n1)
    
    if [[ -n "$video_codec" && "$video_codec" != "null" ]]; then
        log_info "Video: $video_codec ${video_width}x${video_height} @ ${video_fps}fps, bitrate: $video_bitrate"
    fi
    
    # Get audio stream info
    local audio_codec audio_channels audio_sample_rate audio_bitrate
    audio_codec=$(jq -r '.streams[] | select(.codec_type=="audio") | .codec_name // "unknown"' "$json_file" 2>/dev/null | head -n1)
    audio_channels=$(jq -r '.streams[] | select(.codec_type=="audio") | .channels // "?"' "$json_file" 2>/dev/null | head -n1)
    audio_sample_rate=$(jq -r '.streams[] | select(.codec_type=="audio") | .sample_rate // "?"' "$json_file" 2>/dev/null | head -n1)
    audio_bitrate=$(jq -r '.streams[] | select(.codec_type=="audio") | .bit_rate // "unknown"' "$json_file" 2>/dev/null | head -n1)
    
    if [[ -n "$audio_codec" && "$audio_codec" != "null" ]]; then
        log_info "Audio: $audio_codec $audio_channels channels @ ${audio_sample_rate}Hz, bitrate: $audio_bitrate"
    fi
    
    # Stream counts
    local video_streams audio_streams subtitle_streams data_streams
    video_streams=$(jq '[.streams[] | select(.codec_type=="video")] | length' "$json_file" 2>/dev/null || echo "0")
    audio_streams=$(jq '[.streams[] | select(.codec_type=="audio")] | length' "$json_file" 2>/dev/null || echo "0")
    subtitle_streams=$(jq '[.streams[] | select(.codec_type=="subtitle")] | length' "$json_file" 2>/dev/null || echo "0")
    data_streams=$(jq '[.streams[] | select(.codec_type=="data")] | length' "$json_file" 2>/dev/null || echo "0")
    
    log_info "Streams: $video_streams video, $audio_streams audio, $subtitle_streams subtitle, $data_streams data"
    
    # File info
    local duration size
    duration=$(jq -r '.format.duration // "unknown"' "$json_file" 2>/dev/null)
    size=$(jq -r '.format.size // "unknown"' "$json_file" 2>/dev/null)
    
    if [[ "$size" != "unknown" && "$size" =~ ^[0-9]+$ ]]; then
        local size_mb
        size_mb=$(echo "scale=1; $size / 1024 / 1024" | bc -l 2>/dev/null || echo "?")
        log_info "Duration: ${duration}s, Size: ${size_mb} MB"
    else
        log_info "Duration: ${duration}s, Size: $size"
    fi
    
    log_info "=== End Video Details ==="
}

# Verify output file
verify_output_file() {
    local output_file="$1"
    local input_file="$2"
    
    if [[ ! -f "$output_file" ]]; then
        log_error "Output file does not exist: $output_file"
        return 1
    fi
    
    local output_size input_size
    output_size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null || echo "0")
    input_size=$(stat -f%z "$input_file" 2>/dev/null || stat -c%s "$input_file" 2>/dev/null || echo "0")
    
    if [[ "$output_size" -eq 0 ]]; then
        log_error "Output file is empty: $output_file"
        return 1
    fi
    
    # Check size ratio (stream copy should be similar size)
    if [[ "$input_size" -gt 0 ]] && command -v bc >/dev/null 2>&1; then
        local size_ratio
        size_ratio=$(echo "scale=2; $output_size / $input_size" | bc -l)
        
        if (( $(echo "$size_ratio < 0.8" | bc -l) )) || (( $(echo "$size_ratio > 1.2" | bc -l) )); then
            log_warning "Output file size differs significantly from input (ratio: $size_ratio)"
        fi
    fi
    
    local output_size_mb
    output_size_mb=$(echo "scale=1; $output_size / 1024 / 1024" | bc -l 2>/dev/null || echo "?")
    log_info "Output verified: ${output_size_mb} MB"
    
    return 0
}

# Convert a single video file
convert_video() {
    local input_file="$1"
    local output_file="$2"
    local start_time
    start_time=$(date +%s)
    
    log_info "Starting conversion of: $input_file"
    ((CONVERSIONS_ATTEMPTED++))
    
    # Validate input
    if [[ ! -f "$input_file" ]]; then
        log_error "Input file not found: $input_file"
        ((CONVERSIONS_FAILED++))
        return 1
    fi
    
    # Create output directory if needed
    mkdir -p "$(dirname "$output_file")"
    
    # Check if output exists and overwrite setting
    if [[ -f "$output_file" && "$OVERWRITE" != "true" ]]; then
        log_warning "Output file exists and overwrite disabled: $output_file"
        ((CONVERSIONS_FAILED++))
        return 1
    fi
    
    # Get and log video information
    log_info "Analyzing video file: $input_file"
    get_video_info "$input_file" || log_warning "Could not retrieve video information"
    
    # Perform the conversion
    log_info "Converting to ${CONTAINER^^}: $input_file -> $output_file"
    
    local ffmpeg_cmd=(
        ffmpeg
        -i "$input_file"
        -c copy                    # Copy all streams without re-encoding
        -map 0                     # Include all streams from input
        -avoid_negative_ts make_zero  # Handle timestamp issues
        -fflags +genpts           # Generate presentation timestamps
    )
    
    if [[ "$OVERWRITE" == "true" ]]; then
        ffmpeg_cmd+=(-y)          # Overwrite output if exists
    else
        ffmpeg_cmd+=(-n)          # Never overwrite
    fi
    
    ffmpeg_cmd+=("$output_file")
    
    log_debug "Running FFmpeg command: ${ffmpeg_cmd[*]}"
    
    # Run conversion
    local ffmpeg_output
    ffmpeg_output=$(mktemp)
    local conversion_success=false
    
    if timeout 3600 "${ffmpeg_cmd[@]}" >"$ffmpeg_output" 2>&1; then
        # Verify output file
        if verify_output_file "$output_file" "$input_file"; then
            local processing_time
            processing_time=$(($(date +%s) - start_time))
            log_info "Conversion successful: $output_file (${processing_time}s)"
            ((CONVERSIONS_SUCCESSFUL++))
            conversion_success=true
        else
            log_error "Output file verification failed"
            ((CONVERSIONS_FAILED++))
        fi
    else
        local exit_code=$?
        local error_output
        error_output=$(tail -n 10 "$ffmpeg_output" 2>/dev/null || echo "No error details available")
        
        if [[ $exit_code -eq 124 ]]; then
            local processing_time
            processing_time=$(($(date +%s) - start_time))
            log_error "Conversion timeout after ${processing_time}s: $input_file"
        else
            log_error "FFmpeg conversion failed (code $exit_code): $error_output"
        fi
        ((CONVERSIONS_FAILED++))
    fi
    
    rm -f "$ffmpeg_output"
    
    if [[ "$conversion_success" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# Check if file has video extension
is_video_file() {
    local file="$1"
    local extension
    extension=$(echo "${file##*.}" | tr '[:upper:]' '[:lower:]')
    
    for ext in $VIDEO_EXTENSIONS; do
        if [[ "$extension" == "$ext" ]]; then
            return 0
        fi
    done
    
    return 1
}

# Find video files in directory
find_video_files() {
    local directory="$1"
    local recursive="$2"
    local -a video_files=()
    
    if [[ ! -d "$directory" ]]; then
        log_error "Directory does not exist: $directory"
        return 1
    fi
    
    log_debug "Scanning directory: $directory (recursive: $recursive)"
    
    if [[ "$recursive" == "true" ]]; then
        while IFS= read -r -d '' file; do
            if [[ -f "$file" ]] && is_video_file "$file"; then
                video_files+=("$file")
                log_debug "Found video file: $file"
            fi
        done < <(find "$directory" -type f -print0 2>/dev/null)
    else
        for file in "$directory"/*; do
            if [[ -f "$file" ]] && is_video_file "$file"; then
                video_files+=("$file")
                log_debug "Found video file: $file"
            fi
        done
    fi
    
    log_info "Found ${#video_files[@]} video files in $directory"
    
    # Output found files (one per line)
    for file in "${video_files[@]}"; do
        echo "$file"
    done
    
    return 0
}

# Convert directory with parallel processing
convert_directory() {
    local input_dir="$1"
    local output_dir="$2"
    local workers="$3"
    
    # Set default output directory
    if [[ -z "$output_dir" ]]; then
        output_dir="$input_dir"
    else
        mkdir -p "$output_dir"
    fi
    
    log_info "Starting batch conversion: $input_dir -> $output_dir"
    log_info "Container: ${CONTAINER^^}, Workers: $workers"
    
    # Find all video files
    local -a video_files=()
    while IFS= read -r file; do
        [[ -n "$file" ]] && video_files+=("$file")
    done < <(find_video_files "$input_dir" "$RECURSIVE")
    
    if [[ ${#video_files[@]} -eq 0 ]]; then
        log_warning "No video files found to convert"
        return 0
    fi
    
    log_info "Processing ${#video_files[@]} files with $workers workers"
    
    # Process files with parallel execution
    local -a pids=()
    local active_jobs=0
    local completed=0
    
    for video_file in "${video_files[@]}"; do
        # Calculate output file path
        local output_file
        if [[ "$output_dir" != "$input_dir" ]]; then
            # Preserve directory structure in different output directory
            local relative_path
            relative_path="${video_file#$input_dir/}"
            output_file="$output_dir/${relative_path%.*}.$CONTAINER"
        else
            # Same directory, just change extension
            output_file="${video_file%.*}.$CONTAINER"
        fi
        
        # Start conversion in background
        (
            convert_video "$video_file" "$output_file"
            echo "$?" > "/tmp/${SCRIPT_NAME}_result_$$_$BASHPID"
        ) &
        
        pids+=($!)
        ((active_jobs++))
        
        # Wait if we've reached the worker limit
        if [[ $active_jobs -ge $workers ]]; then
            # Wait for at least one job to complete
            wait -n
            ((active_jobs--))
            ((completed++))
            
            # Check for completed jobs
            local -a remaining_pids=()
            for pid in "${pids[@]}"; do
                if kill -0 "$pid" 2>/dev/null; then
                    remaining_pids+=("$pid")
                fi
            done
            pids=("${remaining_pids[@]}")
            
            log_info "Progress: $completed/${#video_files[@]} files processed (${CONVERSIONS_SUCCESSFUL} successful, ${CONVERSIONS_FAILED} failed)"
        fi
    done
    
    # Wait for all remaining jobs to complete
    for pid in "${pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            wait "$pid"
            ((completed++))
            log_info "Progress: $completed/${#video_files[@]} files processed (${CONVERSIONS_SUCCESSFUL} successful, ${CONVERSIONS_FAILED} failed)"
        fi
    done
    
    # Clean up result files
    rm -f /tmp/${SCRIPT_NAME}_result_$$_*
    
    log_info "Batch conversion completed"
    return 0
}

# Log system information
log_system_info() {
    log_info "=== DAV Video Converter Starting ==="
    log_info "Script version: $SCRIPT_VERSION"
    log_info "Bash version: $BASH_VERSION"
    log_info "Platform: $(uname -s) $(uname -r)"
    log_info "Architecture: $(uname -m)"
    
    if command -v nproc >/dev/null 2>&1; then
        log_info "CPU count: $(nproc)"
    elif command -v sysctl >/dev/null 2>&1; then
        log_info "CPU count: $(sysctl -n hw.ncpu 2>/dev/null || echo "unknown")"
    else
        log_info "CPU count: unknown"
    fi
}

# Main function
main() {
    START_TIME=$(date +%s)
    
    # Parse command line arguments
    parse_arguments "$@"
    
    # Log system information
    log_system_info
    
    # Check FFmpeg availability
    check_ffmpeg_availability
    
    # Set default max workers if not specified
    if [[ $MAX_WORKERS -eq 0 ]]; then
        if command -v nproc >/dev/null 2>&1; then
            MAX_WORKERS=$(($(nproc) - 1))
        elif command -v sysctl >/dev/null 2>&1; then
            local cpu_count
            cpu_count=$(sysctl -n hw.ncpu 2>/dev/null || echo "2")
            MAX_WORKERS=$((cpu_count - 1))
        else
            MAX_WORKERS=1
        fi
        MAX_WORKERS=$((MAX_WORKERS < 1 ? 1 : MAX_WORKERS))
    fi
    
    # Process based on input type
    if [[ -n "$INPUT_FILE" ]]; then
        # Single file conversion
        log_info "Converting single file: $INPUT_FILE"
        
        local output_file="$OUTPUT"
        if [[ -z "$output_file" ]]; then
            output_file="${INPUT_FILE%.*}.$CONTAINER"
        fi
        
        if convert_video "$INPUT_FILE" "$output_file"; then
            log_info "Conversion stats: Attempted=$CONVERSIONS_ATTEMPTED, Successful=$CONVERSIONS_SUCCESSFUL, Failed=$CONVERSIONS_FAILED"
            return 0
        else
            log_info "Conversion stats: Attempted=$CONVERSIONS_ATTEMPTED, Successful=$CONVERSIONS_SUCCESSFUL, Failed=$CONVERSIONS_FAILED"
            return 1
        fi
    else
        # Directory batch conversion
        if [[ $MAX_WORKERS -gt 1 ]]; then
            log_info "Using $MAX_WORKERS worker processes"
        fi
        
        convert_directory "$INPUT_DIR" "$OUTPUT" "$MAX_WORKERS"
        
        # Log final results
        log_info "Final results: Total=${#video_files[@]:-0}, Successful=$CONVERSIONS_SUCCESSFUL, Failed=$CONVERSIONS_FAILED"
        log_info "Converter stats: Attempted=$CONVERSIONS_ATTEMPTED, Successful=$CONVERSIONS_SUCCESSFUL, Failed=$CONVERSIONS_FAILED"
        
        # Return appropriate exit code
        if [[ $CONVERSIONS_FAILED -eq 0 ]]; then
            log_info "All conversions completed successfully"
            return 0
        elif [[ $CONVERSIONS_SUCCESSFUL -gt 0 ]]; then
            log_warning "Partial success: $CONVERSIONS_SUCCESSFUL succeeded, $CONVERSIONS_FAILED failed"
            return 2
        else
            log_error "All conversions failed"
            return 1
        fi
    fi
}

# Handle interruption
handle_interrupt() {
    log_warning "Conversion interrupted by user"
    exit 130
}

trap handle_interrupt INT TERM

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
