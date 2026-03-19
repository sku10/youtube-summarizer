"""Default prompts for YouTube video summarization."""

SYSTEM_PROMPT = """You are a helpful assistant that analyzes YouTube video transcripts.
Be concise, accurate, and well-structured in your responses.
Use markdown formatting for readability."""

EXECUTIVE_SUMMARY = """Provide an executive summary of this video transcript.
Include:
- What the video is about (1-2 sentences)
- The main argument or narrative
- Key conclusions or takeaways

Keep it under 200 words.

Transcript:
{transcript}"""

KEY_POINTS = """Extract the key points from this video transcript.
Format as a bulleted list of 5-10 main points.
Each point should be 1-2 sentences.
Order by importance, most important first.

Transcript:
{transcript}"""

CUSTOM = """Based on this video transcript, answer the following:

{user_prompt}

Transcript:
{transcript}"""

PROMPT_TYPES = {
    "executive_summary": EXECUTIVE_SUMMARY,
    "key_points": KEY_POINTS,
    "custom": CUSTOM,
}


def build_prompt(transcript_text: str, prompt_type: str = "executive_summary",
                 user_prompt: str = "", prompt_text: str = "") -> tuple[str, str]:
    """Build system + user prompt pair.

    If prompt_text is provided, use it directly (from stored prompt).
    Otherwise fall back to built-in prompt_type templates.

    Returns (system_prompt, user_prompt).
    """
    if prompt_text:
        user_msg = prompt_text + f"\n\nTranscript:\n{transcript_text}"
    else:
        template = PROMPT_TYPES.get(prompt_type, CUSTOM)
        user_msg = template.format(transcript=transcript_text, user_prompt=user_prompt)
    return SYSTEM_PROMPT, user_msg
