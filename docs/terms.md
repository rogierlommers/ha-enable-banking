# Terms of use

These generic terms apply to use of the Enable Banking custom integration for
Home Assistant.

## Purpose of the integration

The integration connects Home Assistant to Enable Banking to retrieve
bank-account information and current balances. It exposes those balances as
Home Assistant sensors and allows Home Assistant to retain balance history and
long-term statistics. Users can optionally expose a capped list of recent
transaction summaries as sensor attributes.

The integration is provided for informational and personal automation purposes.
It does not provide financial, accounting, tax, legal, or investment advice.
The integration retrieves up to 10 recent transaction summaries per account by
default. Users can change this limit or disable transaction retrieval. The
integration does not initiate payments.

## Authorized use

Users may connect only accounts that they own or are authorized to access. They
are responsible for completing bank consent accurately and for complying with
the terms of Enable Banking and the selected bank.

Users must not use the integration to access another person's financial
information without appropriate authorization.

## User responsibilities

Users are responsible for:

- protecting Home Assistant credentials, backups, and the Enable Banking
  private key;
- restricting banking entities and dashboards to authorized people;
- keeping Home Assistant and the integration up to date;
- verifying important balances directly with the bank before relying on them;
  and
- revoking access when authorization to use an account ends.

## Availability and accuracy

The integration depends on Home Assistant, Enable Banking, the selected bank,
network connectivity, and active bank consent. Data may be delayed, incomplete,
temporarily unavailable, or different from the bank's official records.

Sensor values are not guaranteed to be real-time and must not be treated as
official bank statements.

## Third-party services

Enable Banking, the selected bank, Home Assistant, and any hosting,
remote-access, or backup providers are separate services. Their own terms and
privacy notices apply. The integration's developer and maintainers do not
control those services or their availability.

## Privacy

Data handling by the integration is described in the
[privacy notice](privacy.md).

## No warranty

The integration is open-source software provided "as is" and "as available",
without warranties of availability, accuracy, completeness, fitness for a
particular purpose, or uninterrupted operation, to the extent permitted by
applicable law.

## Limitation of responsibility

To the extent permitted by applicable law, the integration's contributors and
maintainers are not responsible for losses resulting from delayed or inaccurate
bank data, third-party outages, unauthorized access, configuration errors, or
loss of Home Assistant data or backups.

Rights and responsibilities that cannot legally be excluded remain unaffected.

## Ending use

Users may stop using the integration at any time. Removing it stops future
updates but does not automatically remove historical Home Assistant states,
long-term statistics, backups, or consent held by Enable Banking or the selected
bank.

## Changes

These terms may be updated when the integration or its dependencies change. The
version history of this repository records changes to this document.
