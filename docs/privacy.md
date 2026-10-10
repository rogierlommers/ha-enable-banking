# Privacy notice

This privacy notice describes how the Enable Banking custom integration for
Home Assistant handles data. It is a generic notice for users of the
integration and contains no operator-specific information.

## Data processed by the integration

Depending on what the connected bank provides, the integration processes:

- the selected bank, bank country, and customer type;
- bank-account names, products, currencies, and opaque account identifiers;
- current and available account balances and the times they were reported;
- recent transaction dates, amounts, currencies, directions, statuses,
  counterparty names, and remittance text when the user enables transaction
  retrieval;
- Enable Banking application and session identifiers; and
- bank-consent status and expiry information.

Recent transaction retrieval is disabled by default. The integration does not
expose account numbers, provider transaction IDs, postal addresses, or raw
transaction payloads, and it does not initiate payments.

## Purpose

The data is processed only to:

- connect a bank account through Enable Banking;
- show current account balances in Home Assistant;
- optionally show a capped list of recent transaction summaries;
- create balance history and long-term statistics; and
- support dashboards, automations, maintenance, and troubleshooting within the
  user's Home Assistant installation.

## Storage and retention

The integration stores its configuration in the user's Home Assistant
installation. Balance states and statistics are stored by Home Assistant's
recorder. Recent transaction summaries are stored as sensor attributes and may
also be retained by the recorder. This data may be included in Home Assistant
backups.

Retention is controlled by the user's Home Assistant recorder, statistics, and
backup settings. Removing the integration does not automatically remove
historical states or existing backups.

The Enable Banking private RSA key is stored in the Home Assistant config entry
and may be included in backups. It is used locally to sign API requests. It is
not exposed as an entity attribute or included in integration diagnostics.

## Data sharing and external services

The integration communicates with Enable Banking and, through Enable Banking,
the bank selected by the user. Those services process data under their own
privacy notices and terms.

Installing this integration does not by itself send bank data to the developer
or maintainers of this repository. Other services used by the Home Assistant
installation—such as remote access, hosting, logging, or backup providers—may
process data according to the user's own configuration and those providers'
privacy notices.

## Security

Users are responsible for securing their Home Assistant installation,
configuration directory, backups, remote-access URL, and Enable Banking private
key. Access to entities and dashboards containing banking information should be
limited to authorized people.

## Revoking access and deleting data

Users can stop future access by removing the integration and revoking or
deleting the corresponding Enable Banking consent or session where available.
Historical Home Assistant states, long-term statistics, and backups must be
removed or expired separately according to the user's Home Assistant settings.

## Changes

This notice may be updated when the integration or its data handling changes.
The version history of this repository records changes to this document.
