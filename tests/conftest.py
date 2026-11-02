import pytest

from bvc.analysis import analyse
from bvc.data import connect, load_frames


@pytest.fixture(scope="session")
def con():
    return connect()


@pytest.fixture(scope="session")
def analysis(con):
    return analyse(con)


@pytest.fixture()
def raw_frames():
    nodes, groups = load_frames()
    return nodes.copy(), groups.copy()
