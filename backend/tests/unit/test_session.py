from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.db import session as session_module


def test_session_scope_commits_and_closes(
    monkeypatch: pytest.MonkeyPatch, unit_settings: Settings
) -> None:
    session = MagicMock()
    factory = MagicMock(return_value=session)
    monkeypatch.setattr(session_module, "session_factory", lambda _settings: factory)

    with session_module.session_scope(unit_settings) as yielded:
        assert yielded is session

    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()


def test_session_scope_rolls_back_and_closes(
    monkeypatch: pytest.MonkeyPatch, unit_settings: Settings
) -> None:
    session = MagicMock()
    factory = MagicMock(return_value=session)
    monkeypatch.setattr(session_module, "session_factory", lambda _settings: factory)

    with (
        pytest.raises(RuntimeError, match="test failure"),
        session_module.session_scope(unit_settings),
    ):
        raise RuntimeError("test failure")

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
