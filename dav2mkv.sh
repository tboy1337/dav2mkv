#!/bin/bash

# Function to get video information using ffprobe
get_video_info() {
    local input_file="$1"
    
    # Get raw JSON info
    local info=$(ffprobe -v quiet -print_format json -show_format -show_streams "$input_file" 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo "Warning: Could not read video info"
        return 1
    fi
    
    # Parse and display video information
    echo -e "\nSource video details:"
    
    # Count stream types
    local video_streams=$(echo "$info" | grep -c '"codec_type":"video"')
    local audio_streams=$(echo "$info" | grep -c '"codec_type":"audio"')
    local subtitle_streams=$(echo "$info" | grep -c '"codec_type":"subtitle"')
    local data_streams=$(echo "$info" | grep -c '"codec_type":"data"')
    
    # Get video details
    local video_codec=$(echo "$info" | grep -m1 '"codec_name"' | cut -d'"' -f4)
    local width=$(echo "$info" | grep -m1 '"width"' | grep -o '[0-9]*')
    local height=$(echo "$info" | grep -m1 '"height"' | grep -o '[0-9]*')
    local fps=$(echo "$info" | grep -m1 '"r_frame_rate"' | cut -d'"' -f4)
    
    # Get audio details
    local audio_codec=$(echo "$info" | grep -A5 '"codec_type":"audio"' | grep '"codec_name"' | head -1 | cut -d'"' -f4)
    local channels=$(echo "$info" | grep -A5 '"codec_type":"audio"' | grep '"channels"' | head -1 | grep -o '[0-9]*')
    local sample_rate=$(echo "$info" | grep -A5 '"codec_type":"audio"' | grep '"sample_rate"' | head -1 | cut -d'"' -f4)
    
    # Display information
    [ ! -z "$video_codec" ] && echo "Video: $video_codec ${width}x${height} @ ${fps}fps"
    [ ! -z "$audio_codec" ] && echo "Audio: $audio_codec $channels channels @ ${sample_rate}Hz"
    
    echo -e "\nStreams found: $video_streams video, $audio_streams audio, $subtitle_streams subtitle, $data_streams data"
}

# Function to convert a single video
convert_video() {
    local input_file="$1"
    local output_file="$2"
    local container="$3"
    
    # Check if input file exists
    if [ ! -f "$input_file" ]; then
        echo "Error: Input file '$input_file' not found."
        return 1
    fi
    
    # Create output filename if not provided
    if [ -z "$output_file" ]; then
        output_file="${input_file%.*}.${container}"
    fi
    
    # Get and display video information
    echo "Analyzing $input_file..."
    get_video_info "$input_file"
    
    # Perform the conversion
    echo -e "\nConverting to ${container^^}..."
    ffmpeg -i "$input_file" -c copy -map 0 -y "$output_file"
    
    if [ $? -eq 0 ]; then
        echo "Conversion successful! Output saved to: $output_file"
        
        # Verify output file
        if [ -f "$output_file" ]; then
            local size=$(du -m "$output_file" | cut -f1)
            echo "Output file verified ($size MB)"
            return 0
        else
            echo "Error: Output file is missing or empty"
            return 1
        fi
    else
        echo "Conversion failed"
        return 1
    fi
}

# Function to convert all videos in a directory
batch_convert_directory() {
    local input_dir="$1"
    local container="$2"
    local max_concurrent="${3:-$(( $(nproc) - 1 ))}"
    
    # Check if directory exists
    if [ ! -d "$input_dir" ]; then
        echo "Error: Directory '$input_dir' not found."
        return 1
    fi
    
    # Find video files
    local video_files=()
    while IFS= read -r -d $'\0' file; do
        video_files+=("$file")
    done < <(find "$input_dir" -type f \( -name "*.dav" -o -name "*.avi" -o -name "*.mp4" -o -name "*.mkv" -o -name "*.mov" -o -name "*.wmv" \) -print0)
    
    local total_files=${#video_files[@]}
    
    if [ $total_files -eq 0 ]; then
        echo "No video files found in the directory."
        return 1
    fi
    
    echo "Found $total_files video files to convert."
    echo "Processing up to $max_concurrent files concurrently"
    
    # Process files concurrently using background processes
    local completed=0
    local running=0
    local i=0
    
    while [ $i -lt $total_files ] || [ $running -gt 0 ]; do
        # Start new conversions if under limit and files remain
        while [ $running -lt $max_concurrent ] && [ $i -lt $total_files ]; do
            convert_video "${video_files[$i]}" "" "$container" &
            running=$((running + 1))
            i=$((i + 1))
        done
        
        # Wait for any child process to finish
        wait -n
        running=$((running - 1))
        completed=$((completed + 1))
        echo "Progress: $completed/$total_files files processed"
    done
}

# Main script
show_usage() {
    echo "Usage: $0 [-f FILE | -d DIRECTORY] [-o OUTPUT] [-c CONCURRENT] [--container mkv|mp4]"
    echo "Convert video files using direct stream copy for maximum quality."
    echo
    echo "Options:"
    echo "  -f, --file FILE        Single video file to convert"
    echo "  -d, --directory DIR    Directory containing video files to convert"
    echo "  -o, --output FILE      Output file name (only for single file conversion)"
    echo "  -c, --concurrent NUM   Maximum number of concurrent conversions"
    echo "  --container FORMAT     Output container format (mkv or mp4, default: mkv)"
}

# Parse command line arguments
TEMP=$(getopt -o 'f:d:o:c:h' --long 'file:,directory:,output:,concurrent:,container:,help' -n "$0" -- "$@")
if [ $? -ne 0 ]; then
    echo "Failed to parse arguments. Use -h for help."
    exit 1
fi

eval set -- "$TEMP"
unset TEMP

input_file=""
input_dir=""
output_file=""
max_concurrent=""
container="mkv"

while true; do
    case "$1" in
        '-f'|'--file')
            input_file="$2"
            shift 2
            continue
        ;;
        '-d'|'--directory')
            input_dir="$2"
            shift 2
            continue
        ;;
        '-o'|'--output')
            output_file="$2"
            shift 2
            continue
        ;;
        '-c'|'--concurrent')
            max_concurrent="$2"
            shift 2
            continue
        ;;
        '--container')
            container="$2"
            shift 2
            continue
        ;;
        '-h'|'--help')
            show_usage
            exit 0
        ;;
        '--')
            shift
            break
        ;;
        *)
            echo "Internal error!"
            exit 1
        ;;
    esac
done

# Validate arguments
if [ ! -z "$input_file" ] && [ ! -z "$input_dir" ]; then
    echo "Error: Cannot specify both file and directory"
    exit 1
fi

if [ -z "$input_file" ] && [ -z "$input_dir" ]; then
    echo "Error: Must specify either file or directory"
    show_usage
    exit 1
fi

# Run conversion
if [ ! -z "$input_file" ]; then
    convert_video "$input_file" "$output_file" "$container"
else
    batch_convert_directory "$input_dir" "$container" "$max_concurrent"
fi
