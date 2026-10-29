import assert from "node:assert/strict";
import test from "node:test";
import { makeLimiter, quotedFromMe, shouldForward, toJid } from "./logic.js";

test("toJid accepts numbers, Green-API ids and groups", () => {
  assert.equal(toJid("+31 6 12345678"), "31612345678@s.whatsapp.net");
  assert.equal(toJid("31612345678@c.us"), "31612345678@s.whatsapp.net");
  assert.equal(toJid("120363@g.us"), "120363@g.us");
  assert.throws(() => toJid("abc"));
});

test("shouldForward only for listed chats", () => {
  assert.equal(shouldForward(["120363@g.us"], ["120363@g.us"]), true);
  assert.equal(shouldForward(["31612345678"], ["99@lid", "31612345678@s.whatsapp.net"]), true);
  assert.equal(shouldForward(["120363@g.us"], ["999@g.us"]), false);
  assert.equal(shouldForward([], ["120363@g.us"]), false);
});

test("quotedFromMe", () => {
  const base = { sentIds: new Set(["A"]), mine: ["31600000000:5@s.whatsapp.net"], isGroup: true, fromMe: false };
  assert.equal(quotedFromMe({ ...base, ctx: undefined }), false);
  assert.equal(quotedFromMe({ ...base, ctx: { stanzaId: "A" } }), true); // we sent it
  assert.equal(quotedFromMe({ ...base, ctx: { stanzaId: "B", participant: "31600000000@s.whatsapp.net" } }), true); // after restart
  assert.equal(quotedFromMe({ ...base, ctx: { stanzaId: "B", participant: "31611111111@s.whatsapp.net" } }), false);
  assert.equal(quotedFromMe({ ...base, ctx: { stanzaId: "B" } }), false); // group, unknown sender
  assert.equal(quotedFromMe({ ...base, isGroup: false, ctx: { stanzaId: "B" } }), true); // private, other person answers
  assert.equal(quotedFromMe({ ...base, isGroup: false, fromMe: true, ctx: { stanzaId: "B" } }), false);
});

test("limiter blocks the 3rd message in a window and recovers", () => {
  let now = 0;
  const allow = makeLimiter(2, 1000, () => now);
  assert.deepEqual([allow(), allow(), allow()], [true, true, false]);
  now = 1001;
  assert.equal(allow(), true);
});
