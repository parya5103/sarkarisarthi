import pytest
from parser import summarize_job_description

def test_summarize_job_description_empty_or_none():
    """Test with empty string or None."""
    assert summarize_job_description("") == "No description available"
    assert summarize_job_description(None) == "No description available"

def test_summarize_job_description_short_text():
    """Test with text length less than 500."""
    text = "This is a short job description."
    assert summarize_job_description(text) == text

def test_summarize_job_description_exactly_500():
    """Test with text length exactly 500."""
    text = "a" * 500
    assert summarize_job_description(text) == text

def test_summarize_job_description_over_500():
    """Test with text length greater than 500."""
    text = "a" * 501
    expected = "a" * 497 + "..."
    assert summarize_job_description(text) == expected
    assert len(summarize_job_description(text)) == 500
