import pytest

from applykit.jd_parser import (
    JDParseError,
    ParsedJD,
    detect_source_type,
    parse,
    strip_html,
)


def test_detect_url():
    assert detect_source_type("https://example.com/jobs/123") == "url"
    assert detect_source_type("http://example.com") == "url"


def test_detect_file_suffixes():
    assert detect_source_type("/path/to/jd.pdf") == "pdf"
    assert detect_source_type("C:/x/jd.docx") == "docx"
    assert detect_source_type("notes.txt") == "txt"


def test_detect_raw_text():
    blob = "We are hiring a Director of Engineering.\nResponsibilities include..."
    assert detect_source_type(blob) == "text"


def test_parse_text_roundtrip():
    parsed = parse("  Director of AI Safety. Lead a team.  ")
    assert isinstance(parsed, ParsedJD)
    assert parsed.source_type == "text"
    assert parsed.text == "Director of AI Safety. Lead a team."
    assert len(parsed.hash()) == 16


def test_parse_empty_text_raises():
    with pytest.raises(JDParseError):
        parse("   ")


def test_parse_missing_file_raises():
    with pytest.raises(JDParseError):
        parse("definitely_not_here.pdf")


def test_strip_html_removes_scripts_and_tags():
    html = "<html><head><style>.x{}</style></head><body><h1>Job</h1>" \
           "<script>evil()</script><p>Lead the team</p></body></html>"
    text = strip_html(html)
    assert "Job" in text
    assert "Lead the team" in text
    assert "evil" not in text
    assert ".x{}" not in text


def test_parse_txt_file(tmp_path):
    f = tmp_path / "jd.txt"
    f.write_text("Senior Director, Security", encoding="utf-8")
    parsed = parse(str(f))
    assert parsed.source_type == "txt"
    assert "Senior Director" in parsed.text
