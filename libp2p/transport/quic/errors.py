class QuicError(Exception):
    """Base class for all QUIC-related errors."""
    pass

class QuicStreamError(QuicError):
    """Errors related to QUIC streams."""
    pass

class QuicConnectionError(QuicError):
    """Errors related to QUIC connections."""
    pass

class QuicProtocolError(QuicError):
    """Errors related to QUIC protocol violations."""
    pass