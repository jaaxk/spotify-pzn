import subprocess
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def convert_mp3_to_wav(
    input_path: Path, 
    output_dir: Optional[Path] = None,
    sample_rate: int = 24000
) -> Path:
    """
    Convert an MP3 file to WAV format using ffmpeg.
    
    Args:
        input_path: Path to the input MP3 file
        output_dir: Directory to save the WAV file (defaults to same as input)
        sample_rate: Target sample rate in Hz
        
    Returns:
        Path to the converted WAV file
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Set output path
    if output_dir is None:
        output_dir = input_path.parent / "wav"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{input_path.stem}.wav"
    
    logger.info(f"Converting {input_path} to WAV format...")
    
    try:
        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-i", str(input_path),  # Input file
            "-t", "15",  # Limit to first 15 seconds
            "-ar", str(sample_rate),  # Sample rate
            "-ac", "1",  # Mono audio
            "-y",  # Overwrite output file if it exists
            "-loglevel", "warning",  # Only show warnings/errors
            str(output_path)
        ]
        
        # Run ffmpeg
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed with error: {result.stderr}"
            )
            
        logger.info(f"Successfully converted to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error converting {input_path}: {str(e)}")
        raise

def convert_directory(
    input_dir: Path, 
    output_dir: Optional[Path] = None,
    sample_rate: int = 24000
) -> list[Path]:
    """
    Convert all MP3 files in a directory to WAV format.
    """
    print(f"Converting directory: {input_dir}")
    if not input_dir.exists() or not input_dir.is_dir():
        print(' NO INPUT DIR')
        raise NotADirectoryError(f"Input directory not found: {input_dir}")
    
    output_dir.mkdir(exist_ok=True)
    
    converted_files = []
    for mp3_file in input_dir.glob("*.mp3"):
        print(f"Converting file: {mp3_file}")
        try:
            wav_path = convert_mp3_to_wav(mp3_file, output_dir, sample_rate)
            converted_files.append(wav_path)
        except Exception as e:
            logger.error(f"Failed to convert {mp3_file}: {e}")
            continue
            
    return converted_files