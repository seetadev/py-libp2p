"""
Tests for the rcmgr enhanced_errors module.
"""

from __future__ import annotations

import pytest
import multiaddr

from libp2p.peer.id import ID
from libp2p.rcmgr.enhanced_errors import (
    ConfigurationError,
    ErrorCategory,
    ErrorCode,
    ErrorContext,
    ErrorSeverity,
    OperationalError,
    ResourceLimitExceededError,
    SystemResourceError,
    create_configuration_error,
    create_connection_limit_error,
    create_memory_limit_error,
    create_operational_error,
)


def _peer(seed: int) -> ID:
    return ID(seed.to_bytes(32, "big"))


class TestEnums:
    def test_severity_values(self) -> None:
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_category_values(self) -> None:
        assert ErrorCategory.CONNECTION_LIMIT.value == "connection_limit"
        assert ErrorCategory.MEMORY_LIMIT.value == "memory_limit"

    def test_code_values(self) -> None:
        assert ErrorCode.CONNECTION_LIMIT_EXCEEDED.value == "CONN_001"
        assert ErrorCode.MEMORY_LIMIT_EXCEEDED.value == "MEM_001"


class TestErrorContext:
    def test_to_dict_with_minimal_fields(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.CONNECTION_LIMIT_EXCEEDED,
            error_category=ErrorCategory.CONNECTION_LIMIT,
            severity=ErrorSeverity.HIGH,
            message="test",
        )
        d = ctx.to_dict()
        assert d["error_code"] == "CONN_001"
        assert d["message"] == "test"
        assert d["peer_id"] is None
        assert d["remote_addr"] is None

    def test_to_dict_with_addresses(self) -> None:
        ma = multiaddr.Multiaddr("/ip4/1.2.3.4/tcp/4001")
        ctx = ErrorContext(
            error_code=ErrorCode.NETWORK_ERROR,
            error_category=ErrorCategory.NETWORK_ERROR,
            severity=ErrorSeverity.MEDIUM,
            message="x",
            peer_id=_peer(1),
            local_addr=ma,
            remote_addr=ma,
        )
        d = ctx.to_dict()
        assert d["peer_id"] == str(_peer(1))
        assert d["local_addr"] == str(ma)
        assert d["remote_addr"] == str(ma)

    def test_str(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.CONNECTION_LIMIT_EXCEEDED,
            error_category=ErrorCategory.CONNECTION_LIMIT,
            severity=ErrorSeverity.HIGH,
            message="limit",
        )
        s = str(ctx)
        assert "CONN_001" in s
        assert "limit" in s
        assert "high" in s


class TestResourceLimitExceededError:
    def test_message_with_limit_and_current(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.CONNECTION_LIMIT_EXCEEDED,
            error_category=ErrorCategory.CONNECTION_LIMIT,
            severity=ErrorSeverity.HIGH,
            message="boom",
            limit_type="connections",
            limit_value=10,
            current_value=10,
            resource_type="conn",
        )
        e = ResourceLimitExceededError(ctx)
        msg = str(e)
        assert "CONN_001" in msg
        assert "limit=10" in msg
        assert "current=10" in msg
        assert "[resource=conn]" in msg

    def test_message_with_connection_id(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.CONNECTION_LIMIT_EXCEEDED,
            error_category=ErrorCategory.CONNECTION_LIMIT,
            severity=ErrorSeverity.HIGH,
            message="x",
            limit_type="t",
            limit_value=1,
            current_value=1,
            connection_id="c1",
        )
        e = ResourceLimitExceededError(ctx)
        assert "[connection=c1]" in str(e)

    def test_message_with_peer(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.CONNECTION_LIMIT_EXCEEDED,
            error_category=ErrorCategory.CONNECTION_LIMIT,
            severity=ErrorSeverity.HIGH,
            message="x",
            limit_type="t",
            limit_value=1,
            current_value=1,
            peer_id=_peer(42),
        )
        e = ResourceLimitExceededError(ctx)
        assert "[peer=" in str(e)

    def test_error_summary(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.CONNECTION_LIMIT_EXCEEDED,
            error_category=ErrorCategory.CONNECTION_LIMIT,
            severity=ErrorSeverity.HIGH,
            message="x",
        )
        e = ResourceLimitExceededError(ctx, original_exception=ValueError("inner"))
        summary = e.get_error_summary()
        assert summary["error_code"] == "CONN_001"
        assert summary["has_original_exception"] is True


class TestSystemResourceError:
    def test_message_with_system_memory(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.MEMORY_LIMIT_EXCEEDED,
            error_category=ErrorCategory.MEMORY_LIMIT,
            severity=ErrorSeverity.CRITICAL,
            message="oom",
            system_memory_total=100,
            system_memory_percent=80.0,
            process_memory_bytes=80,
        )
        e = SystemResourceError(ctx)
        msg = str(e)
        assert "MEM_001" in msg
        assert "system_memory=100" in msg
        assert "process_memory=80" in msg


