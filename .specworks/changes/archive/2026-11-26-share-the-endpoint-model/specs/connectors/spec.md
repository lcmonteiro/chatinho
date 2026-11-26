# Spec Delta: connectors

## REMOVED Requirements

### Requirement: REQ-CONN-027 The model an Endpoint becomes takes a key per call

**Reason**: The model is now shared by every component that calls one, so its
behaviour belongs to the `models` capability.

**Migration**: Unchanged behaviour as REQ-MODEL-003; `EndpointModel(endpoint).chat_model()`
gives the same chat model, which an agent built from an `Endpoint` still uses.
