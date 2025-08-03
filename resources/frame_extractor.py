import cv2
import os
from pathlib import Path
from typing import Optional, Tuple, List
import glob

def extract_frames(
    video_path: str,
    frame_elapsed: int = 30,
    output_dir: Optional[str] = None,
    max_frames: Optional[int] = None,
    resize: Optional[Tuple[int, int]] = None
) -> bool:
    """
    Extract frames from a video at specified intervals and save them to disk.

    Args:
        video_path (str): Path to the input video file
        frame_elapsed (int): Extract every N frames (default: 30)
        output_dir (str, optional): Output directory path. If None, uses 'resources/frames'
        max_frames (int, optional): Maximum number of frames to extract. If None, extracts all
        resize (tuple, optional): Resize frames to (width, height). If None, keeps original size

    Returns:
        bool: True if extraction was successful, False otherwise
    """

    # Set default output directory
    if output_dir is None:
        script_dir = Path(__file__).parent
        output_dir = script_dir / "frames"
    else:
        output_dir = Path(output_dir)

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if video file exists
    if not os.path.exists(video_path):
        print(f"Error: Video file '{video_path}' not found.")
        return False

    # Open video capture
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Could not open video file '{video_path}'.")
        return False

    # Get video properties
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0

    print(f"Video info:")
    print(f"  - Total frames: {total_frames}")
    print(f"  - FPS: {fps:.2f}")
    print(f"  - Duration: {duration:.2f} seconds")
    print(f"  - Extracting every {frame_elapsed} frames")

    frame_count = 0
    extracted_count = 0

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                break

            # Extract frame if it's at the specified interval
            if frame_count % frame_elapsed == 0:
                # Resize frame if specified
                if resize is not None:
                    frame = cv2.resize(frame, resize)

                # Generate filename with zero-padding
                filename = f"frame_{extracted_count:06d}.jpg"
                filepath = output_dir / filename

                # Save frame
                success = cv2.imwrite(str(filepath), frame)

                if success:
                    extracted_count += 1
                    if extracted_count % 10 == 0:  # Progress update every 10 frames
                        print(f"Extracted {extracted_count} frames...")
                else:
                    print(f"Warning: Failed to save frame {extracted_count}")

                # Check if we've reached the maximum number of frames
                if max_frames is not None and extracted_count >= max_frames:
                    print(f"Reached maximum frame limit ({max_frames})")
                    break

            frame_count += 1

    except Exception as e:
        print(f"Error during frame extraction: {e}")
        return False

    finally:
        cap.release()

    print(f"Frame extraction completed!")
    print(f"  - Total frames processed: {frame_count}")
    print(f"  - Frames extracted: {extracted_count}")
    print(f"  - Output directory: {output_dir}")

    return True


def extract_frames_from_timestamp(
    video_path: str,
    start_time: float,
    end_time: float,
    frame_elapsed: int = 30,
    output_dir: Optional[str] = None
) -> bool:
    """
    Extract frames from a video between specific timestamps.

    Args:
        video_path (str): Path to the input video file
        start_time (float): Start time in seconds
        end_time (float): End time in seconds
        frame_elapsed (int): Extract every N frames (default: 30)
        output_dir (str, optional): Output directory path. If None, uses 'resources/frames'

    Returns:
        bool: True if extraction was successful, False otherwise
    """

    # Set default output directory
    if output_dir is None:
        script_dir = Path(__file__).parent
        output_dir = script_dir / "frames"
    else:
        output_dir = Path(output_dir)

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if video file exists
    if not os.path.exists(video_path):
        print(f"Error: Video file '{video_path}' not found.")
        return False

    # Open video capture
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Could not open video file '{video_path}'.")
        return False

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    # Validate timestamps
    if start_time < 0 or end_time > duration or start_time >= end_time:
        print(f"Error: Invalid timestamps. Video duration: {duration:.2f}s")
        return False

    # Calculate frame numbers
    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)

    print(f"Extracting frames from {start_time}s to {end_time}s")
    print(f"Frame range: {start_frame} to {end_frame}")

    # Set video position to start frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frame_count = start_frame
    extracted_count = 0

    try:
        while frame_count <= end_frame:
            ret, frame = cap.read()

            if not ret:
                break

            # Extract frame if it's at the specified interval
            if (frame_count - start_frame) % frame_elapsed == 0:
                # Generate filename with timestamp info
                timestamp = frame_count / fps
                filename = f"frame_{extracted_count:06d}_t{timestamp:.2f}s.jpg"
                filepath = output_dir / filename

                # Save frame
                success = cv2.imwrite(str(filepath), frame)

                if success:
                    extracted_count += 1
                else:
                    print(f"Warning: Failed to save frame {extracted_count}")

            frame_count += 1

    except Exception as e:
        print(f"Error during frame extraction: {e}")
        return False

    finally:
        cap.release()

    print(f"Frame extraction completed!")
    print(f"  - Frames extracted: {extracted_count}")
    print(f"  - Output directory: {output_dir}")

    return True


