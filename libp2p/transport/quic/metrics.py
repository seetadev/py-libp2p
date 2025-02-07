from datetime import datetime

class QuicMetrics:
    """Metrics collection for QUIC connections."""
    
    def __init__(self):
        self.bytes_sent = 0
        self.bytes_received = 0
        self.streams_opened = 0
        self.streams_closed = 0
        self.connection_start_time = datetime.now()
        self.handshake_duration = None
        self.errors_count = 0
        
    def log_metrics(self):
        """Log current metrics."""
        logger.info(
            "quic_metrics",
            bytes_sent=self.bytes_sent,
            bytes_received=self.bytes_received,
            streams_opened=self.streams_opened,
            streams_closed=self.streams_closed,
            uptime=str(datetime.now() - self.connection_start_time),
            handshake_duration=str(self.handshake_duration) if self.handshake_duration else None,
            errors_count=self.errors_count
        )