class TestConfigurationError:
    def test_message_includes_config_key(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.CONFIG_ERROR,
            error_category=ErrorCategory.CONFIG_ERROR,
            severity=ErrorSeverity.MEDIUM,
            message="bad config",
            metadata={"config_key": "max_connections", "config_value": "abc"},
        )
        e = ConfigurationError(ctx)
        assert "[config_key=max_connections]" in str(e)
        assert "[config_value=abc]" in str(e)


class TestOperationalError:
    def test_message_includes_operation_and_component(self) -> None:
        ctx = ErrorContext(
            error_code=ErrorCode.OPERATIONAL_ERROR,
            error_category=ErrorCategory.OPERATIONAL_ERROR,
            severity=ErrorSeverity.MEDIUM,
            message="boom",
            metadata={"operation": "start", "component": "tracker"},
        )
        e = OperationalError(ctx)
        msg = str(e)
        assert "[operation=start]" in msg
        assert "[component=tracker]" in msg


class TestFactoryCreateConnectionLimitError:
    @pytest.mark.parametrize(
        "limit_type, expected_code",
        [
            ("pending", ErrorCode.CONNECTION_PENDING_LIMIT_EXCEEDED),
            ("established", ErrorCode.CONNECTION_ESTABLISHED_LIMIT_EXCEEDED),
            ("per_peer", ErrorCode.CONNECTION_PER_PEER_LIMIT_EXCEEDED),
            ("total", ErrorCode.CONNECTION_TOTAL_LIMIT_EXCEEDED),
            ("unknown_kind", ErrorCode.CONNECTION_LIMIT_EXCEEDED),
        ],
    )
    def test_codes_per_kind(self, limit_type: str, expected_code: ErrorCode) -> None:
        e = create_connection_limit_error(
            limit_type=limit_type,
            limit_value=10,
            current_value=10,
        )
        assert isinstance(e, ResourceLimitExceededError)
        assert e.error_context.error_code == expected_code
        assert e.error_context.severity == ErrorSeverity.HIGH
        assert e.error_context.limit_percentage == 100.0

    def test_message_override(self) -> None:
        e = create_connection_limit_error(
            limit_type="total",
            limit_value=10,
            current_value=10,
            message="custom",
        )
        assert "custom" in str(e)

    def test_includes_peer_and_connection(self) -> None:
        e = create_connection_limit_error(
            limit_type="total",
            limit_value=10,
            current_value=10,
            connection_id="c1",
            peer_id=_peer(1),
        )
        assert e.error_context.connection_id == "c1"
        assert e.error_context.peer_id == _peer(1)

    def test_limit_value_zero_handled(self) -> None:
        # limit_percentage guarded against zero limit
        e = create_connection_limit_error(
            limit_type="total", limit_value=0, current_value=0
        )
        assert e.error_context.limit_percentage is None


class TestFactoryCreateMemoryLimitError:
    @pytest.mark.parametrize(
        "limit_type, expected_code",
        [
            ("process", ErrorCode.MEMORY_PROCESS_LIMIT_EXCEEDED),
            ("system", ErrorCode.MEMORY_SYSTEM_LIMIT_EXCEEDED),
            ("global", ErrorCode.MEMORY_LIMIT_EXCEEDED),
        ],
    )
    def test_codes_per_kind(self, limit_type: str, expected_code: ErrorCode) -> None:
        e = create_memory_limit_error(
            limit_type=limit_type,
            limit_value=1000,
            current_value=900,
        )
        assert isinstance(e, SystemResourceError)
        assert e.error_context.error_code == expected_code
        assert e.error_context.severity == ErrorSeverity.CRITICAL

    def test_system_memory_metrics(self) -> None:
        e = create_memory_limit_error(
            limit_type="process",
            limit_value=1000,
            current_value=900,
            system_memory_total=2000,
            system_memory_available=400,
            process_memory_bytes=900,
        )
        assert e.error_context.system_memory_percent == 80.0
        assert e.error_context.process_memory_percent == 45.0


class TestFactoryCreateConfigurationError:
    def test_creates_with_metadata(self) -> None:
        e = create_configuration_error(
            config_key="max", config_value=10, message="bad"
        )
        assert isinstance(e, ConfigurationError)
        assert e.error_context.metadata["config_key"] == "max"
        assert e.error_context.metadata["config_value"] == "10"
        assert "bad" in str(e)


class TestFactoryCreateOperationalError:
    def test_creates_with_metadata(self) -> None:
        e = create_operational_error(
            operation="dial", component="conn-mgr", message="failed"
        )
        assert isinstance(e, OperationalError)
        assert e.error_context.metadata["operation"] == "dial"
        assert e.error_context.metadata["component"] == "conn-mgr"
        assert "failed" in str(e)
