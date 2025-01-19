import cv2
import os
from pathlib import Path
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
from queue import Queue
from threading import Thread
import argparse

def get_optimal_worker_count():
    """
    Calculate optimal number of worker threads while reserving cores for the OS
    Returns number of workers, leaving at least 2 cores free for system processes
    """
    total_cores = multiprocessing.cpu_count()
    # Reserve 2 cores for OS and other processes, minimum 1 worker
    return max(1, total_cores - 2)

def process_frame_chunk(frames):
    """Process a chunk of frames in parallel"""
    return [frame for frame in frames if frame is not None]

def frame_reader(cap, frame_queue, total_frames):
    """Read frames from the video file and put them in the queue"""
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_queue.put(frame)
        frame_count += 1
        if frame_count % 100 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"Reading Progress: {progress:.1f}%")
    frame_queue.put(None)  # Signal end of frames

def frame_writer(out, frame_queue, total_frames):
    """Write frames from the queue to the output file"""
    frame_count = 0
    while True:
        frame = frame_queue.get()
        if frame is None:
            break
        out.write(frame)
        frame_count += 1
        if frame_count % 100 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"Writing Progress: {progress:.1f}%")

def convert_dav_to_mp4(input_file, output_file=None, chunk_size=32):
    """
    Convert a .dav file to .mp4 format with high quality settings using parallel processing
    
    Args:
        input_file (str): Path to input .dav file
        output_file (str, optional): Path for output .mp4 file. If None, uses same name as input
        chunk_size (int): Number of frames to process in parallel
    
    Returns:
        bool: True if conversion successful, False otherwise
    """
    try:
        # Validate input file
        if not os.path.exists(input_file):
            print(f"Error: Input file '{input_file}' not found.")
            return False
            
        # Create output filename if not provided
        if output_file is None:
            output_file = str(Path(input_file).with_suffix('.mp4'))
            
        # Open the input video
        cap = cv2.VideoCapture(input_file)
        if not cap.isOpened():
            print(f"Error: Could not open input file '{input_file}'")
            return False
            
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Initialize video writer with best available codec
        try:
            fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
            out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
            if not out.isOpened():
                raise Exception("H.264 codec not available")
        except:
            try:
                fourcc = cv2.VideoWriter_fourcc(*'hvc1')  # H.265 codec
                out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
                if not out.isOpened():
                    raise Exception("H.265 codec not available")
            except:
                print("Warning: Using fallback MPEG-4 codec. Quality may be reduced.")
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

        # Set up queues for parallel processing
        read_queue = Queue(maxsize=chunk_size * 2)
        write_queue = Queue(maxsize=chunk_size * 2)
        
        # Start reader and writer threads
        reader_thread = Thread(target=frame_reader, args=(cap, read_queue, total_frames))
        writer_thread = Thread(target=frame_writer, args=(out, write_queue, total_frames))
        
        reader_thread.start()
        writer_thread.start()

        # Process frames in parallel using ThreadPoolExecutor
        num_workers = get_optimal_worker_count()
        print(f"Processing with {num_workers} workers (reserved 2 cores for system)")
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            while True:
                frames = []
                for _ in range(chunk_size):
                    frame = read_queue.get()
                    if frame is None:
                        break
                    frames.append(frame)
                
                if not frames:
                    break
                    
                # Process frame chunk in parallel
                processed_frames = executor.submit(process_frame_chunk, frames).result()
                
                # Put processed frames in write queue
                for frame in processed_frames:
                    write_queue.put(frame)
        
        # Signal end of processing
        write_queue.put(None)
        
        # Wait for threads to finish
        reader_thread.join()
        writer_thread.join()
        
        # Release everything
        cap.release()
        out.release()
        
        print(f"Conversion completed! Output saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def batch_convert_directory(input_dir, max_concurrent=None):
    """
    Convert all .dav files in a directory to .mp4 using parallel processing
    
    Args:
        input_dir (str): Path to directory containing .dav files
        max_concurrent (int, optional): Maximum number of concurrent conversions
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        print(f"Error: Directory '{input_dir}' not found.")
        return
        
    dav_files = list(input_dir.glob("*.dav"))
    if not dav_files:
        print("No .dav files found in the directory.")
        return
    
    if max_concurrent is None:
        # Just reserve 2 cores, no extra division
        max_concurrent = max(1, multiprocessing.cpu_count() - 2)
        
    print(f"Found {len(dav_files)} .dav files to convert.")
    print(f"Processing up to {max_concurrent} files concurrently (reserved 2 cores for system)")
    
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = [executor.submit(convert_dav_to_mp4, str(dav_file)) for dav_file in dav_files]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Conversion failed: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert DAV files to MP4 format with parallel processing.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-f', '--file', help='Single DAV file to convert')
    group.add_argument('-d', '--directory', help='Directory containing DAV files to convert')
    parser.add_argument('-o', '--output', help='Output file name (only for single file conversion)')
    parser.add_argument('-c', '--concurrent', type=int, help='Maximum number of concurrent conversions for directory processing')
    
    args = parser.parse_args()
    
    if args.file:
        # Single file conversion
        convert_dav_to_mp4(args.file, args.output)
    else:
        # Directory conversion
        batch_convert_directory(args.directory, args.concurrent)
