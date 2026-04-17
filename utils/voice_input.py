"""Voice input — Sprint 4 stub.

Will use the Web Speech API via a Streamlit custom component,
or a server-side Whisper model for transcription.
"""


def transcribe_audio(audio_bytes: bytes, language: str = "es-ES") -> str:
    """Transcribes audio bytes to text.

    Args:
        audio_bytes: Raw audio data (WAV or MP3).
        language:    BCP-47 language tag ('es-ES' or 'pt-PT').

    Returns:
        Transcribed text string, or empty string on failure.
    """
    raise NotImplementedError("Voice input will be implemented in Sprint 4.")
