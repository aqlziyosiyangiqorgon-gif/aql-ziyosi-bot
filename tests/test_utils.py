"""HTML utility tests."""

from gatebot.utils.html import escape_html


def test_escape_html():
    assert escape_html(None) == ""
    assert escape_html("") == ""
    assert escape_html("Hello <world> & 'friends' \"test\"") == "Hello &lt;world&gt; &amp; &#x27;friends&#x27; &quot;test&quot;"
    assert escape_html(12345) == "12345"
