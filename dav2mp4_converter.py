import cv2
import os
from pathlib import Path

def convert_dav_to_mp4(input_file, output_file=None):
    """
    Convert a .dav file to .mp4 format with high quality settings
    
    Args:
        input_file (str): Path to input .dav file
        output_file (str, optional): Path for output .mp4 file. If None, uses same name as input
    
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
        
        # Try to use H.264 codec first (better quality)
        try:
            fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
            out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
            if not out.isOpened():
                raise Exception("H.264 codec not available")
        except:
            try:
                # Fallback to H.265 (HEVC)
                fourcc = cv2.VideoWriter_fourcc(*'hvc1')
                out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
                if not out.isOpened():
                    raise Exception("H.265 codec not available")
            except:
                # Final fallback to MPEG-4
                print("Warning: Using fallback MPEG-4 codec. Quality may be reduced.")
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
        
        # Process the video frame by frame
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Write the frame without any compression
            out.write(frame)
            
            # Update progress
            frame_count += 1
            if frame_count % 100 == 0:
                progress = (frame_count / total_frames) * 100
                print(f"Progress: {progress:.1f}%")
        
        # Release everything
        cap.release()
        out.release()
        
        print(f"Conversion completed! Output saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def batch_convert_directory(input_dir):
    """
    Convert all .dav files in a directory to .mp4
    
    Args:
        input_dir (str): Path to directory containing .dav files
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        print(f"Error: Directory '{input_dir}' not found.")
        return
        
    dav_files = list(input_dir.glob("*.dav"))
    if not dav_files:
        print("No .dav files found in the directory.")
        return
        
    print(f"Found {len(dav_files)} .dav files to convert.")
    for dav_file in dav_files:
        print(f"\nConverting: {dav_file}")
        convert_dav_to_mp4(str(dav_file))

if __name__ == "__main__":
