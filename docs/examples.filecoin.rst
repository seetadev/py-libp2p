Filecoin DX Examples
====================

Read this first:

- :doc:`filecoin_architecture_positioning`

These examples show practical Filecoin-focused workflows using
``libp2p.filecoin``.

Connect to a Filecoin peer
--------------------------

.. code-block:: console

    $ filecoin-connect-demo --network mainnet --resolve-dns --json

.. literalinclude:: ../examples/filecoin/filecoin_connect_demo.py
    :language: python
    :linenos:

Ping + identify a Filecoin peer
-------------------------------

.. code-block:: console

    $ filecoin-ping-identify-demo --network calibnet --ping-count 3 --json

.. literalinclude:: ../examples/filecoin/filecoin_ping_identify_demo.py
    :language: python
    :linenos:

Read-only pubsub observer
-------------------------

This observer does not publish messages. It subscribes to Filecoin gossip
topics and reports inbound metadata.

.. code-block:: console

    $ filecoin-pubsub-demo --network mainnet --topic both --seconds 20

.. code-block:: console

    $ filecoin-pubsub-demo --network calibnet --topic blocks --max-messages 25 --json

.. literalinclude:: ../examples/filecoin/filecoin_pubsub_demo.py
    :language: python
    :linenos:

Local Filecoin-compatible gossipsub example
-------------------------------------------

Reference example for Filecoin-style pubsub — runs two local peers with
``build_filecoin_gossipsub`` presets (degree 8/6/12, heartbeat 1s, history 10).

Mesh parameters are documented inline and traceable to Lotus v1.35.0
``node/modules/lp2p/pubsub.go:24`` and Forest ``src/libp2p/gossip_params.rs:17``:

.. list-table::
   :header-rows: 1
   * - Param
     - Filecoin value
     - Default
   * - degree
     - 8
     - n/a
   * - degree_low
     - 6
     - n/a
   * - degree_high
     - 12
     - n/a
   * - heartbeat_interval
     - 1
     - 120
   * - gossip_window
     - 3
     - 3
   * - gossip_history
     - 10
     - 5
   * - time_to_live
     - 60
     - 60
   * - prune_back_off
     - 60 (bootstrapper 300)
     - 60
   * - do_px
     - False (bootstrapper True)
     - False

Message validation expectations: ``strict_signing=True``, ``msg_id`` is
``blake2b(payload)`` (32 bytes), topics ``/fil/blocks/<network>`` or
``/fil/msgs/<network>``, payload non-empty and ≤256 KiB (example validator).

.. code-block:: console

    $ python -m examples.filecoin.filecoin_gossipsub_example --network mainnet --topic blocks --verbose

.. literalinclude:: ../examples/filecoin/filecoin_gossipsub_example.py
    :language: python
    :linenos:

CLI helpers
-----------

.. code-block:: console

    $ filecoin-dx topics --network mainnet --json
    $ filecoin-dx bootstrap --network mainnet --runtime --resolve-dns --json
    $ python -m libp2p.filecoin preset --network calibnet --json