def extract_frames_from_all_videos(
    videos_dir: Optional[str] = None,
    frame_elapsed: int = 30,
    max_frames_per_video: Optional[int] = None,
    resize: Optional[Tuple[int, int]] = None
) -> bool:
    """
    Extract frames from all videos in the specified directory.

    Args:
        videos_dir (str, optional): Directory containing videos. If None, uses 'resources/full_videos'
        frame_elapsed (int): Extract every N frames (default: 30)
        max_frames_per_video (int, optional): Maximum number of frames to extract per video
        resize (tuple, optional): Resize frames to (width, height). If None, keeps original size

    Returns:
        bool: True if extraction was successful for at least one video, False otherwise
    """

    # Set default videos directory
    if videos_dir is None:
        script_dir = Path(__file__).parent
        videos_dir = script_dir / "full_videos"
    else:
        videos_dir = Path(videos_dir)

    # Check if videos directory exists
    if not videos_dir.exists():
        print(f"Error: Videos directory '{videos_dir}' not found.")
        return False

    # Common video file extensions
    video_extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.flv', '*.wmv', '*.m4v']

    # Find all video files
    video_files = []
    for extension in video_extensions:
        video_files.extend(videos_dir.glob(extension))
        video_files.extend(videos_dir.glob(extension.upper()))  # Include uppercase extensions

    if not video_files:
        print(f"No video files found in '{videos_dir}'")
        return False

    print(f"Found {len(video_files)} video files in '{videos_dir}':")
    for i, video_file in enumerate(video_files, 1):
        print(f"  {i}. {video_file.name}")

    successful_extractions = 0

    for i, video_file in enumerate(video_files, 1):
        print(f"\n{'='*60}")
        print(f"Processing video {i}/{len(video_files)}: {video_file.name}")
        print(f"{'='*60}")

        # Create a unique output directory for each video
        video_name_clean = video_file.stem.replace(' ', '_').replace('-', '_')
        output_dir = Path(__file__).parent / "frames" / video_name_clean

        try:
            success = extract_frames(
                video_path=str(video_file),
                frame_elapsed=frame_elapsed,
                output_dir=str(output_dir),
                max_frames=max_frames_per_video,
                resize=resize
            )

            if success:
                successful_extractions += 1
                print(f"✅ Successfully extracted frames from '{video_file.name}'")
            else:
                print(f"❌ Failed to extract frames from '{video_file.name}'")

        except Exception as e:
            print(f"❌ Error processing '{video_file.name}': {e}")

    print(f"\n{'='*60}")
    print(f"EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total videos found: {len(video_files)}")
    print(f"Successfully processed: {successful_extractions}")
    print(f"Failed: {len(video_files) - successful_extractions}")

    return successful_extractions > 0


def list_videos_in_directory(videos_dir: Optional[str] = None) -> List[Path]:
    """
    List all video files in the specified directory.

    Args:
        videos_dir (str, optional): Directory containing videos. If None, uses 'resources/full_videos'

    Returns:
        List[Path]: List of video file paths
    """

    # Set default videos directory
    if videos_dir is None:
        script_dir = Path(__file__).parent
        videos_dir = script_dir / "full_videos"
    else:
        videos_dir = Path(videos_dir)

    # Check if videos directory exists
    if not videos_dir.exists():
        print(f"Error: Videos directory '{videos_dir}' not found.")
        return []

    # Common video file extensions
    video_extensions = ['*.mp4', '*.avi', '*.mov', '*.mkv', '*.flv', '*.wmv', '*.m4v']

    # Find all video files
    video_files = []
    for extension in video_extensions:
        video_files.extend(videos_dir.glob(extension))
        video_files.extend(videos_dir.glob(extension.upper()))  # Include uppercase extensions

    # Sort files by name
    video_files.sort(key=lambda x: x.name.lower())

    return video_files


def get_video_info(video_path: str) -> dict:
    """
    Get basic information about a video file.

    Args:
        video_path (str): Path to the video file

    Returns:
        dict: Dictionary containing video information
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return {"error": f"Could not open video file '{video_path}'"}

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        # Get file size
        file_size = Path(video_path).stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        return {
            "filename": Path(video_path).name,
            "total_frames": total_frames,
            "fps": round(fps, 2),
            "width": width,
            "height": height,
            "duration_seconds": round(duration, 2),
            "duration_formatted": f"{int(duration // 60)}:{int(duration % 60):02d}",
            "file_size_mb": round(file_size_mb, 2)
        }

    finally:
        cap.release()


if __name__ == "__main__":
    # Example usage options:

    # Option 1: List all videos in full_videos directory
    print("Videos found in full_videos directory:")
    videos = list_videos_in_directory()
    for i, video in enumerate(videos, 1):
        print(f"{i}. {video.name}")
        info = get_video_info(str(video))
        if "error" not in info:
            print(f"   Duration: {info['duration_formatted']}, Size: {info['file_size_mb']} MB")

    print("\n" + "="*60)

    # Option 2: Extract frames from all videos (uncomment to run)
    success = extract_frames_from_all_videos(
        frame_elapsed=3 * 60,  # Extract every 60th frame (every ~2 seconds for 30fps video)
        max_frames_per_video=150  # Limit to 50 frames per video
    )

    # # Option 3: Extract frames from a single video (current behavior)
    # video_path = "avp_front_1.mp4"  # Relative to this script's directory
    #
    # # Extract every 30th frame
    # success = extract_frames(
    #     video_path=video_path,
    #     frame_elapsed=30,
    #     max_frames=100  # Limit to first 100 extracted frames
    # )

    if success:
        print("Frame extraction successful!")
    else:
        print("Frame extraction failed!")
