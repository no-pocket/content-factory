import pytest
from app.youtube import normalize_youtube_url, download_youtube

@pytest.mark.parametrize("url", [
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDabc",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
])
def test_normalize(url):
    assert normalize_youtube_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

@pytest.mark.parametrize("url", [
    "http://youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/playlist?list=PL123",
    "https://www.youtube.com/watch?v=bad",
    "https://user:password@www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com:123/watch?v=dQw4w9WgXcQ",
])
def test_reject(url):
    with pytest.raises(ValueError):
        normalize_youtube_url(url)


def test_download_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("ENABLE_YOUTUBE_DOWNLOAD", raising=False)
    with pytest.raises(PermissionError):
        download_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ", tmp_path)


def test_youtube_format_supports_separate_audio_video():
    # Downloader must allow DASH separate tracks rather than combined-only format.
    import inspect
    from app import youtube
    source = inspect.getsource(youtube.download_youtube)
    assert 'bestvideo[height<=720]+bestaudio' in source
    assert 'merge_output_format' in source
    assert 'js_runtimes' in source
