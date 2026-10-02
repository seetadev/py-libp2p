import pytest
from py_libp2p.utils.network import parse_multiaddr, format_multiaddr, extract_peer_id, MultiaddrError

def test_multiaddr_parsing():
    # Test standard TCP
    addr = "/ip4/127.0.0.1/tcp/8080"
    parsed = parse_multiaddr(addr)
    assert str(parsed) == addr

    # Test DNS + PeerID
    dns_addr = "/dns4/google.com/tcp/443/p2p/QmExamplePeerID"
    parsed_dns = parse_multiaddr(dns_addr)
    assert str(parsed_dns) == dns_addr
    assert extract_peer_id(parsed_dns) == "QmExamplePeerID"

def test_invalid_multiaddr():
    with pytest.raises(MultiaddrError):
        parse_multiaddr("not-a-multiaddr")

def test_format_multiaddr():
    from multiaddr import Multiaddr
    maddr = Multiaddr("/ip4/1.1.1.1/tcp/1234")
    assert format_multiaddr(maddr) == "/ip4/1.1.1.1/tcp/1234"
    assert format_multiaddr("/ip4/1.1.1.1/tcp/1234") == "/ip4/1.1.1.1/tcp/1234"

def test_peer_id_extraction():
    addr = "/ip4/192.168.0.1/tcp/4001/p2p/QmTest123"
    assert extract_peer_id(addr) == "QmTest123"
    
    addr_no_peer = "/ip4/192.168.0.1/tcp/4001"
    assert extract_peer_id(addr_no_peer) is None
