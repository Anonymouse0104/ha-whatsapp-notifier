# WhatsApp Notifier for Home Assistant

Send WhatsApp messages from Home Assistant to a person or a group, and react to replies, **without a third-party service** (no Green-API). Everything runs on your own Home Assistant.

It has two parts:

1. **Bridge add-on** (`whatsapp_bridge/`): a small Node service using [Baileys](https://github.com/WhiskeySockets/Baileys). It links to your WhatsApp account as a *linked device* (like WhatsApp Web).
2. **Integration** (`custom_components/whatsapp_notifier/`): notify entity, `send_message` service, status sensor, test button and an event for incoming messages.

> **Disclaimer:** Baileys uses the unofficial WhatsApp Web protocol. This is against WhatsApp's terms and the account can be banned. Use a dedicated number, send low volumes, never spam.

## Install

1. HA > Settings > Add-ons > Add-on store > ⋮ > Repositories: add this repo's URL. Install **WhatsApp Bridge**.
2. Set `pairing_phone` (international number, digits only, e.g. `31612345678`) and an `api_token`. Start it.
3. Open the add-on log or the status sensor attributes: you get an 8-character pairing code. On the phone: WhatsApp > Linked devices > Link a device > *Link with phone number instead* > enter the code. The session is stored in the add-on's `/data`, so restarts need no new pairing.
4. Install the integration via HACS (custom repository, type *Integration*) or copy `custom_components/whatsapp_notifier` into your config folder, restart HA.
5. Settings > Devices > Add integration > **WhatsApp Notifier**. Host `homeassistant.local` (or the add-on hostname), port `8099`, your token, and the **default chat ID**. Change the default later via the integration's *Configure* button.

No add-ons (HA Container/Core)? Run the bridge anywhere: `cd whatsapp_bridge && npm ci && API_TOKEN=secret PAIRING_PHONE=31612345678 node index.js`.

## Chat IDs

- Person: phone number with country code, e.g. `31612345678` (also accepts `31612345678@c.us`, so Green-API automations keep working).
- Group: `120363012345678901@g.us`. List your groups: `curl -H "Authorization: Bearer <token>" http://<host>:8099/groups`.

## Sending

Default chat (from the UI):

```yaml
action: notify.send_message
target:
  entity_id: notify.whatsapp_message
data:
  message: "The bins go out tomorrow"
```

Other chat (overrides the default), and returns the message id:

```yaml
action: whatsapp_notifier.send_message
data:
  chat_id: "120363012345678901@g.us"
  message: "Dinner is ready"
```

**Status**: `sensor.whatsapp_status` is `connected`, `connecting`, `pairing_required`, `logged_out`, `error` or `bridge_unreachable`. **Test**: press `button.whatsapp_send_test_message`.

## Replies

Every incoming text message fires the event `whatsapp_notifier_message_received` with `chat_id`, `sender`, `text`, `from_me`, `quoted_message_id`. There is no built-in rule engine: use normal automations, so any language works. Example: ask, then wait up to 10 minutes for "yes" as a reply *to that message*:

```yaml
actions:
  - action: whatsapp_notifier.send_message
    data: { message: "Bins out tomorrow. Already outside?" }
    response_variable: sent
  - wait_for_trigger:
      - trigger: event
        event_type: whatsapp_notifier_message_received
        event_data: {}
        # match in any language; drop the quoted_message_id test to accept any reply
        # in the chat
    timeout: "00:10:00"
    continue_on_timeout: true
  # Template conditions on the trigger:
  - condition: template
    value_template: >
      {{ wait.trigger is not none
         and wait.trigger.event.data.quoted_message_id == sent.message_id
         and wait.trigger.event.data.text | lower in ['yes', 'ja', 'oui'] }}
  - action: input_boolean.turn_on
    target: { entity_id: input_boolean.bins_outside }
```

## Same number for sending and replying

Messages you type on your own phone arrive on the linked device too (`from_me: true`); the bridge only drops its *own* sends, so your replies should reach HA. **This is untested** and in groups WhatsApp may report senders as `@lid` ids. If it misbehaves, use a separate number for the bridge (recommended).

## Status

Not tested against real WhatsApp yet: pairing, sending and receiving need a live check.
