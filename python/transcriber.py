from openai import OpenAI
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def transcribe_audio(
    client: OpenAI, 
    file_path: str,
    language: str = "en",
    prompt: Optional[str] = None,
    temperature: float = 0.0,
    response_format: str = "verbose_json",
    timestamp_granularities: list = None,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Dict[str, Any]:
    """
    Transcribes an audio file using OpenAI's Whisper model with enhanced options
    for interview scenarios with Indian English speakers.
    
    Args:
        client: An initialized OpenAI client instance
        file_path: The path to the audio file to transcribe
        language: Language code (default: "en" for English)
        prompt: Optional prompt to guide transcription style and terminology
        temperature: Controls randomness (0.0 = deterministic, 1.0 = creative)
        response_format: "text", "json", "srt", "verbose_json", "vtt"
        timestamp_granularities: List of granularities for timestamps ["word", "segment"]
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        
    Returns:
        Dictionary containing transcription results and metadata
    """
    
    # Validate inputs
    if not _validate_file(file_path):
        raise ValueError(f"Invalid audio file: {file_path}")
    
    # Default timestamp granularities for interview analysis
    if timestamp_granularities is None:
        timestamp_granularities = ["word", "segment"]
    
    # Enhanced prompt for Indian English interview context
    if prompt is None:
        prompt = """This is an interview recording with an Indian English speaker. 
        Please transcribe accurately including natural speech patterns, pauses, 
        and any technical terms. Common Indian English pronunciations and 
        expressions should be transcribed as intended."""
    
    # Prepare transcription parameters
    transcription_params = {
        "model": "whisper-1",
        "language": language,
        "response_format": response_format,
        "temperature": temperature,
        "prompt": prompt
    }
    
    # Add timestamp granularities for verbose_json format
    if response_format == "verbose_json":
        transcription_params["timestamp_granularities"] = timestamp_granularities
    
    # Attempt transcription with retries
    for attempt in range(max_retries):
        try:
            logger.info(f"Transcription attempt {attempt + 1} for: {file_path}")
            
            with open(file_path, "rb") as audio_file:
                start_time = time.time()
                
                transcription = client.audio.transcriptions.create(
                    file=audio_file,
                    **transcription_params
                )
                
                processing_time = time.time() - start_time
                logger.info(f"Transcription completed in {processing_time:.2f} seconds")
                
                # Process and return results
                return _process_transcription_result(
                    transcription, 
                    file_path, 
                    processing_time,
                    response_format
                )
                
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            
            if attempt == max_retries - 1:
                logger.error(f"All transcription attempts failed for: {file_path}")
                raise
            
            # Wait before retry
            time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
    
    raise Exception("Transcription failed after all retry attempts")


def _validate_file(file_path: str) -> bool:
    """Validate audio file exists and has supported format."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    # Check file size (OpenAI has 25MB limit)
    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
    if file_size > 25:
        logger.error(f"File too large: {file_size:.1f}MB (max 25MB)")
        return False
    
    # Check supported formats
    supported_formats = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'}
    file_extension = Path(file_path).suffix.lower()
    
    if file_extension not in supported_formats:
        logger.error(f"Unsupported format: {file_extension}")
        return False
    
    return True


def _process_transcription_result(
    transcription, 
    file_path: str, 
    processing_time: float,
    response_format: str
) -> Dict[str, Any]:
    """Process transcription result and add metadata."""
    
    result = {
        "file_path": file_path,
        "processing_time": processing_time,
        "response_format": response_format,
        "timestamp": time.time()
    }
    
    if response_format == "verbose_json":
        result.update({
            "text": transcription.text,
            "language": transcription.language,
            "duration": transcription.duration,
            "words": getattr(transcription, 'words', []),
            "segments": getattr(transcription, 'segments', [])
        })
        
        # Calculate additional metrics
        result["word_count"] = len(transcription.text.split())
        result["speaking_rate"] = result["word_count"] / transcription.duration * 60  # words per minute
        
        # Analyze pause patterns if word-level timestamps available
        if hasattr(transcription, 'words') and transcription.words:
            result["pause_analysis"] = _analyze_pauses(transcription.words)
    
    elif response_format == "text":
        result["text"] = transcription
        result["word_count"] = len(transcription.split())
    
    else:
        result["content"] = transcription
    
    return result


def _analyze_pauses(words: list) -> Dict[str, Any]:
    """Analyze pause patterns in speech for interview evaluation."""
    if len(words) < 2:
        return {"pause_count": 0, "avg_pause_duration": 0, "long_pauses": []}
    
    pauses = []
    long_pauses = []  # Pauses longer than 2 seconds
    
    for i in range(1, len(words)):
        prev_end = words[i-1].get('end', 0)
        curr_start = words[i].get('start', 0)
        
        if prev_end and curr_start:
            pause_duration = curr_start - prev_end
            if pause_duration > 0.1:  # Ignore very short gaps
                pauses.append(pause_duration)
                
                if pause_duration > 2.0:  # Long pause
                    long_pauses.append({
                        "duration": pause_duration,
                        "position": curr_start,
                        "before_word": words[i-1].get('word', ''),
                        "after_word": words[i].get('word', '')
                    })
    
    return {
        "pause_count": len(pauses),
        "avg_pause_duration": sum(pauses) / len(pauses) if pauses else 0,
        "max_pause_duration": max(pauses) if pauses else 0,
        "long_pauses": long_pauses,
        "total_pause_time": sum(pauses)
    }


def batch_transcribe(
    client: OpenAI,
    file_paths: list,
    **kwargs
) -> Dict[str, Any]:
    """Transcribe multiple audio files in batch."""
    results = {}
    failed_files = []
    
    logger.info(f"Starting batch transcription of {len(file_paths)} files")
    
    for file_path in file_paths:
        try:
            result = transcribe_audio(client, file_path, **kwargs)
            results[file_path] = result
            logger.info(f"Successfully transcribed: {file_path}")
        except Exception as e:
            logger.error(f"Failed to transcribe {file_path}: {str(e)}")
            failed_files.append({"file": file_path, "error": str(e)})
    
    return {
        "successful_transcriptions": results,
        "failed_files": failed_files,
        "total_files": len(file_paths),
        "success_count": len(results),
        "failure_count": len(failed_files)
    }


# Example usage for interview transcription
def transcribe_interview(client: OpenAI, audio_file: str):
    """Specialized function for interview transcription with Indian English speakers."""
    
    interview_prompt = """This is a job interview recording with an Indian English speaker 
    responding to interview questions. Please transcribe accurately, maintaining natural 
    speech patterns including 'um', 'uh', pauses, and repetitions. Preserve technical 
    terms and Indian English expressions as spoken. Include natural hesitations and 
    self-corrections that show the candidate's thought process."""
    
    return transcribe_audio(
        client=client,
        file_path=audio_file,
        language="en",
        prompt=interview_prompt,
        temperature=0.0,  # More deterministic for consistency
        response_format="verbose_json",
        timestamp_granularities=["word", "segment"]
    )