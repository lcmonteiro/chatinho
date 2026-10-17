## REMOVED Requirements

### Requirement: A say in a room with one peer that answers is asked of it
**Reason**: The rule moves into the default router, and it now sets the say's `to` instead of a separate `asked_of`, so the say is no longer kept a broadcast.
**Migration**: See `message-routing`, "The default router". A listener that filtered on `is_broadcast` checks `msg.to is None`, and stays quiet for a say the router gave to a peer.

### Requirement: A reply is asked of the peer it replies to
**Reason**: The rule moves into the default router, and it now sets `to`.
**Migration**: See `message-routing`, "The default router".

### Requirement: A message says who it was asked of
**Reason**: `asked_of` is removed. `to` is the only field that says whose `answer` is called, and an answer is addressed to nobody.
**Migration**: Read `msg.to` where `msg.asked_of` was read. See `message-routing`, "An answer is addressed to nobody".
