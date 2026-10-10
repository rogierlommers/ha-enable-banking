# Enable Banking for Home Assistant

A HACS custom integration that connects Home Assistant to bank accounts through
the [Enable Banking API](https://enablebanking.com/docs/api/). It creates one
monetary balance sensor for every account returned by a bank connection.

Balance sensors opt in to Home Assistant long-term statistics, so their history
is available to History cards, statistics graphs, and automations without a
separate history database.

## Requirements

- Home Assistant 2025.1 or newer
- HACS
- An [Enable Banking](https://enablebanking.com/cp) application and its RSA
  private key
- A publicly reachable HTTPS Home Assistant external URL, such as a Home
  Assistant Cloud URL

This integration reads account information only. It does not fetch transactions
or initiate payments.

## Install

1. In HACS, add this repository as a custom **Integration** repository.
2. Install **Enable Banking** and restart Home Assistant.
3. In Enable Banking Control Panel, register an application. Add this exact
   redirect URL, replacing the origin with the external URL configured in Home
   Assistant:

   ```text
   https://your-home-assistant.example/api/enable_banking/callback
   ```

4. In Home Assistant, go to **Settings → Devices & services → Add integration**
   and select **Enable Banking**.
5. Paste the application ID and PEM private key, choose a country and bank, and
   complete authorization at the bank.

The Enable Banking application environment determines whether sandbox or
production bank connections are available. Production access may require
Enable Banking approval or a linked account.

## Sensors and history

Each account is represented as a Home Assistant device with one **Balance**
sensor. The sensor:

- uses the account's ISO 4217 currency as its unit;
- has the `monetary` device class and `total` state class;
- is refreshed hourly; and
- is retained by Home Assistant's recorder and long-term statistics.

When a bank returns multiple balances, the integration prefers interim
available (`ITAV`), closing available (`CLAV`), interim booked (`ITBD`), then
closing booked (`CLBD`). It falls back to the first valid balance.

History begins when the integration is installed. Enable Banking does not
provide historical balance samples through its balances endpoint, so earlier
balances cannot be backfilled reliably.

## Consent renewal

Bank consent has an expiry date. When it expires or is revoked, Home Assistant
marks the integration as requiring reauthentication. Open the integration and
complete the bank authorization again.

## Security

The RSA private key is a credential. Home Assistant stores it in the config
entry, which is not encrypted at rest. Protect Home Assistant's configuration
directory and backups. The key is never exposed as an entity attribute or in
integration diagnostics.

The callback accepts a one-time, high-entropy state value tied to the active
config flow. Authorization codes and private keys are not written to logs.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

## License

MIT
