Filecoin GossipSub reference example
-------------------------------------

Two local peers run a Filecoin-style GossipSub mesh over loopback
(degree 8, low/high watermarks 6/12, 1s heartbeat), using the same
score thresholds as Lotus/Forest. Messages are deduplicated with
Blake2b-256 message IDs (``filecoin_message_id``), and topic
validators reject bad payloads on ``/fil/blocks`` and ``/fil/msgs``.

.. code-block:: console

    $ python -m examples.filecoin.filecoin_gossipsub_example --network mainnet --topic both

.. code-block:: console

    $ python -m examples.filecoin.filecoin_gossipsub_example --network calibnet --topic blocks --json

.. literalinclude:: ../examples/filecoin/filecoin_gossipsub_example.py
    :language: python
    :linenos: