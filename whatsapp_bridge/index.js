import fs from "node:fs";
import http from "node:http";
import { WebSocketServer } from "ws";
import pino from "pino";
import QRCode from "qrcode";
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  jidNormalizedUser,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";

const opts = (() => {
  try {
    return JSON.parse(fs.readFileSync("/data/options.json", "utf8"));
  } catch {
    return {};
  }
})();
const PORT = Number(opts.port ?? process.env.PORT ?? 8099);
const TOKEN = opts.api_token ?? process.env.API_TOKEN ?? "";
const PAIR_PHONE = String(opts.pairing_phone ?? process.env.PAIRING_PHONE ?? "").replace(/\D/g, "");
const AUTH_DIR =process.env.AUTH_DIR ?? (fs.existsSync("/data") ? "/data/auth" : "./auth");

if (!TOKEN) {
  console.error("api_token is required: anyone on the network could send messages without it");
  process.exit(1);
}

// chats whose incoming messages reach HA; set by the integration (POST /forward), kept across restarts
const FWD_FILE = (fs.existsSync("/data") ? "/data" : ".") + "/forward.json";
let FORWARD = [];
try {
  FORWARD = JSON.parse(fs.readFileSync(FWD_FILE, "utf8"));
} catch {}

const log = pino({ level: "warn" });
const say = (...a) => console.log(new Date().toISOString(), ...a);

// status: connecting | pairing_required | connected | logged_out | error
const state = { status: "connecting", pairing_code: null, error: null };
let lastQr = null; // served at /qr as a scannable alternative to the pairing code
let codeRequested = false; // WhatsApp resends qr every ~20s; a new code would invalidate the one being typed
let sock = null;
const sentIds = new Set(); // own sends echo back as fromMe; drop them

const wss = new WebSocketServer({ noServer: true });
const broadcast = (obj) => {
  const s = JSON.stringify(obj);
  for (const c of wss.clients) if (c.readyState === 1) c.send(s);
};
const setStatus = (status, extra = {}) => {
  Object.assign(state, { status, error: null }, extra);
  broadcast({ type: "status", ...state });
  say("status", status);
};

function toJid(chatId) {
  const id = String(chatId).trim().replace(/@c\.us$/, "@s.whatsapp.net"); // Green-API format
  if (id.includes("@")) return id;
  const digits = id.replace(/\D/g, "");
  if (!digits) throw new Error("invalid chat_id");
  return `${digits}@s.whatsapp.net`;
}

const fromMe = (jid) => {
  const mine = [sock?.user?.id, sock?.user?.lid].filter(Boolean).map(jidNormalizedUser);
  return !!jid && mine.includes(jidNormalizedUser(jid));
};

async function start() {
  const { state: auth, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();
  sock = makeWASocket({ version, auth, logger: log, markOnlineOnConnect: false, syncFullHistory: false });
  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
    if (qr) lastQr = qr;
    if (qr && !auth.creds.registered && !codeRequested) {
      if (PAIR_PHONE) {
        codeRequested = true;
        try {
          const code = await sock.requestPairingCode(PAIR_PHONE);
          setStatus("pairing_required", { pairing_code: code });
          say("PAIRING CODE:", code, "-> WhatsApp > Linked devices > Link with phone number");
        } catch (e) {
          setStatus("error", { error: String(e.message ?? e) });
        }
      } else {
        setStatus("pairing_required", { error: "open http://<host>:" + PORT + "/qr?token=<api_token> and scan with WhatsApp > Linked devices" });
      }
    }
    if (connection === "open") {
      lastQr = null;
      setStatus("connected", { pairing_code: null });
    } else if (connection === "close") {
      codeRequested = false;
      const code = lastDisconnect?.error?.output?.statusCode;
      if (code === DisconnectReason.loggedOut) {
        fs.rmSync(AUTH_DIR, { recursive: true, force: true });
        setStatus("logged_out");
      } else {
        setStatus("connecting");
      }
      setTimeout(start, code === DisconnectReason.loggedOut ? 2000 : 5000);
    }
  });

  sock.ev.on("messages.upsert", ({ messages, type }) => {
    if (type !== "notify") return;
    for (const m of messages) {
      if (!m.message || m.key.remoteJid === "status@broadcast") continue;
      if (m.key.fromMe && sentIds.has(m.key.id)) continue;
      const msg = m.message;
      const text = msg.conversation ?? msg.extendedTextMessage?.text ?? "";
      if (!text) continue;
      const ctx = msg.extendedTextMessage?.contextInfo;
      const ids = [m.key.remoteJid, m.key.remoteJidAlt].filter(Boolean);
      const ok = FORWARD.some((c) => ids.includes(toJid(c))); // privacy: only listed chats reach HA
      say(ok ? "forwarding message from" : "ignoring message from unlisted chat", ids.join(" / "), m.key.fromMe ? "(from me)" : "");
      if (!ok) continue;
      const isGroup = m.key.remoteJid.endsWith("@g.us");
      broadcast({
        type: "message",
        id: m.key.id,
        // groups may report @lid; participantAlt is the phone JID when WhatsApp provides it
        chat_id: m.key.remoteJidAlt ?? m.key.remoteJid,
        is_group: isGroup,
        sender: m.key.participantAlt ?? m.key.participant ?? m.key.remoteJidAlt ?? m.key.remoteJid,
        from_me: !!m.key.fromMe,
        text,
        quoted_message_id: ctx?.stanzaId ?? null,
        quoted_text: ctx?.quotedMessage?.conversation ?? ctx?.quotedMessage?.extendedTextMessage?.text ?? null,
        // true when the replied-to message was sent by this linked account (what the bridge sent)
        quoted_from_me: !!ctx?.stanzaId && (sentIds.has(ctx.stanzaId) || fromMe(ctx.participant)),
      });
    }
  });
}

