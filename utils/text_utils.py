"""
Text Utility Functions

Provides text manipulation and formatting utilities for Discord bot operations.
"""


def split_text_for_fields(text: str, max_length: int = 1024, split_on: str = '\n') -> list[str]:
    """
    Split text into chunks that fit Discord field value limits.

    Discord embeds have a field value limit of 1024 characters. This function intelligently
    splits longer text into multiple chunks while preserving readability by splitting on
    semantic boundaries (default: newlines).

    Args:
        text: Text to split into chunks
        max_length: Maximum characters per chunk (default 1024 for Discord field values)
        split_on: Character/string to split on for clean breaks (default newline)

    Returns:
        List of text chunks, each under max_length characters

    Examples:
        >>> short_text = "This is short"
        >>> split_text_for_fields(short_text)
        ['This is short']

        >>> long_text = "Line 1\\nLine 2\\nLine 3\\n..." * 100
        >>> chunks = split_text_for_fields(long_text, max_length=100)
        >>> all(len(chunk) <= 100 for chunk in chunks)
        True

        >>> # Custom delimiter
        >>> text = "Part 1. Part 2. Part 3."
        >>> split_text_for_fields(text, max_length=10, split_on='. ')
        ['Part 1.', 'Part 2.', 'Part 3.']

    Notes:
        - If text is already under max_length, returns single-item list
        - Splits on boundaries to preserve formatting (no mid-line breaks)
        - Trailing delimiters are removed from final chunks
        - Empty segments are preserved if they exist in original text
    """
    # Handle edge cases
    if not text:
        return ['']

    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = []
    current_length = 0

    # Split on the delimiter (e.g., '\n')
    segments = text.split(split_on)

    for i, segment in enumerate(segments):
        # Add delimiter back except for last segment
        is_last_segment = (i == len(segments) - 1)
        segment_with_delimiter = segment if is_last_segment else segment + split_on
        segment_length = len(segment_with_delimiter)

        # If adding this segment would exceed limit, start new chunk
        if current_length + segment_length > max_length and current_chunk:
            # Save current chunk
            chunks.append(''.join(current_chunk).rstrip(split_on))
            current_chunk = []
            current_length = 0

        # Handle edge case: single segment longer than max_length
        if segment_length > max_length:
            # Split mid-segment as last resort (shouldn't happen with reasonable max_length)
            if current_chunk:
                chunks.append(''.join(current_chunk).rstrip(split_on))
                current_chunk = []
                current_length = 0

            # Split the long segment into character chunks
            for j in range(0, len(segment_with_delimiter), max_length):
                chunks.append(segment_with_delimiter[j:j + max_length])
        else:
            # Add segment to current chunk
            current_chunk.append(segment_with_delimiter)
            current_length += segment_length

    # Add remaining chunk if any
    if current_chunk:
        chunks.append(''.join(current_chunk).rstrip(split_on))

    return chunks
