---
title: Treat Enable Banking consent as an external config-flow step
date: 2026-10-10
category: architecture-patterns
module: Enable Banking authorization
problem_type: architecture_pattern
component: authentication
severity: high
applies_when:
  - Integrating Enable Banking account consent with Home Assistant
  - Handling an authorization-code redirect that is not a standard OAuth token flow
tags: [enable-banking, home-assistant, config-flow, authentication, callback]
---

# Treat Enable Banking consent as an external config-flow step

## Context

Enable Banking's account-information consent resembles OAuth: start an
authorization, redirect the user to a bank, and receive a `code` and `state`.
It is not Home Assistant's standard OAuth2 token lifecycle, though. API calls
are authenticated with short-lived JWTs signed locally by the application's RSA
private key, while the returned code creates an Enable Banking session.

Using Home Assistant's generic OAuth helper would therefore model the wrong
credential lifecycle and introduce refresh-token assumptions that the provider
does not satisfy.

## Guidance

Model consent as a Home Assistant external config-flow step:

1. Sign Enable Banking API requests with the configured application ID and RSA
   private key.
2. Generate a high-entropy, one-time state value and map it to the active flow
   ID in memory.
3. Require an external HTTPS Home Assistant URL and register the integration's
   callback path as the exact Enable Banking redirect URL.
4. Return `async_external_step` with Enable Banking's authorization URL.
5. At the unauthenticated callback, consume the state before forwarding only
   the expected callback fields to `flow.async_configure`.
6. Compare state again in the flow, exchange the code through `POST /sessions`,
   then finish with `async_external_step_done`.

The callback response should set `Cache-Control: no-store` and
`Referrer-Policy: no-referrer`. Never include the authorization code, private
key, session ID, or provider account identifiers in callback text, logs,
diagnostics, or entity attributes.

For consent expiry, raise `ConfigEntryAuthFailed` from a coordinator associated
with its config entry. Home Assistant then starts the integration's reauth flow
both during initial setup and after a later polling failure.

## Why This Matters

The public callback cannot require an authenticated Home Assistant browser
session because the bank controls the redirect. The one-time state value is
therefore the binding between the callback and the local setup attempt. Keeping
that mapping in memory avoids persisting transient authorization material, and
consuming it before code exchange prevents callback replay.

Separating application authentication from bank consent also makes renewal
correct: the RSA key continues to authenticate the application, while the user
repeats only the bank authorization needed to create a new session.

## When to Apply

- The provider redirects a browser with an authorization code but authenticates
  API requests using a separate locally signed credential.
- Home Assistant must complete the flow without storing transient codes.
- The callback must be reachable from outside the user's local network.

## Examples

The implementation is split across:

- `custom_components/enable_banking/api.py` for application JWT signing and
  session creation;
- `custom_components/enable_banking/config_flow.py` for state generation,
  external-step transitions, and reauthentication; and
- `custom_components/enable_banking/__init__.py` for the public one-time
  callback endpoint.

## Related

- [Enable Banking API reference](https://enablebanking.com/docs/api/reference/)
- [Home Assistant config-flow documentation](https://developers.home-assistant.io/docs/core/integration/config_flow/)
