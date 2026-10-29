# WhatsApp Notifier for Home Assistant

Send WhatsApp messages from Home Assistant to a person or a group, and react to replies, **without a third-party service** (no Green-API). Everything runs on your own Home Assistant.

It has two parts:

1. **Bridge add-on** (`whatsapp_bridge/`): a small Node service using [Baileys](https://github.com/WhiskeySockets/Baileys). It links to your WhatsApp account as a *linked device* (like WhatsApp Web).
2. **Integration** (`custom_components/whatsapp_notifier/`): a status sensor, a test button, a `send_message` service, and **one device per chat** with its own notify entity and "Last message" sensor.

Needs Home Assistant 2025.3 or newer.

> **Disclaimer:** Baileys uses the unofficial WhatsApp Web protocol. This is against WhatsApp's terms and the account can be banned. Use a dedicated number, send low volumes, never spam.

## Install

### 1. Bridge add-on

1. HA > Settings > Add-ons > Add-on store > ⋮ > Repositories: add `https://github.com/Anonymouse0104/ha-whatsapp-notifier`. Install **WhatsApp Bridge**.
2. On the *Configuration* tab set:
   - `api_token` (**required**): make up a long password. The bridge refuses to start without one. You need it again below.
   - `pairing_phone`: leave **empty** to link with a QR code (recommended, see below).
3. Save and start the add-on.

### 2. Link your WhatsApp (QR code)

1. Open `http://homeassistant.local:8099/qr?token=<api_token>` on a computer. You see a QR code that refreshes every 15 seconds.
2. On the phone of the number that will send the messages: WhatsApp > Settings > Linked devices > Link a device, and scan the QR code.
3. The add-on log now shows `status connected` (a `515` stream error right after linking is normal). The session is stored in the add-on's `/data`, so restarts need no new pairing.

Alternative: put your number in `pairing_phone` (international, digits only, e.g. `31612345678`), restart the add-on and enter the 8-character code from the log under *Link with phone number instead*. This has failed on some iPhones, so prefer the QR code. Never use both at once: clear `pairing_phone` when you use the QR page.

### 3. Integration

1. Install via HACS: ⋮ > Custom repositories > this repo's URL, category *Integration*. Restart HA. (Or copy `custom_components/whatsapp_notifier` into your config folder.)
2. Settings > Devices > Add integration > **WhatsApp Notifier**: host `homeassistant.local` (or the HA address), port `8099`, your `api_token` and optionally a **default chat ID**. Change the default later with the integration's *Configure* button.

No add-ons (HA Container/Core)? Run the bridge anywhere: `cd whatsapp_bridge && npm ci && API_TOKEN=secret node index.js`, then open `/qr` as above. Optional env vars: `PORT`, `PAIRING_PHONE`, `AUTH_DIR`.

## Finding chat IDs

**A person:** the phone number with country code, digits only, no `+`, no leading `0`.
`06 12345678` in the Netherlands becomes `31612345678`. (`31612345678@c.us` and `31612345678@s.whatsapp.net` also work, so Green-API automations keep working.)

**A group:** open this in a browser on your network:

```
http://homeassistant.local:8099/groups?token=<api_token>
```

You get a list like `[{"chat_id":"120363012345678901@g.us","name":"Family"}, ...]`. Copy the whole `chat_id`, including `@g.us`. The linked number must be a member of the group. If the group is missing, wait a minute and reload.

## Chats: one device per chat

On the integration page (Settings > Devices & services > WhatsApp Notifier) press **Add chat** and fill in:

- **Name**: shown as the device name, e.g. "Family group".
- **Chat ID**: a number or group ID, see above.
- **Only replies to messages sent by this bridge**: see [Replies](#replies).

Each chat becomes its own device with:

| Entity | What it does |
|---|---|
| Message (`notify`) | Sends to this chat. |
| Last message (`sensor`) | State is the text of the last message received in this chat (max 255 characters). Attributes: `text`, `sender`, `chat_id`, `from_me`, `is_group`, `id`, `quoted_message_id`, `quoted_text`, `quoted_from_me`. |

Use *⋮ > Reconfigure* on the chat to edit it, or delete it to remove the device. **Incoming messages are only passed on from chats you added** (privacy: everything else is dropped in the bridge).

The main **WhatsApp** device (the bridge) has:

| Entity | What it does |
|---|---|
| Status (`sensor`) | `connected`, `connecting`, `pairing_required`, `logged_out`, `error` or `bridge_unreachable`. |
| Send test message (`button`) | Sends a test message to the default chat. |
| Message (`notify`) | Sends to the **default chat** from the integration options. Shows *unknown* until the first message; that is normal. |

Entity IDs follow your HA language (check them under Developer tools > States).

## Sending

To a chat you added, with its notify entity:

```yaml
action: notify.send_message
target:
  entity_id: notify.family_group_message
data:
  title: "Bins"
  message: "The bins go out tomorrow"
```

To any chat (or the default chat when `chat_id` is left out); it also returns the id of the sent message:

```yaml
action: whatsapp_notifier.send_message
data:
  chat_id: "120363012345678901@g.us"
  message: "Dinner is ready"
response_variable: sent   # sent.message_id
```

WhatsApp formatting works in the text: `*bold*`, `_italic_`, `~strike~`.

## Testing

1. `Status` shows *Connected*.
2. Press **Send test message**. A message should arrive in the default chat (set one in *Configure*).
3. Call `whatsapp_notifier.send_message` in Developer tools > Actions with a `chat_id`.
4. If something fails, check the add-on log and the *Status* sensor (`pairing_required` or `logged_out` means: link again via `/qr`).

## Replies

When someone writes in a chat you added, its **Last message** sensor updates and the event `whatsapp_notifier_message_received` fires with the same fields as the sensor attributes.

**Reply to one specific message:** WhatsApp lets people swipe a message and answer on it. Then `quoted_message_id` is the id of the message that was answered, `quoted_text` is its text, and `quoted_from_me` is `true` when it was a message sent by the bridge. Tick *Only replies to messages sent by this bridge* on a chat and its sensor ignores everything else. To tie an answer to one exact message, compare `quoted_message_id` with the `message_id` returned by `whatsapp_notifier.send_message`.

Example: ask, then wait up to 10 minutes for "yes" as a reply *to that message*:

```yaml
actions:
  - action: whatsapp_notifier.send_message
    data: { message: "Bins out tomorrow. Already outside?" }
    response_variable: sent
  # keep waiting until someone answers our message; other chat messages are skipped.
  # On timeout the script stops.
  - repeat:
      sequence:
        - wait_for_trigger:
            - trigger: event
              event_type: whatsapp_notifier_message_received
          timeout: "00:10:00"
          continue_on_timeout: false
      # answer words in any language you like
      until: >
        {{ wait.trigger.event.data.quoted_message_id == sent.message_id
           and wait.trigger.event.data.text | lower | trim in ['yes', 'ja', 'oui'] }}
  - action: input_boolean.turn_on
    target: { entity_id: input_boolean.bins_outside }
```

### Notes for automations on the sensor

- If someone sends the same text twice in a row ("yes", "yes"), the sensor **state** does not change, only the `id` attribute does. A state trigger with `to:` then fires only once. Trigger on *any* change of the sensor (no `to:`), or use the event as above.
- The sensor is empty after a Home Assistant restart until the next message arrives.
- `sender` can be a WhatsApp internal id (`...@lid`) in groups instead of a phone number.

## Ready-made script

A script that sends a formatted message (emoji, bold title, text, italic footer) to a chat and falls back to a phone notification when WhatsApp fails. Replace `notify.mobile_app_YOUR_PHONE`. Leave `chat_id` empty to use the default chat.

```yaml
alias: WhatsApp notification
description: Send a formatted WhatsApp message, with a phone notification as fallback.
icon: mdi:whatsapp
mode: parallel
max: 20
fields:
  emoji:
    name: Emoji
    example: "🧺"
    selector: { text: }
  title:
    name: Title
    description: Shown in bold
    required: true
    example: Washing machine done!
    selector: { text: }
  text:
    name: Text
    required: true
    example: The laundry is ready.
    selector:
      text:
        multiline: true
  footer:
    name: Footer
    description: Optional italic line at the bottom
    selector: { text: }
  chat_id:
    name: Chat ID
    description: Leave empty for the default chat
    selector: { text: }
sequence:
  - variables:
      body: |-
        {% if emoji | default('') %}{{ emoji }} {% endif %}*{{ title }}*

        {{ text }}{% if footer | default('') %}

        _{{ footer }}_{% endif %}
  - action: whatsapp_notifier.send_message
    data:
      chat_id: "{{ chat_id | default('') }}"
      message: "{{ body }}"
    response_variable: sent
    continue_on_error: true
  - alias: Fall back to the phone when WhatsApp fails
    if:
      - condition: template
        value_template: "{{ sent is not defined or sent.message_id is not defined }}"
    then:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "{{ title }}"
          message: "{{ text }} (WhatsApp failed)"
```

Use it from an automation with `action: script.whatsapp_notification` and `data: { title: ..., text: ... }`.

## Same number for sending and replying

Messages you type on your own phone arrive on the linked device too (`from_me: true`); the bridge only drops its *own* sends, so your replies should reach HA. Replying from your own phone to a bridge message in a group should work too (`quoted_from_me` is then `true`), but this is not confirmed yet. In groups WhatsApp may report senders as `@lid` ids. If it misbehaves, use a separate number for the bridge (recommended).

## Security

- Only one bridge per Home Assistant is supported; `whatsapp_notifier.send_message` uses the first configured one.
- Anyone with the `api_token` can send messages as your account. Keep port 8099 inside your network and never forward it to the internet.

## Status

Linking, sending to a group and the *Last message* sensor are confirmed to work. Per-chat devices and *Only replies* need real-world feedback: please open an issue.
