Filecoin Interop Runbook
========================

This runbook captures a reproducible checklist for validating py-libp2p against
real Filecoin peers. It is intentionally read-only: the examples dial, identify,
ping, and observe pubsub metadata without publishing Filecoin messages.

Preflight
---------

- Use Python 3.10+ and install the package with the Filecoin examples available.
- Run checks from a network that can reach public Filecoin bootstrap peers.
- Start with ``calibnet`` when possible; use ``mainnet`` only for read-only
  diagnostics.
- Keep QUIC/WebTransport addresses disabled unless the local transport stack has
  explicit support for them.

Handshake and protocol checks
----------------------------

Run identify and ping against a resolved bootstrap peer:

.. code-block:: console

    $ filecoin-ping-identify-demo --network calibnet --ping-count 3 --json

Record the following fields from the JSON output:

- ``connected`` is ``true``.
- ``identify.supports_filecoin_hello`` is ``true`` when the peer advertises
  ``/fil/hello/1.0.0``.
- ``identify.supports_filecoin_chain_exchange`` is ``true`` when the peer
  advertises ``/fil/chain/xchg/0.0.1``.
- ``ping.avg_rtt_us`` is present for basic round-trip visibility.

If dialing fails, retry with a specific peer from:

.. code-block:: console

    $ filecoin-dx bootstrap --network calibnet --runtime --resolve-dns --json

Pubsub observer checks
---------------------

Run the read-only observer:

.. code-block:: console

    $ filecoin-pubsub-demo --network calibnet --topic both --seconds 30 --json

Expected configuration:

- selected topics include ``/fil/blocks/calibrationnet`` and
  ``/fil/msgs/calibrationnet``.
- the mode is ``read_only_observer``.
- the message id constructor is the Filecoin Blake2b-256 payload hash configured
  by ``build_filecoin_pubsub``.
- the gossipsub mesh defaults match the Filecoin preset in
  ``libp2p.filecoin.pubsub``.

Interop matrix
--------------

.. list-table::
   :header-rows: 1

   * - Layer
     - Expected result
     - Failure mode to capture
   * - Address resolution
     - DNS bootstrap entries resolve to dialable TCP multiaddrs.
     - DNS lookup errors, unsupported transport, or no TCP fallback.
   * - Transport/security
     - TCP + Noise handshake completes.
     - timeout, peer id mismatch, or security negotiation failure.
   * - Identify
     - Peer advertises Filecoin hello and chain exchange protocols when
       supported.
     - missing protocol id, unexpected agent version, or identify timeout.
   * - Ping
     - Three ping RTTs complete within the configured timeout.
     - stream reset, protocol negotiation failure, or high packet loss.
   * - Pubsub
     - Observer subscribes to Filecoin topics without publishing.
     - gossipsub negotiation failure, validation rejection, or no inbound
       messages during the run window.

Reporting template
------------------

Use this short form when attaching results to an issue or pull request:

.. code-block:: text

    Network: calibnet
    Peer/client: <peer id or agent version>
    Transport: tcp/noise
    Identify: hello=<yes/no>, chain_exchange=<yes/no>
    Ping: avg_rtt_us=<value or n/a>
    Pubsub topics: blocks=<ok/fail>, messages=<ok/fail>
    Failure mode: <timeout/protocol mismatch/no messages/other>
    Command used: <exact command>