const json = (res, code, body) => {
  res.writeHead(code, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
};
const authed = (req, url) => {
  if (!TOKEN) return true;
  const h = req.headers.authorization ?? "";
  return h === `Bearer ${TOKEN}` || url.searchParams.get("token") === TOKEN;
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  if (!authed(req, url)) return json(res, 401, { error: "unauthorized" });
  try {
    if (req.method === "GET" && url.pathname === "/status") return json(res, 200, state);
    if (url.pathname === "/forward") {
      if (req.method === "POST") {
        let raw = "";
        for await (const c of req) raw += c;
        const { chats } = JSON.parse(raw || "{}");
        if (!Array.isArray(chats)) return json(res, 400, { error: "chats must be a list" });
        FORWARD = chats.map((c) => String(c).trim()).filter(Boolean);
        fs.writeFileSync(FWD_FILE, JSON.stringify(FORWARD));
        say("forward list set:", FORWARD.join(", ") || "(empty)");
      }
      return json(res, 200, { chats: FORWARD });
    }
    if (req.method === "GET" && url.pathname === "/qr") {
      if (!lastQr) return json(res, 404, { error: "no QR available (already linked?)" });
      const img = await QRCode.toDataURL(lastQr, { width: 320 });
      res.writeHead(200, { "content-type": "text/html" });
      return res.end(`<meta http-equiv="refresh" content="15"><img src="${img}"><p>WhatsApp > Linked devices > Link a device. Page refreshes every 15s.</p>`);
    }
    if (req.method === "GET" && url.pathname === "/groups") {
      if (state.status !== "connected") return json(res, 503, { error: "not connected" });
      const g = await sock.groupFetchAllParticipating();
      return json(res, 200, Object.values(g).map((x) => ({ chat_id: x.id, name: x.subject })));
    }
    if (req.method === "POST" && url.pathname === "/send") {
      if (state.status !== "connected") return json(res, 503, { error: "not connected" });
      let raw = "";
      for await (const c of req) raw += c;
      const { chat_id, message } = JSON.parse(raw || "{}");
      if (!chat_id || !message) return json(res, 400, { error: "chat_id and message required" });
      const sent = await sock.sendMessage(toJid(chat_id), { text: String(message) });
      sentIds.add(sent.key.id);
      if (sentIds.size > 500) sentIds.delete(sentIds.values().next().value);
      return json(res, 200, { id: sent.key.id });
    }
    json(res, 404, { error: "not found" });
  } catch (e) {
    json(res, 500, { error: String(e.message ?? e) });
  }
});

server.on("upgrade", (req, socket, head) => {
  const url = new URL(req.url, "http://x");
  if (url.pathname !== "/ws" || !authed(req, url)) return socket.destroy();
  wss.handleUpgrade(req, socket, head, (ws) => {
    ws.send(JSON.stringify({ type: "status", ...state }));
  });
});

server.listen(PORT, () => say("bridge listening on", PORT));
start().catch((e) => setStatus("error", { error: String(e.message ?? e) }));
