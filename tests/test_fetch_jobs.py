import pytest
from fetch_jobs import extract_trending_skills

def test_extract_trending_skills_empty_or_none():
    """Test with empty string or None."""
    assert extract_trending_skills("") == []
    assert extract_trending_skills(None) == []

def test_extract_trending_skills_no_match():
    """Test with text containing no keywords."""
    text = "This is a random text about gardening and cooking."
    assert extract_trending_skills(text) == []

def test_extract_trending_skills_single_match():
    """Test with a single keyword match."""
    text = "We are looking for a Python developer."
    assert extract_trending_skills(text) == ["Python"]

def test_extract_trending_skills_multiple_matches():
    """Test with multiple keyword matches."""
    text = "Required skills: Python, Java, and SQL."
    result = extract_trending_skills(text)
    assert sorted(result) == sorted(["Python", "Java", "Sql"])

def test_extract_trending_skills_case_insensitivity():
    """Test case insensitivity."""
    text = "python, JAVA, sQl"
    result = extract_trending_skills(text)
    assert sorted(result) == sorted(["Python", "Java", "Sql"])

def test_extract_trending_skills_multi_word_match():
    """Test multi-word keyword match."""
    text = "He has great communication skills."
    assert extract_trending_skills(text) == ["Communication Skills"]

def test_extract_trending_skills_uniqueness():
    """Test that duplicate keywords in text result in unique skills list."""
    text = "Python and more Python with some python."
    assert extract_trending_skills(text) == ["Python"]

def test_extract_trending_skills_mixed_content():
    """Test text with various skills including multi-word and overlapping."""
    text = """
    We need a candidate with Cloud experience, specifically AWS or Azure.
    Strong Communication Skills and leadership are must-haves.
    Knowledge of Artificial Intelligence and Machine Learning is a plus.
    """
    result = extract_trending_skills(text)
    expected = ["Cloud", "Aws", "Azure", "Communication Skills", "Leadership", "Artificial Intelligence", "Machine Learning"]
    assert sorted(result) == sorted(expected)

def test_extract_trending_skills_additional_skills():
    """Test more specific skills to cover edge cases"""
    text = "looking for devops, automation, and project management with agile methodologies like scrum"
    result = extract_trending_skills(text)
    expected = ["Devops", "Automation", "Project Management", "Agile", "Scrum"]
    assert sorted(result) == sorted(expected)

def test_extract_trending_skills_special_characters():
    """Test skills mixed with special characters."""
    text = "Skills required: C++, C#, Java! And maybe some SQL..."
    result = extract_trending_skills(text)
    expected = ["Java", "Sql"]
    assert sorted(result) == sorted(expected)
