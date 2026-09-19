import pytest

from wealth_lab import db


@pytest.fixture
def conn(tmp_path):
    with db.connect(tmp_path / "test.db") as connection:
        yield connection
