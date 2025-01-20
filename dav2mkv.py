import subprocess
import os
from pathlib import Path
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

def get_video_info(input_file):
    """
    Get video information using ffprobe
    Returns dict with video details or None if failed
    """
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        input_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Warning: Could not read video info: {str(e)}")
        return None

def convert_video(input_file, output_file=None, container='mkv'):
    """
    Convert video using direct stream copy
    
    Args:
        input_file (str): Path to input video file
        output_file (str, optional): Path for output file
        container (str): Output container format ('mkv' or 'mp4')
    
    Returns:
        bool: True if conversion successful, False otherwise
    """
    try:
        if not os.path.exists(input_file):
            print(f"Error: Input file '{input_file}' not found.")
            return False

        # Create output filename if not provided
        if output_file is None:
            output_file = str(Path(input_file).with_suffix(f'.{container}'))

        # Get video info before conversion
        print(f"Analyzing {input_file}...")
        info = get_video_info(input_file)
        
        if info:
            # Print source video details
            print("\nSource video details:")
            streams = {
                'video': 0,
                'audio': 0,
                'subtitle': 0,
                'data': 0
            }
            
            for stream in info.get('streams', []):
                stream_type = stream.get('codec_type', 'unknown')
                streams[stream_type] = streams.get(stream_type, 0) + 1
                
                if stream_type == 'video':
                    print(f"Video: {stream.get('codec_name', 'unknown')} "
                          f"{stream.get('width', '?')}x{stream.get('height', '?')} @ "
                          f"{stream.get('r_frame_rate', '?')}fps")
                elif stream_type == 'audio':
                    print(f"Audio: {stream.get('codec_name', 'unknown')} "
                          f"{stream.get('channels', '?')} channels @ "
                          f"{stream.get('sample_rate', '?')}Hz")
            
            print(f"\nStreams found: "
                  f"{streams['video']} video, "
                  f"{streams['audio']} audio, "
                  f"{streams['subtitle']} subtitle, "
                  f"{streams['data']} data")

        # Perform the conversion
        print(f"\nConverting to {container.upper()}...")
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-c', 'copy',        # Copy all streams without re-encoding
            '-map', '0',         # Include all streams
            '-y',                # Overwrite output if exists
            output_file
        ]
        
        # Run conversion
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            print(f"Conversion successful! Output saved to: {output_file}")
            
            # Verify output file exists and has size
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f"Output file verified ({os.path.getsize(output_file) / (1024*1024):.1f} MB)")
                return True
            else:
                print("Error: Output file is missing or empty")
                return False
        else:
            print(f"Conversion failed with error: {process.stderr}")
            return False
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def batch_convert_directory(input_dir, container='mkv', max_concurrent=None):
    """
    Convert all video files in a directory
    
    Args:
        input_dir (str): Path to directory containing videos
        container (str): Output container format ('mkv' or 'mp4')
        max_concurrent (int, optional): Maximum number of concurrent conversions
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        print(f"Error: Directory '{input_dir}' not found.")
        return

    # Look for common video file extensions
    video_files = []
    for ext in ['.dav', '.avi', '.mp4', '.mkv', '.mov', '.wmv']:
        video_files.extend(input_dir.glob(f"*{ext}"))
    
    if not video_files:
        print("No video files found in the directory.")
        return
    
    if max_concurrent is None:
        max_concurrent = max(1, multiprocessing.cpu_count() - 1)
        
    print(f"Found {len(video_files)} video files to convert.")
    print(f"Processing up to {max_concurrent} files concurrently")
    
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = [
            executor.submit(convert_video, str(video_file), container=container)
            for video_file in video_files
        ]
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            try:
                success = future.result()
                print(f"Progress: {completed}/{len(video_files)} files processed")
            except Exception as e:
                print(f"Conversion failed: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Convert video files using direct stream copy for maximum quality.'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-f', '--file', help='Single video file to convert')
    group.add_argument('-d', '--directory', help='Directory containing video files to convert')
    parser.add_argument('-o', '--output', help='Output file name (only for single file conversion)')
    parser.add_argument('-c', '--concurrent', type=int, 
                       help='Maximum number of concurrent conversions for directory processing')
    parser.add_argument('--container', choices=['mkv', 'mp4'], default='mkv',
                       help='Output container format (default: mkv)')
    
    args = parser.parse_args()
    
    if args.file:
        convert_video(args.file, args.output, args.container)
    else:
        batch_convert_directory(args.directory, args.container, args.concurrent)
