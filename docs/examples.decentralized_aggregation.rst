Decentralized Aggregation Demo
==============================

This example demonstrates decentralized model aggregation strategies for federated learning in ``py-libp2p``, eliminating the single point of failure inherent in centralized parameter servers.

It provides two strategies:

1. **Round-Robin Leader Rotation**: Peers take turns aggregating model weights each round (``leader = participants[round % N]``). Updates can be weighted by local sample counts, and a quorum timeout prevents slow peers from stalling training.
2. **Gossip Averaging**: An asynchronous, leaderless diffusion protocol where peers continuously broadcast weights to a GossipSub topic and mix incoming weights locally (``w_local = (1 - γ) * w_local + γ * w_remote``).

Running the Demo
----------------

After installing py-libp2p (``pip install -e .`` from a checkout, or ``pip install libp2p``), you can run the demo as a console script:

.. code-block:: console

    $ decentralized-aggregation-demo

From a source checkout you can also run:

.. code-block:: console

    $ python examples/decentralized_aggregation/demo.py

Source Code
-----------

.. literalinclude:: ../examples/decentralized_aggregation/demo.py
    :language: python
    :linenos:

API Reference
-------------

Submodules
~~~~~~~~~~

examples.decentralized\_aggregation.demo module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: examples.decentralized_aggregation.demo
   :members:
   :show-inheritance:
   :undoc-members:

Package contents
~~~~~~~~~~~~~~~~

.. automodule:: examples.decentralized_aggregation
   :members:
   :show-inheritance:
   :undoc-members:
