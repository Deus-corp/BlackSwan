import os
import tempfile
import pytest
from src.core.ipfs_client import IPFSClient

@pytest.fixture
def ipfs_client():
    tmp_dir = tempfile.mkdtemp()
    client = IPFSClient(fallback_dir=tmp_dir)
    yield client
    import shutil
    shutil.rmtree(tmp_dir)

def test_add_and_get_json(ipfs_client):
    data = {"test": "value", "number": 42}
    cid = ipfs_client.add_json(data)
    assert isinstance(cid, str)
    assert len(cid) > 0
    restored = ipfs_client.get_json(cid)
    assert restored == data

def test_get_nonexistent(ipfs_client):
    assert ipfs_client.get_json("nonexistent_cid") is None

def test_add_json_returns_different_cids(ipfs_client):
    data1 = {"a": 1}
    data2 = {"b": 2}
    cid1 = ipfs_client.add_json(data1)
    cid2 = ipfs_client.add_json(data2)
    assert cid1 != cid2