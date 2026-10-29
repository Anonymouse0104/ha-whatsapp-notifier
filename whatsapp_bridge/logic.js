import { jidNormalizedUser } from "@whiskeysockets/baileys";

export function toJid(chatId) {
  const id = String(chatId).trim().replace(/@c\.us$/, "@s.whatsapp.net"); // Green-API format
  if (id.includes("@")) return id;
  const digits = id.replace(/\D/g, "");
  if (!digits) throw new Error("invalid chat_id");
  return `${digits}@s.whatsapp.net`;
}

// privacy: only chats the user added in HA reach HA
export const shouldForward = (forward, ids) => forward.some((c) => ids.includes(toJid(c)));

// true when the replied-to message came from this linked account (what the bridge sent)
export function quotedFromMe({ ctx, sentIds, mine, isGroup, fromMe }) {
  if (!ctx?.stanzaId) return false;
  if (sentIds.has(ctx.stanzaId)) return true;
  if (ctx.participant) return mine.map(jidNormalizedUser).includes(jidNormalizedUser(ctx.participant));
  return !isGroup && !fromMe; // private chat without a quoted sender, e.g. after a restart: the other person answers us
}

// WhatsApp bans numbers that send floods, so cap runaway automations
export function makeLimiter(max, windowMs, now = Date.now) {
  const times = [];
  return () => {
    const t = now();
    while (times.length && times[0] <= t - windowMs) times.shift();
    if (times.length >= max) return false;
    times.push(t);
    return true;
  };
}
