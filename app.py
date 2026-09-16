# -*- coding: utf-8 -*-
# PLP FREE KEY — Đổi key mỗi ngày, hết hạn 20 phút, chống gian lận qua link
from __future__ import annotations
import os, json, time, random, string, hashlib, sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, render_template_string, make_response

app = Flask(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DB_PATH = os.environ.get("DB_PATH", "freekey.db")
SESSION_MINUTES = 20          # key sống 20 phút
SHORTLINK_SECRET = os.environ.get("SHORTLINK_SECRET", "plp-short-2026")

# ============================================================
# DB
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT NOT NULL,           -- YYYY-MM-DD
        visitor TEXT NOT NULL,       -- hash(ip + ua)
        key TEXT NOT NULL,
        created_at INTEGER NOT NULL, -- ms
        expires_at INTEGER NOT NULL, -- ms
        unlock_token TEXT,           -- token đã vượt link
        unlocked_at INTEGER,
        UNIQUE(day, visitor)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS unlock_tokens (
        token TEXT PRIMARY KEY,
        created_at INTEGER NOT NULL,
        used INTEGER DEFAULT 0,
        used_at INTEGER
    )""")
    conn.commit(); conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================
# HELPERS
# ============================================================
def today_vn() -> str:
    """Ngày hôm nay theo giờ VN, tự đổi lúc 00h."""
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")

def visitor_id() -> str:
    """Hash IP + User-Agent → định danh 'người truy cập' (không lưu IP thô)."""
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "0.0.0.0"
    ua = request.headers.get("User-Agent", "")
    raw = f"{ip}|{ua}|{SHORTLINK_SECRET}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]

def gen_key() -> str:
    """7 ký tự: chữ HOA + số, bỏ ký tự dễ nhầm (0,O,1,I,L)."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(7))

def ms_now() -> int:
    return int(time.time() * 1000)

def get_today_key(visitor: str):
    """Lấy key của visitor hôm nay (tạo mới nếu chưa có)."""
    day = today_vn()
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT * FROM keys WHERE day=? AND visitor=?", (day, visitor)).fetchone()

    if row:
        row = dict(row)
        # nếu hết hạn session → trả về nhưng đánh dấu expired
        if row["expires_at"] < ms_now():
            conn.close()
            return {"status": "expired", "key": None}
        conn.close()
        return {"status": "active", **row}

    # tạo mới — nhưng chỉ khi visitor đã vượt link
    row_unlock = c.execute(
        "SELECT * FROM unlock_tokens WHERE used=0 ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    # Không tự dùng token ở đây — chỉ tạo key khi client gọi /api/unlock
    conn.close()
    return {"status": "new", "key": None}

def create_key(visitor: str) -> str:
    """Tạo key mới cho visitor hôm nay."""
    day = today_vn()
    now = ms_now()
    k = gen_key()
    conn = get_db(); c = conn.cursor()
    try:
        c.execute("""INSERT OR REPLACE INTO keys 
                     (day, visitor, key, created_at, expires_at, unlocked_at)
                     VALUES (?,?,?,?,?,?)""",
                  (day, visitor, k, now, now + SESSION_MINUTES * 60 * 1000, now))
        conn.commit()
    finally:
        conn.close()
    return k

def is_unlocked(visitor: str) -> bool:
    """Kiểm tra visitor đã vượt link chưa (có token đã dùng hôm nay)."""
    day = today_vn()
    conn = get_db(); c = conn.cursor()
    # đơn giản: dùng flag trong bảng keys nếu có, hoặc dùng cookie
    row = c.execute("SELECT unlocked_at FROM keys WHERE day=? AND visitor=?", (day, visitor)).fetchone()
    conn.close()
    return bool(row and row["unlocked_at"])

def mark_unlocked(visitor: str):
    day = today_vn()
    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO keys (day, visitor, key, created_at, expires_at, unlocked_at)
                 VALUES (?,?,?,?,?,?)
                 ON CONFLICT(day, visitor) DO UPDATE SET unlocked_at=excluded.unlocked_at""",
              (day, visitor, "", ms_now(), 0, ms_now()))
    conn.commit(); conn.close()

# ============================================================
# SHORT LINK — trang vượt link
# ============================================================
def make_unlock_token() -> str:
    token = hashlib.sha256(f"{time.time()}{random.random()}".encode()).hexdigest()[:24]
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO unlock_tokens (token, created_at, used) VALUES (?,?,0)",
              (token, ms_now()))
    conn.commit(); conn.close()
    return token

@app.route("/go/<token>")
def shortlink_redirect(token):
    """Link rút gọn — redirect về trang chủ kèm token đánh dấu đã vượt link."""
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT * FROM unlock_tokens WHERE token=?", (token,)).fetchone()
    if not row:
        conn.close()
        return "Link không hợp lệ", 404
    row = dict(row)
    if row["used"]:
        conn.close()
        return "Link đã được sử dụng", 403

    # đánh dấu đã dùng + set cookie
    c.execute("UPDATE unlock_tokens SET used=1, used_at=? WHERE token=?", (ms_now(), token))
    conn.commit(); conn.close()

    resp = make_response(render_template_string(REDIRECT_HTML))
    resp.set_cookie("plp_unlock", token, max_age=3600, httponly=True, samesite="Lax")
    return resp

REDIRECT_HTML = """
<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Đang xác minh...</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{background:#0b1220;color:#eaf2ff;font-family:sans-serif;display:flex;
align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}
.box{padding:30px}
.spin{width:40px;height:40px;border:4px solid #1f355e;border-top-color:#00d4ff;
border-radius:50%;animation:sp 1s linear infinite;margin:0 auto 16px}
@keyframes sp{to{transform:rotate(360deg)}}
a{color:#00d4ff}
</style></head><body>
<div class="box">
  <div class="spin"></div>
  <h2>✅ Xác minh thành công</h2>
  <p style="color:#7a8ca3">Đang chuyển về trang lấy key...</p>
  <p><a href="/">Bấm vào đây nếu không tự chuyển</a></p>
</div>
<script>setTimeout(()=>location.href="/", 800);</script>
</body></html>
"""

# ============================================================
# MAIN PAGE
# ============================================================
PAGE_HTML = """
<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PLP FREE KEY</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,sans-serif}
body{background:radial-gradient(ellipse at top,#0a1a3a,#050a14);color:#eaf2ff;
min-height:100vh;padding:20px;display:flex;align-items:center;justify-content:center}
.card{max-width:480px;width:100%;background:#111c33;border:1px solid #1f355e;
border-radius:18px;padding:28px;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,0.5)}
h1{color:#00d4ff;font-size:26px;letter-spacing:2px;margin-bottom:6px}
.sub{color:#7a8ca3;font-size:12px;margin-bottom:22px;text-transform:uppercase;letter-spacing:2px}
.keybox{background:#0b1220;border:2px dashed #1f355e;border-radius:14px;
padding:24px 16px;margin:16px 0;transition:all .3s}
.keybox.active{border-color:#00e676;box-shadow:0 0 30px rgba(0,230,118,.25)}
.keybox.expired{border-color:#ff4d6d;opacity:.6}
.key{font-family:'Consolas',monospace;font-size:38px;font-weight:900;
letter-spacing:6px;color:#00d4ff;user-select:all;word-break:break-all}
.keybox.expired .key{color:#ff4d6d;text-decoration:line-through}
.keybox.empty .key{color:#7a8ca3;font-size:20px;letter-spacing:2px}
.timer{font-size:15px;color:#7a8ca3;margin-top:12px}
.timer b{color:#ffd740;font-family:monospace;font-size:18px}
.day{font-size:12px;color:#7a8ca3;margin-top:6px}
button{padding:14px 26px;border:none;border-radius:10px;font-weight:700;
font-size:14px;cursor:pointer;background:linear-gradient(135deg,#00d4ff,#2563eb);
color:#050a14;letter-spacing:1px;margin-top:8px;width:100%}
button:hover{opacity:.9}
button:disabled{opacity:.5;cursor:not-allowed}
.btn-get{background:linear-gradient(135deg,#00e676,#00b050);color:#050a14}
.footer{margin-top:18px;font-size:11px;color:#7a8ca3}
.footer b{color:#00d4ff}
</style></head><body>

<div class="card">
  <h1>🔑 PLP FREE KEY</h1>
  <div class="sub">Key miễn phí • 20 phút / lần</div>

  <div id="keybox" class="keybox empty">
    <div id="keytext" class="key">Đang tải...</div>
    <div id="timer" class="timer"></div>
    <div id="day" class="day"></div>
  </div>

  <div id="actions"></div>

  <div class="footer">
    ⚡ Key đổi mới mỗi <b>00:00</b> hàng ngày<br>
    ⏱️ Mỗi key sống trong <b>20 phút</b>
  </div>
</div>

<script>
const box = document.getElementById('keybox');
const keyEl = document.getElementById('keytext');
const timerEl = document.getElementById('timer');
const dayEl = document.getElementById('day');
const actionsEl = document.getElementById('actions');

let currentEnd = 0;
let tickTimer = null;

function fmt(n){ return String(n).padStart(2,'0'); }
function renderTime(msLeft){
  if (msLeft <= 0) return '00:00';
  const s = Math.floor(msLeft / 1000);
  return fmt(Math.floor(s/60)) + ':' + fmt(s % 60);
}

async function load(){
  const r = await fetch('/api/key', {cache:'no-store'});
  const j = await r.json();

  dayEl.textContent = '📅 Ngày: ' + j.day;

  if (j.status === 'locked'){
    box.className = 'keybox empty';
    keyEl.textContent = '🔒 CHƯA XÁC MINH';
    timerEl.innerHTML = 'Bạn cần vượt link để nhận key';
    actionsEl.innerHTML = '<button class="btn-get" onclick="goUnlock()">🚀 VƯỢT LINK NHẬN KEY</button>';
    return;
  }

  if (j.status === 'expired'){
    box.className = 'keybox expired';
    keyEl.textContent = 'KHÔNG CÓ KEY';
    timerEl.innerHTML = 'Key đã hết hạn sau 20 phút';
    actionsEl.innerHTML = '<button onclick="location.reload()">🔄 Tải lại trang</button>';
    return;
  }

  if (j.status === 'active'){
    box.className = 'keybox active';
    keyEl.textContent = j.key;
    currentEnd = j.expires_at;
    timerEl.innerHTML = '⏱️ Còn lại: <b id="cd">--:--</b>';
    actionsEl.innerHTML = '<button onclick="copyKey()">📋 COPY KEY</button>' +
      '<button style="margin-top:8px;background:#1f355e;color:#eaf2ff" onclick="location.reload()">🔄 Tải lại</button>';
    startCountdown();
    return;
  }

  // new — chưa có key, cho phép lấy
  box.className = 'keybox empty';
  keyEl.textContent = 'CHƯA CÓ KEY';
  timerEl.innerHTML = 'Bấm nút dưới để nhận key hôm nay';
  actionsEl.innerHTML = '<button class="btn-get" onclick="getKey()">🎁 NHẬN KEY NGAY</button>';
}

function startCountdown(){
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = setInterval(()=>{
    const left = currentEnd - Date.now();
    const el = document.getElementById('cd');
    if (el) el.textContent = renderTime(left);
    if (left <= 0){
      clearInterval(tickTimer);
      load();
    }
  }, 1000);
}

async function getKey(){
  actionsEl.innerHTML = '<button disabled>Đang lấy key...</button>';
  const r = await fetch('/api/key/new', {method:'POST'});
  const j = await r.json();
  if (j.ok){ load(); }
  else { alert('Lỗi: ' + (j.error || 'không xác định')); load(); }
}

function copyKey(){
  const k = keyEl.textContent.trim();
  if (k && k.length === 7) navigator.clipboard.writeText(k)
    .then(()=>alert('Đã copy: ' + k))
    .catch(()=>alert('Không copy được — tự bôi đen và copy nhé'));
}

async function goUnlock(){
  const r = await fetch('/api/unlock-link');
  const j = await r.json();
  if (j.url) location.href = j.url;
  else alert('Không tạo được link');
}

load();
setInterval(()=>{ if (!tickTimer) load(); }, 30000);
</script>
</body></html>
"""

@app.route("/")
def index():
    return render_template_string(PAGE_HTML)

# ============================================================
# API
# ============================================================
@app.route("/api/key", methods=["GET"])
def api_key():
    visitor = visitor_id()
    day = today_vn()

    if not is_unlocked(visitor):
        return jsonify({"status": "locked", "day": day})

    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT * FROM keys WHERE day=? AND visitor=?", (day, visitor)).fetchone()
    conn.close()

    if not row or not row["key"]:
        return jsonify({"status": "new", "day": day})

    row = dict(row)
    if row["expires_at"] < ms_now():
        return jsonify({"status": "expired", "day": day,
                        "expires_at": row["expires_at"]})

    return jsonify({
        "status": "active", "day": day,
        "key": row["key"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
    })

@app.route("/api/key/new", methods=["POST"])
def api_new_key():
    visitor = visitor_id()
    if not is_unlocked(visitor):
        return jsonify({"ok": False, "error": "Chưa vượt link xác minh"}), 403

    day = today_vn()
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT * FROM keys WHERE day=? AND visitor=?", (day, visitor)).fetchone()

    # nếu đã có key còn hạn → không tạo mới
    if row and row["key"] and row["expires_at"] > ms_now():
        conn.close()
        return jsonify({"ok": False, "error": "Bạn đã có key còn hiệu lực"}), 429

    conn.close()
    k = create_key(visitor)
    return jsonify({"ok": True, "key": k})

@app.route("/api/unlock-link", methods=["GET"])
def api_unlock_link():
    """Tạo link rút gọn — trỏ tới /go/<token>."""
    token = make_unlock_token()
    base = request.url_root.rstrip("/")
    return jsonify({"url": f"{base}/go/{token}", "token": token})

@app.route("/health")
def health():
    return jsonify({"ok": True, "day": today_vn(), "ts": ms_now()})

# ============================================================
# INIT
# ============================================================
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)