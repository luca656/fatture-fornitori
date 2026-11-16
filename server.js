// Server minimale (nessuna dipendenza) per tenere le ricette sul NAS.
// Avvio:  node server.js        (porta 8080, cartella dati ./data)
// Variabili: PORT, DATA_DIR, RICETTE_PASSWORD (obbligatoria), RICETTE_USER (default "luca"),
//            TLS_KEY + TLS_CERT (percorsi file, per attivare HTTPS)
const http = require("http"), https = require("https"), fs = require("fs"), path = require("path"), crypto = require("crypto");
const PORT = +process.env.PORT || 8080;
const USER = process.env.RICETTE_USER || "luca", PASS = process.env.RICETTE_PASSWORD || "";
if (!PASS && process.env.ALLOW_NO_PASSWORD !== "1") {
  console.error("Imposta una password:  RICETTE_PASSWORD='la-tua-password' node server.js\n(solo per uso in casa senza accesso da fuori: ALLOW_NO_PASSWORD=1)");
  process.exit(1);
}
const same = (a, b) => { const x = crypto.createHash("sha256").update(a).digest(), y = crypto.createHash("sha256").update(b).digest(); return crypto.timingSafeEqual(x, y); };
const fails = new Map(); // ip -> {n, until}: dopo 8 errori si blocca per 15 minuti
function authorized(req, res) {
  if (!PASS) return true;
  const ip = req.socket.remoteAddress, f = fails.get(ip) || { n: 0, until: 0 };
  if (f.until > Date.now()) { res.writeHead(429, { "content-type": "text/plain" }); res.end("Troppi tentativi, riprova più tardi"); return false; }
  const m = /^Basic (.+)$/.exec(req.headers.authorization || "");
  const [u = "", ...pw] = m ? Buffer.from(m[1], "base64").toString().split(":") : [];
  if (m && same(u, USER) & same(pw.join(":"), PASS)) { fails.delete(ip); return true; }
  if (m) { f.n++; if (f.n >= 8) { f.n = 0; f.until = Date.now() + 15 * 60e3; } fails.set(ip, f); }
  res.writeHead(401, { "www-authenticate": 'Basic realm="Ricettario", charset="UTF-8"', "content-type": "text/plain" }); res.end("Accesso richiesto");
  return false;
}
const DATA = path.resolve(process.env.DATA_DIR || path.join(__dirname, "data"));
const PHOTOS = path.join(DATA, "photos"), BACKUPS = path.join(DATA, "backups");
const FILE = path.join(DATA, "ricette.json");
for (const d of [DATA, PHOTOS, BACKUPS]) fs.mkdirSync(d, { recursive: true });

const read = () => { try { return JSON.parse(fs.readFileSync(FILE, "utf8")); } catch { return {}; } };
const write = o => { fs.writeFileSync(FILE + ".tmp", JSON.stringify(o)); fs.renameSync(FILE + ".tmp", FILE); };

// copia di sicurezza giornaliera (ricette.json), si tengono le ultime 30
function backup() {
  if (!fs.existsSync(FILE)) return;
  const f = path.join(BACKUPS, "ricette-" + new Date().toISOString().slice(0, 10) + ".json");
  if (!fs.existsSync(f)) fs.copyFileSync(FILE, f);
  fs.readdirSync(BACKUPS).sort().slice(0, -30).forEach(x => fs.unlinkSync(path.join(BACKUPS, x)));
}
backup(); setInterval(backup, 6 * 3600e3);

// le foto arrivano come dataURL: le salvo come file e nel JSON tengo solo il percorso
const storePhotos = photos => (photos || []).map(p => {
  const m = /^data:image\/(jpeg|png|webp);base64,(.+)$/.exec(p);
  if (!m) return p;
  const name = Date.now().toString(36) + Math.random().toString(36).slice(2, 8) + "." + (m[1] === "jpeg" ? "jpg" : m[1]);
  fs.writeFileSync(path.join(PHOTOS, name), Buffer.from(m[2], "base64"));
  return "/photos/" + name;
});

const send = (res, code, body, type = "application/json") => { res.writeHead(code, { "content-type": type }); res.end(body); };
const body = req => new Promise(r => { let b = ""; req.on("data", c => b += c); req.on("end", () => r(b)); });

const handler = async (req, res) => {
  if (!authorized(req, res)) return;
  const url = decodeURIComponent(req.url.split("?")[0]);
  try {
    if (url === "/api/recipes" && req.method === "GET") {
      const db = read(); return send(res, 200, JSON.stringify({ recipes: Object.values(db), modified: fs.existsSync(FILE) ? fs.statSync(FILE).mtimeMs : null }));
    }
    const m = /^\/api\/recipes\/([\w-]+)$/.exec(url);
    if (m && req.method === "PUT") {
      const r = JSON.parse(await body(req)); r.id = m[1]; r.photos = storePhotos(r.photos);
      const db = read(); db[r.id] = r; write(db); return send(res, 200, JSON.stringify(r));
    }
    if (m && req.method === "DELETE") { const db = read(); delete db[m[1]]; write(db); return send(res, 200, "{}"); }
    if (url.startsWith("/photos/")) {
      const f = path.join(PHOTOS, path.basename(url));
      if (!fs.existsSync(f)) return send(res, 404, "", "text/plain");
      res.writeHead(200, { "content-type": "image/" + (f.endsWith(".jpg") ? "jpeg" : path.extname(f).slice(1)), "cache-control": "max-age=31536000" });
      return fs.createReadStream(f).pipe(res);
    }
    if (url === "/" || url === "/index.html") return send(res, 200, fs.readFileSync(path.join(__dirname, "index.html")), "text/html; charset=utf-8");
    send(res, 404, "Non trovato", "text/plain");
  } catch (e) { send(res, 500, JSON.stringify({ error: e.message })); }
};
const tls = process.env.TLS_KEY && process.env.TLS_CERT;
(tls ? https.createServer({ key: fs.readFileSync(process.env.TLS_KEY), cert: fs.readFileSync(process.env.TLS_CERT) }, handler) : http.createServer(handler))
  .listen(PORT, "0.0.0.0", () => console.log("Ricettario su " + (tls ? "https" : "http") + "://0.0.0.0:" + PORT + "  (dati in " + DATA + ")" + (PASS ? "" : "  ATTENZIONE: senza password")));
