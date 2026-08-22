# Filecoin-Style Gossipsub Configuration Notes

This note documents the changes made to examples/pubsub/pubsub.py,
which configures its GossipSub instance to match Filecoin/Lotus's
production mesh parameters, and adds a basic message validator.

## Mesh Parameters

| Parameter        | Old value | New value | What it controls |
|-------------------|-----------|-----------|-------------------|
| degree          | 3         | 8         | Target number of peers kept in the mesh for a topic. |
| degree_low      | 2         | 6         | Minimum mesh size before the router grafts (adds) more peers. |
| degree_high     | 4         | 12        | Maximum mesh size before the router prunes (drops) peers. |
| gossip_history  | 5         | 10        | Number of past heartbeat rounds of message IDs kept in memory, used to answer IWANT requests from peers catching up on missed messages. |

These values match Filecoin's Lotus client configuration, which tunes
gossipsub for fast, redundant block/transaction propagation across a
large peer-to-peer network.

## Message Validation

A validator function, `message_validator(peer_id, msg) -> bool`, is
registered on the topic via `pubsub.set_topic_validator(...)` in two
places in the file (the main subscribe call, and the auto-subscribe
loop for peer-announced topics).

The validator currently checks:
- **Empty messages** are rejected.
- **Oversized messages** (> 1 MiB) are rejected, matching the size
  assumption noted in Lotus's own source comments.

This mirrors the *shape* of Filecoin's real validation pipeline
(reject invalid messages before they propagate further), but is a
simplified stand-in - it does not perform real signature verification
like Filecoin's production validators do.

## Known Limitations

- This demo runs with **2 local peers**, so mesh grafting/pruning
  behavior (converging toward degree=8) is configured but not
  directly observable at this scale.
- Several other Filecoin/Lotus-specific gossipsub settings (flood
  publish, custom blake2b message-ID hashing, per-topic peer scoring,
  a subscription topic allowlist) are not implemented here - either
  because this constructor doesn't expose them, or because they were
  out of scope for this change.
- This is a learning/reference example, not a production-ready
  Filecoin network client.
