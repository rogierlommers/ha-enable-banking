# Receive an alert when bank account balance is low

This automation sends an alert when one of the bank accounts is having a low balance.

```
alias: Laag saldo melding
description: >-
  Stuurt een melding naar de iPhone zodra één van de saldo-sensoren
  onder de € 100 zakt.
triggers:
  - below: 100
    entity_id:
      - sensor.hr_prive_saldo
      - sensor.hr_vaste_lasten_saldo
    trigger: numeric_state
conditions: []
actions:
  - action: notify.send_message
    data:
      data:
        tag: laag_saldo_{{ trigger.entity_id }}
      message: >-
        {{ trigger.to_state.name }} is onder de € 100: nog € {{ '%.2f' |
        format(trigger.to_state.state | float) | replace('.', ',') }}.
      title: 💶 Laag saldo
    target:
      label_id: notification_device
max: 5
mode: parallel
```
