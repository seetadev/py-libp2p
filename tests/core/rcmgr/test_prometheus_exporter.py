"""
Tests for the rcmgr prometheus_exporter module.
"""

from __future__ import annotations

import pytest

from libp2p.rcmgr.metrics import Metrics
from libp2p.rcmgr.prometheus_exporter import (
    PROMETHEUS_AVAILABLE,
    PrometheusExporter,
    create_prometheus_exporter,
)

if not PROMETHEUS_AVAILABLE:
    pytest.skip("prometheus_client not installed", allow_module_level=True)


@pytest.fixture
def exporter() -> PrometheusExporter:
    return PrometheusExporter(
        port=0, enable_server=False
    )  # don't bind any port


class TestPrometheusExporterInit:
    def test_starts_with_zero_state(self, exporter: PrometheusExporter) -> None:
        assert exporter._peer_connections == {}
        assert exporter._peer_streams == {}
        assert exporter._peer_memory == {}
        assert exporter._conn_memory == {}
        assert exporter._running is False

    def test_metric_objects_exist(self, exporter: PrometheusExporter) -> None:
        assert exporter.connections is not None
        assert exporter.streams is not None
        assert exporter.memory is not None
        assert exporter.fds is not None
        assert exporter.blocked_resources is not None
        assert exporter.peer_connections is not None
        assert exporter.previous_peer_connections is not None
        assert exporter.peer_streams is not None
        assert exporter.previous_peer_streams is not None
        assert exporter.peer_memory is not None
        assert exporter.previous_peer_memory is not None
        assert exporter.conn_memory is not None
        assert exporter.previous_conn_memory is not None


class TestPrometheusExporterUpdateFromMetrics:
    def test_updates_gauges(self, exporter: PrometheusExporter) -> None:
        m = Metrics()
        exporter.update_from_metrics(m)
        # Connections should be set to 0 initially
        v = exporter.connections.labels(dir="inbound", scope="system")._value._value
        assert v == 0

    def test_tracks_summary(self, exporter: PrometheusExporter) -> None:
        m = Metrics()
        exporter.update_from_metrics(m)
        # blocked_resources should reflect metrics summary
        v = exporter.blocked_resources.labels(
            dir="", scope="system", resource="connection"
        )._value._value
        assert v == 0


class TestPrometheusExporterRecordEvents:
    def test_record_blocked_resource(self, exporter: PrometheusExporter) -> None:
        exporter.record_blocked_resource("inbound", "system", "connection", count=3)
        v = exporter.blocked_resources.labels(
            dir="inbound", scope="system", resource="connection"
        )._value._value
        assert v == 3
        # Subsequent calls accumulate on top of the current value
        exporter.record_blocked_resource("inbound", "system", "connection", count=2)
        v = exporter.blocked_resources.labels(
            dir="inbound", scope="system", resource="connection"
        )._value._value
        assert v == 5

    def test_record_peer_connections_increases(self, exporter: PrometheusExporter) -> None:
        exporter.record_peer_connections("peer-a", "inbound", 0, 4)
        assert exporter._peer_connections["peer-a"]["inbound"] == 4
        exporter.record_peer_connections("peer-a", "inbound", 4, 6)
        assert exporter._peer_connections["peer-a"]["inbound"] == 6

    def test_record_peer_connections_same_value(self, exporter: PrometheusExporter) -> None:
        # old == new should not add observations
        exporter.record_peer_connections("peer-a", "inbound", 3, 3)
        assert exporter._peer_connections["peer-a"]["inbound"] == 3

    def test_record_peer_streams(self, exporter: PrometheusExporter) -> None:
        exporter.record_peer_streams("peer-b", "outbound", 0, 2)
        assert exporter._peer_streams["peer-b"]["outbound"] == 2

    def test_record_peer_memory(self, exporter: PrometheusExporter) -> None:
        exporter.record_peer_memory("peer-c", 0, 1024)
        assert exporter._peer_memory["peer-c"] == 1024
        exporter.record_peer_memory("peer-c", 1024, 2048)
        assert exporter._peer_memory["peer-c"] == 2048

    def test_record_conn_memory(self, exporter: PrometheusExporter) -> None:
        exporter.record_conn_memory("conn-1", 0, 4096)
        assert exporter._conn_memory["conn-1"] == 4096


class TestPrometheusExporterAccessors:
    def test_get_metrics_text_returns_bytes(self, exporter: PrometheusExporter) -> None:
        text = exporter.get_metrics_text()
        assert isinstance(text, str)
        # The metrics payload should mention at least one of the declared metrics
        assert "libp2p_rcmgr" in text

    def test_get_metrics_content_type(self, exporter: PrometheusExporter) -> None:
        from prometheus_client import CONTENT_TYPE_LATEST

        assert exporter.get_metrics_content_type() == CONTENT_TYPE_LATEST

    def test_reset_clears_tracking(self, exporter: PrometheusExporter) -> None:
        exporter.record_peer_memory("p", 0, 100)
        exporter.record_conn_memory("c", 0, 200)
        exporter.record_peer_connections("p", "inbound", 0, 1)
        exporter.record_peer_streams("p", "outbound", 0, 1)
        exporter.reset()
        assert exporter._peer_connections == {}
        assert exporter._peer_streams == {}
        assert exporter._peer_memory == {}
        assert exporter._conn_memory == {}

    def test_start_server_no_op_when_disabled(self, exporter: PrometheusExporter) -> None:
        # enable_server was False in the fixture, so start_server must be a no-op
        exporter.start_server()
        assert exporter._running is False
        assert exporter._server_thread is None


class TestPrometheusExporterFactory:
    def test_create_returns_instance(self) -> None:
        ex = create_prometheus_exporter(port=0, enable_server=False)
        assert isinstance(ex, PrometheusExporter)

    def test_create_handles_failure(self) -> None:
        # Force a failure by passing a closed/None registry placeholder
        class _BrokenExporter:
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("boom")

        # Patch PrometheusExporter to always raise
        import libp2p.rcmgr.prometheus_exporter as mod

        original = mod.PrometheusExporter
        mod.PrometheusExporter = _BrokenExporter  # type: ignore[assignment]
        try:
            result = create_prometheus_exporter(port=0, enable_server=False)
            assert result is None
        finally:
            mod.PrometheusExporter = original  # type: ignore[assignment]
