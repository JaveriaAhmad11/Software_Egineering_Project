"""Shared pytest setup: keep unit-test log lines out of the real logs/gemini.log.

The real log must hold real API calls only (team working agreement, and the
SCRUM-47 audit reads it), so during tests the file handler points to a temp file.
"""
import logging

import pytest

from agents import gemini_client as gc


@pytest.fixture(autouse=True, scope="session")
def _keep_test_logs_out_of_real_log(tmp_path_factory):
    real_handlers = [h for h in gc.log.handlers if isinstance(h, logging.FileHandler)]
    for handler in real_handlers:
        gc.log.removeHandler(handler)
    temp_handler = logging.FileHandler(tmp_path_factory.mktemp("logs") / "gemini.log",
                                       encoding="utf-8")
    gc.log.addHandler(temp_handler)
    yield
    gc.log.removeHandler(temp_handler)
    temp_handler.close()
    for handler in real_handlers:
        gc.log.addHandler(handler)
