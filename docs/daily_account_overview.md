
![image](docs/assets/Example-graph.png)

```yaml
alias: Dagelijks bankoverzicht
description: Dagelijks overzicht van recente transacties per bankrekening
triggers:
  - trigger: time
    at: '20:00:00'
conditions: []
actions:
  - action: notify.send_message
    target:
      entity_id: notify.INSERT_YOUR_NOTIFICATION_HERE
    data:
      title: Bankoverzicht — {{ now().strftime('%d-%m-%Y') }}
      message: |2-
                {% set accounts = [
                  {'name': 'Vaste lasten', 'entity': 'sensor.vaste_lasten_recente_transacties'},
                  {'name': 'Boodschappen', 'entity': 'sensor.boodschappen_recente_transacties'},
                  {'name': 'Prive', 'entity': 'sensor.prive_recente_transacties'},
                ] %}
                {% set report = namespace(lines=[]) %}
                {% for account in accounts %}
                  {% set transactions = (state_attr(account.entity, 'transactions') or [])[:5] %}
                  {% set report.lines = report.lines + [
                    '========================================',
                    (account.name | upper),
                    '========================================',
                    ''
                  ] %}
                  {% if states(account.entity) in ['unknown', 'unavailable'] %}
                    {% set report.lines = report.lines + ['Transactiegegevens niet beschikbaar.'] %}
                  {% elif transactions | count == 0 %}
                    {% set report.lines = report.lines + ['Geen recente transacties.'] %}
                  {% else %}
                    {% for transaction in transactions %}
                      {% set sign = '+' if transaction.direction == 'credit' else '-' if transaction.direction == 'debit' else '' %}
                      {% set report.lines = report.lines + [
                        (transaction.counterparty | default('Onbekende tegenpartij', true)),
                        'Bedrag: ' ~ sign ~ transaction.amount ~ ' ' ~ transaction.currency,
                        'Datum: ' ~ (transaction.date | string)
                      ] %}
                      {% if transaction.status | default('') %}
                        {% set report.lines = report.lines + [
                          'Status: ' ~ transaction.status
                        ] %}
                      {% endif %}
                      {% if transaction.remittance | default('') %}
                        {% set report.lines = report.lines + [
                          'Omschrijving: ' ~ transaction.remittance
                        ] %}
                      {% endif %}
                      {% set report.lines = report.lines + [''] %}
                    {% endfor %}
                  {% endif %}
                {% endfor %}
                {{ report.lines | join('\n') | trim }}
mode: single
```