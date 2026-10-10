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

   Use the external URL configured under **Settings → System → Network → Home
   Assistant URL**. For example, with Home Assistant Cloud/Nabu Casa:

   ```text
   https://your-id.ui.nabu.casa/api/enable_banking/callback
   ```

   The redirect URL must:

   - use the publicly reachable HTTPS URL for your Home Assistant instance;
   - end in `/api/enable_banking/callback`;
   - match exactly, including the scheme and hostname; and
   - not have a trailing slash.

   Do not use an internal address such as `http://homeassistant.local:8123`, a
   private IP address, or an internal-only hostname. The first Enable Banking
   setup screen in Home Assistant also displays the exact callback URL expected
   by the integration, so you can open the setup flow before registering the
   Enable Banking application and copy it from there.

   To check external reachability, open the callback URL from outside your home
   network. An `Invalid or expired authorization request` response is expected
   when no setup flow is active and confirms that the callback endpoint can be
   reached.

4. In Home Assistant, go to **Settings → Devices & services → Add integration**
   and select **Enable Banking**.
5. Paste the application ID and PEM private key, choose a country and bank, and
   complete authorization at the bank.

The Enable Banking application environment determines whether sandbox or
production bank connections are available. Production access may require
Enable Banking approval or a linked account.

### Enable Banking application field guide

Open [Enable Banking Control Panel](https://enablebanking.com/cp), go to
**API applications**, and create a new application. The form is divided into
the following sections.

#### 1. Application environment

Choose one of these environments:

- **Sandbox** — recommended while installing or testing the integration. The
  application is activated automatically and connects only to supported test
  banks and sandbox accounts.
- **Production** — use this to connect real bank accounts. Enable Banking may
  require approval, contractual details, or a linked/whitelisted bank account
  before the application becomes active.

Sandbox and production applications are separate. An application cannot be
switched from one environment to the other later, so create a new production
application after sandbox testing succeeds.

#### 2. RSA key and certificate

The private RSA key signs every API request made by Home Assistant. For most
users, select:

**Generate in the browser (using SubtleCrypto) and export private key**

When registration completes, the browser downloads a PEM file, usually named
after the generated application ID:

```text
aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.pem
```

Keep this file private and backed up securely. Open it in a text editor and
paste its complete contents—including the `BEGIN` and `END` lines—into the
**Private RSA key (PEM)** field in Home Assistant. Do not commit it to this
repository, upload it to a public location, or share it. Enable Banking cannot
reconstruct the private key if it is lost.

The alternative **Generate outside the browser and import public certificate**
is intended for advanced users who manage their own key material. For example:

```bash
openssl genrsa -out enable-banking-private.pem 4096
openssl req -new -x509 -days 365 \
  -key enable-banking-private.pem \
  -out enable-banking-public.crt \
  -subj "/C=NL/O=Home Assistant/CN=home.example.com"
```

Upload only `enable-banking-public.crt` to Enable Banking. Paste the contents of
`enable-banking-private.pem` into Home Assistant. Never upload the private key.

#### 3. Application information

Fill in the application fields as follows. Replace all example domains and
email addresses with values you control.

| Enable Banking field | What to enter | Example |
| --- | --- | --- |
| **Application name** | A recognizable name. This may be shown by Enable Banking during bank consent. | `Home Assistant – Personal banking` |
| **Allowed redirect URLs (one per line)** | The exact public HTTPS Home Assistant callback URL. Add one URL per line if you have more than one explicitly supported external hostname. Do not add a trailing slash. | `https://your-id.ui.nabu.casa/api/enable_banking/callback` |
| **Application description** | A short, accurate explanation of the read-only integration. Required for production applications. | `Read-only Home Assistant integration that retrieves my account names and current balances for local dashboards and history.` |
| **Email for data protection matters** | A monitored email address for privacy or data-protection questions. Required for production applications. | `privacy@example.com` |
| **Privacy URL of the application** | A public HTTPS privacy notice. This repository provides a generic notice that all integration users may reference. Required for production applications. | `https://github.com/rogierlommers/ha-enable-banking/blob/main/docs/privacy.md` |
| **Terms URL of the application** | A public HTTPS terms page. This repository provides generic terms that all integration users may reference. Required for production applications. | `https://github.com/rogierlommers/ha-enable-banking/blob/main/docs/terms.md` |

For a private, single-household installation, the data-protection email may be
your own monitored email address. The generic [privacy notice](docs/privacy.md)
and [terms of use](docs/terms.md) contain no personal information and may be
used by all users of this integration. Review them before production use to
confirm that they are appropriate for your situation; they are not legal advice.

The callback URL always has this form:

```text
<Home Assistant external HTTPS URL>/api/enable_banking/callback
```

Examples:

```text
https://your-id.ui.nabu.casa/api/enable_banking/callback
https://home.example.com/api/enable_banking/callback
```

Do **not** enter any of these:

```text
http://homeassistant.local:8123/api/enable_banking/callback
http://192.168.1.10:8123/api/enable_banking/callback
https://home.example.com/api/enable_banking/callback/
```

The first two are not publicly reachable HTTPS URLs. The last one has an extra
trailing slash and does not exactly match the callback URL generated by the
integration.

#### 4. After registering the application

Keep these two values for Home Assistant setup:

1. **Application ID** — the UUID shown in Enable Banking Control Panel, for
   example `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`.
2. **Private RSA key** — the complete contents of the downloaded or externally
   generated private PEM file.

Then add the Enable Banking integration in Home Assistant and enter:

| Home Assistant field | Value |
| --- | --- |
| **Application ID** | The Enable Banking application UUID. |
| **Private RSA key (PEM)** | The complete private PEM key, including its header and footer. |
| **Bank country** | The country where the bank account is held, such as `Netherlands`. |
| **Bank** | The bank returned by Enable Banking for the selected country. |
| **Customer type** | `Personal` for a private account or `Business` for a business account. |
| **Requested consent duration** | The number of days to request access, for example `90`. The bank may grant a shorter period. |

The environment of the Application ID controls which banks and accounts are
available: sandbox credentials cannot access production accounts, and
production credentials cannot access sandbox accounts.

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
