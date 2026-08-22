from __future__ import (
    annotations,
)

import pytest

from examples.decentralized_aggregation.demo import (
    main,
)


@pytest.mark.trio
async def test_decentralized_aggregation_demo() -> None:
    await main()
