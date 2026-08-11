"""
Tests for the rcmgr exceptions module.
"""

from __future__ import annotations

import pytest

from libp2p.rcmgr.exceptions import (
    InvalidResourceManagerState,
    MemoryLimitExceeded,
    ResourceLimitExceeded,
    ResourceManagerException,
    ResourceScopeClosed,
    ScopeClosedException,
    StreamOrConnLimitExceeded,
)


class TestResourceLimitExceeded:
    def test_base_resource_manager_exception(self) -> None:
        e = ResourceManagerException("boom")
        assert e.message == "boom"
        assert str(e) == "boom"
        assert isinstance(e, Exception)

    def test_resource_limit_exceeded_with_message(self) -> None:
        e = ResourceLimitExceeded(message="custom")
        assert str(e) == "custom"
        assert e.scope_name is None
        assert e.resource_type is None

    def test_resource_limit_exceeded_with_all_fields(self) -> None:
        e = ResourceLimitExceeded(
            scope_name="global",
            resource_type="connection",
            requested=10,
            available=5,
        )
        assert e.scope_name == "global"
        assert e.resource_type == "connection"
        assert e.requested == 10
        assert e.available == 5
        s = str(e)
        assert "global" in s
        assert "connection" in s
        assert "10" in s
        assert "5" in s

    def test_resource_limit_exceeded_default_message(self) -> None:
        e = ResourceLimitExceeded()
        assert str(e) == "Resource limit exceeded"


class TestScopeClosedException:
    def test_with_scope_name(self) -> None:
        e = ScopeClosedException(scope_name="my-scope")
        assert e.scope_name == "my-scope"
        assert "my-scope" in str(e)

    def test_with_message(self) -> None:
        e = ScopeClosedException(message="done")
        assert str(e) == "done"

    def test_default(self) -> None:
        e = ScopeClosedException()
        assert "closed" in str(e).lower()


class TestInvalidResourceManagerState:
    def test_message_only(self) -> None:
        e = InvalidResourceManagerState("bad state")
        assert str(e) == "bad state"
        assert isinstance(e, ResourceManagerException)


class TestLegacyExceptions:
    def test_memory_limit_exceeded(self) -> None:
        e = MemoryLimitExceeded(current=80, attempted=10, limit=100, priority=1)
        assert e.current == 80
        assert e.attempted == 10
        assert e.limit == 100
        assert e.priority == 1
        assert isinstance(e, ResourceLimitExceeded)
        assert "80" in str(e) and "10" in str(e) and "100" in str(e)

    def test_stream_or_conn_limit_exceeded(self) -> None:
        e = StreamOrConnLimitExceeded(
            current=3, attempted=2, limit=5, resource_type="stream"
        )
        assert e.current == 3
        assert e.attempted == 2
        assert e.limit == 5
        assert "stream" in str(e)
        assert isinstance(e, ResourceLimitExceeded)

    def test_resource_scope_closed_is_alias(self) -> None:
        e = ResourceScopeClosed(scope_name="x")
        assert isinstance(e, ScopeClosedException)
        assert e.scope_name == "x"

    @pytest.mark.parametrize(
        "exc",
        [
            ResourceLimitExceeded(),
            ScopeClosedException(),
            InvalidResourceManagerState("x"),
            MemoryLimitExceeded(1, 1, 1, 1),
            StreamOrConnLimitExceeded(1, 1, 1, "stream"),
        ],
    )
    def test_all_inherit_resource_manager_exception(self, exc: Exception) -> None:
        assert isinstance(exc, ResourceManagerException)
