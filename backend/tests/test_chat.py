import pytest

from app import chat


def test_dm_channel_is_order_independent():
    assert chat.dm_channel("b@x.com", "A@x.com") == chat.dm_channel("a@x.com", "b@x.com") == "dm:a@x.com|b@x.com"


def test_normalize_channel():
    assert chat.normalize_channel("dm:z@x.com|a@x.com") == "dm:a@x.com|z@x.com"
    assert chat.normalize_channel("team:Client Services") == "team:Client Services"
    with pytest.raises(ValueError):
        chat.normalize_channel("team:Not A Team")
    with pytest.raises(ValueError):
        chat.normalize_channel("dm:only-one@x.com")
