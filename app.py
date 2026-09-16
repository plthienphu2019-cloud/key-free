# -*- coding: utf-8 -*-
# PLP FREE KEY SERVER — Link4m Gate + Neon UI + Device-Bound 20min Key
from __future__ import annotations
import os, time, random, hashlib, sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DB_PATH = os.environ.get("DB_PATH", "freekey.db")
SESSION_MINUTES = 20
SERVER_SECRET = os.environ.get("SERVER_SECRET", "plp-free-2026")
LINK4M_TOKEN = os.environ.get("LINK4M_TOKEN", "68f4489e3ae4c02c3e2ea54c")
LINK4M_API = "https://link4m.co/api-shorten/v2"

# ============================================================
# DB
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT NOT NULL,
        key TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        day TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS unlock (
        device_id TEXT PRIMARY KEY,
        unlocked_at INTEGER NOT NULL,
        day TEXT NOT NULL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_device ON keys(device_id)")
    conn.commit(); conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn

def ms_now(): return int(time.time() * 1000)
def today_vn(): return datetime.now(VN_TZ).strftime("%Y-%m-%d")
def gen_key():
    A = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(A) for _ in range(7))
def device_hash(dev: str) -> str:
    return hashlib.sha256(f"{dev}|{SERVER_SECRET}".encode()).hexdigest()[:32]

# ============================================================
# LOGIC
# ============================================================
def is_unlocked(device_id: str) -> bool:
    if not device_id: return False
    h = device_hash(device_id)
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT unlocked_at FROM unlock WHERE device_id=?", (h,)).fetchone()
    conn.close()
    return bool(row)

def mark_unlocked(device_id: str):
    h = device_hash(device_id)
    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO unlock (device_id, unlocked_at, day)
                 VALUES (?,?,?)""", (h, ms_now(), today_vn()))
    conn.commit(); conn.close()

def get_key_for_device(device_id: str):
    if not device_id: return None
    h = device_hash(device_id)
    conn = get_db(); c = conn.cursor()
    row = c.execute("""SELECT * FROM keys WHERE device_id=? AND expires_at>?
                       ORDER BY created_at DESC LIMIT 1""",
                    (h, ms_now())).fetchone()
    conn.close()
    return dict(row) if row else None

def create_key_for_device(device_id: str) -> dict:
    h = device_hash(device_id)
    k = gen_key(); now = ms_now(); exp = now + SESSION_MINUTES * 60 * 1000
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM keys WHERE device_id=?", (h,))
    c.execute("""INSERT INTO keys (device_id, key, created_at, expires_at, day)
                 VALUES (?,?,?,?,?)""", (h, k, now, exp, today_vn()))
    conn.commit(); conn.close()
    return {"key": k, "created_at": now, "expires_at": exp}

# ============================================================
# LINK4M — tạo link vượt dẫn về /verify
# ============================================================
def link4m_shorten(url: str) -> str:
    try:
        r = requests.get(LINK4M_API, params={"api": LINK4M_TOKEN, "url": url}, timeout=15)
        d = r.json()
        for k in ("shortenedUrl","shortened_url","short","url","result"):
            v = d.get(k)
            if isinstance(v, str) and v.startswith("http"): return v
        for v in d.values():
            if isinstance(v, str) and v.startswith("http"): return v
    except Exception as e:
        print("link4m error:", e)
    return url   # fallback

# ============================================================
# UI HTML
# ============================================================
NEON = """
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',system-ui,sans-serif}
@keyframes glow{0%,100%{box-shadow:0 0 20px #00ffff,0 0 40px #00ffff55}
50%{box-shadow:0 0 30px #ff00ff,0 0 60px #ff00ff55}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@keyframes scan{0%{transform:translateX(-100%)}100%{transform:translateX(200%)}}
@keyframes rgb{0%{filter:hue-rotate(0deg)}100%{filter:hue-rotate(360deg)}}
body{background:radial-gradient(ellipse at top,#0a0e27,#05060f 60%,#000);
color:#eaf2ff;min-height:100vh;padding:20px;display:flex;
align-items:center;justify-content:center;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;
background-image:linear-gradient(rgba(0,255,255,.04) 1px,transparent 1px),
linear-gradient(90deg,rgba(255,0,255,.04) 1px,transparent 1px);
background-size:40px 40px;pointer-events:none;z-index:0}
.card{position:relative;z-index:1;max-width:520px;width:100%;
background:linear-gradient(145deg,rgba(10,15,35,.95),rgba(5,8,20,.98));
border:2px solid #00ffff;border-radius:20px;padding:32px 24px;text-align:center;
animation:glow 3s ease-in-out infinite,float 4s ease-in-out infinite;overflow:hidden}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;
background:linear-gradient(90deg,transparent,#00ffff,#ff00ff,#00ffff,transparent);
animation:scan 3s linear infinite}
h1{font-size:32px;font-weight:900;letter-spacing:4px;
background:linear-gradient(135deg,#00ffff,#ff00ff,#00ffff);background-size:200% 200%;
-webkit-background-clip:text;-webkit-text-fill-color:transparent;
animation:rgb 4s linear infinite;margin-bottom:6px}
.sub{color:#00ffff;font-size:11px;letter-spacing:4px;text-transform:uppercase;
opacity:.7;margin-bottom:24px;text-shadow:0 0 10px #00ffff}
.keybox{position:relative;background:rgba(0,0,0,.6);border:2px dashed #00ffff88;
border-radius:14px;padding:28px 16px;margin:16px 0;transition:all .3s}
.keybox.active{border:2px solid #00ff88;box-shadow:0 0 30px #00ff8855,inset 0 0 20px #00ff8822}
.keybox.empty{border:2px dashed #ff0055aa;box-shadow:0 0 20px #ff005533}
.key{font-family:'Consolas',monospace;font-size:44px;font-weight:900;
letter-spacing:8px;color:#00ffff;user-select:all;word-break:break-all;margin:6px 0;
text-shadow:0 0 10px #00ffff,0 0 20px #00ffff88}
.keybox.empty .key{color:#ff0055;font-size:22px;letter-spacing:3px;text-shadow:0 0 10px #ff0055}
.timer{font-size:14px;color:#7a8ca3;margin-top:14px}
.timer b{color:#ffd740;font-family:monospace;font-size:20px;text-shadow:0 0 8px #ffd740}
button{padding:16px 28px;border:none;border-radius:12px;font-weight:800;font-size:14px;
cursor:pointer;letter-spacing:2px;text-transform:uppercase;
background:linear-gradient(135deg,#00ffff,#0066ff);color:#000;width:100%;margin-top:8px;
box-shadow:0 0 20px #00ffff55,inset 0 0 10px #ffffff33;transition:all .25s;font-family:inherit}
button:hover{transform:translateY(-2px);box-shadow:0 0 30px #00ffff99,inset 0 0 15px #ffffff66}
button:disabled{opacity:.5;cursor:not-allowed}
.btn-copy{background:linear-gradient(135deg,#00ff88,#00aa55);box-shadow:0 0 20px #00ff8855}
.btn-reload{background:linear-gradient(135deg,#ff00ff,#8800ff);color:#fff}
.footer{margin-top:22px;font-size:11px;color:#7a8ca3;letter-spacing:1px;line-height:1.8}
.footer b{color:#00ffff;text-shadow:0 0 6px #00ffff}
.tag{display:inline-block;padding:4px 12px;border-radius:20px;
background:rgba(0,255,255,.1);color:#00ffff;font-size:10px;letter-spacing:2px;
border:1px solid #00ffff44;margin-bottom:12px;text-shadow:0 0 6px #00ffff}
.tag.warn{background:rgba(255,0,85,.1);color:#ff0055;border-color:#ff005544}
.tag.ok{background:rgba(0,255,136,.1);color:#00ff88;border-color:#00ff8844}
</style>
"""

VERIFY_PAGE = """<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ Xác minh ⚡</title>""" + NEON + """</head><body>
<div class="card">
  <h1>⚡ XÁC MINH ⚡</h1>
  <div class="sub">Đang kiểm tra lượt vượt link...</div>
  <div class="keybox empty">
    <div class="tag" id="tag">⏳ ĐANG XỬ LÝ</div>
    <div class="key" id="msg">Vui lòng đợi...</div>
  </div>
</div>
<script>
async function verify(){
  const p = new URLSearchParams(location.search);
  const device = p.get('device') || '';
  if (!device){ document.getElementById('msg').textContent = 'LỖI: THIẾU DEVICE'; return; }
  try {
    const r = await fetch('/api/verify-unlock?device=' + encodeURIComponent(device));
    const j = await r.json();
    if (j.ok){
      document.getElementById('tag').textContent = '✅ THÀNH CÔNG';
      document.getElementById('tag').className = 'tag ok';
      document.getElementById('msg').textContent = 'ĐANG CHUYỂN TRANG...';
      setTimeout(()=>location.href = '/?device=' + encodeURIComponent(device), 1200);
    } else {
      document.getElementById('tag').textContent = '❌ LỖI';
      document.getElementById('tag').className = 'tag warn';
      document.getElementById('msg').textContent = j.error || 'KHÔNG HỢP LỆ';
    }
  } catch(e){
    document.getElementById('msg').textContent = 'LỖI KẾT NỐI';
  }
}
verify();
</script></body></html>"""

KEY_PAGE = """<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ PLP KEY ⚡</title>""" + NEON + """</head><body>
<div class="card">
  <h1>⚡ PLP KEY ⚡</h1>
  <div class="sub">Free Key System</div>
  <div class="keybox empty" id="keybox">
    <div class="tag warn" id="tag">ĐANG TẢI</div>
    <div class="key" id="keytext">Đang tải...</div>
    <div class="timer" id="timer"></div>
  </div>
  <div id="actions"></div>
  <div class="footer">
    ⚡ Key sống <b>20 phút</b><br>
    🔒 Gắn cứng với thiết bị — không share được
  </div>
</div>
<script>
const box = document.getElementById('keybox');
const keyEl = document.getElementById('keytext');
const tagEl = document.getElementById('tag');
const timerEl = document.getElementById('timer');
const actionsEl = document.getElementById('actions');
let currentEnd = 0, tick = null;
const device = new URL(location.href).searchParams.get('device') || '';

function fmt(n){ return String(n).padStart(2,'0'); }
function rtime(ms){ if(ms<=0) return '00:00'; const s=Math.floor(ms/1000);
  return fmt(Math.floor(s/60))+':'+fmt(s%60); }

async function load(){
  if (!device){
    box.className='keybox empty';
    tagEl.textContent='THIẾU DEVICE'; tagEl.className='tag warn';
    keyEl.textContent='MỞ LẠI TỪ TOOL';
    actionsEl.innerHTML=''; return;
  }
  const r = await fetch('/api/key?device=' + encodeURIComponent(device), {cache:'no-store'});
  const j = await r.json();

  if (j.status === 'locked'){
    box.className='keybox empty';
    tagEl.textContent='CHƯA VƯỢT LINK'; tagEl.className='tag warn';
    keyEl.textContent='BẠN CẦN VƯỢT LINK ĐỂ LẤY KEY';
    actionsEl.innerHTML='<button onclick="location.href=\\'/\\'">QUAY LẠI</button>';
    return;
  }
  if (j.status === 'active'){
    box.className='keybox active';
    tagEl.textContent='● KEY HOẠT ĐỘNG'; tagEl.className='tag ok';
    keyEl.textContent=j.key;
    currentEnd = j.expires_at;
    timerEl.innerHTML = '⏱️ Còn lại: <b id="cd">--:--</b>';
    actionsEl.innerHTML =
      '<button class="btn-copy" onclick="copyKey()">📋 COPY KEY</button>' +
      '<button class="btn-reload" style="margin-top:10px" onclick="location.reload()">🔄 LÀM MỚI</button>';
    if (tick) clearInterval(tick);
    tick = setInterval(()=>{
      const left = currentEnd - Date.now();
      const el = document.getElementById('cd');
      if (el) el.textContent = rtime(left);
      if (left<=0){ clearInterval(tick); load(); }
    }, 1000);
    return;
  }
  if (j.status === 'new'){
    box.className='keybox empty';
    tagEl.textContent='● CHƯA CÓ KEY'; tagEl.className='tag warn';
    keyEl.textContent='NHẤN NÚT ĐỂ NHẬN KEY';
    actionsEl.innerHTML='<button onclick="getKey()">🎁 NHẬN KEY NGAY</button>';
    return;
  }
  if (j.status === 'expired'){
    box.className='keybox empty';
    tagEl.textContent='● KEY HẾT HẠN'; tagEl.className='tag warn';
    keyEl.textContent='NHẤN LÀM MỚI ĐỂ LẤY KEY MỚI';
    actionsEl.innerHTML='<button class="btn-reload" onclick="location.reload()">🔄 LÀM MỚI</button>';
    return;
  }
  box.className='keybox empty';
  tagEl.textContent='LỖI'; tagEl.className='tag warn';
  keyEl.textContent='KHÔNG CÓ KEY';
  actionsEl.innerHTML='<button class="btn-reload" onclick="location.reload()">🔄 THỬ LẠI</button>';
}
async function getKey(){
  actionsEl.innerHTML='<button disabled>Đang tạo...</button>';
  const r = await fetch('/api/key/new?device=' + encodeURIComponent(device), {method:'POST'});
  const j = await r.json();
  if (j.ok) load();
  else { alert(j.error || 'Lỗi'); load(); }
}
function copyKey(){
  const k = keyEl.textContent.trim();
  if (k && k.length===7) navigator.clipboard.writeText(k).then(()=>alert('Đã copy: ' + k));
}
load();
setInterval(()=>{ if (!tick) load(); }, 30000);
</script></body></html>"""

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    return render_template_string(KEY_PAGE)

@app.route("/verify")
def verify_page():
    return render_template_string(VERIFY_PAGE)

@app.route("/api/create-link")
def api_create_link():
    """Tool gọi endpoint này để nhận link vượt qua Link4m."""
    device = request.args.get("device", "").strip()
    if not device:
        return jsonify({"ok": False, "error": "missing device"}), 400
    # link đích sau khi vượt link4m → sẽ vào /verify?device=xxx
    base = request.url_root.rstrip("/")
    target = f"{base}/verify?device={device}"
    short = link4m_shorten(target)
    return jsonify({"ok": True, "url": short, "target": target})

@app.route("/api/verify-unlock")
def api_verify_unlock():
    """Sau khi user vượt link4m → Link4m redirect về đây → đánh dấu unlocked."""
    device = request.args.get("device", "").strip()
    if not device:
        return jsonify({"ok": False, "error": "missing device"}), 400
    mark_unlocked(device)
    return jsonify({"ok": True})

@app.route("/api/key")
def api_key():
    device = request.args.get("device", "").strip()
    if not device:
        return jsonify({"status": "locked"})

    if not is_unlocked(device):
        return jsonify({"status": "locked"})

    row = get_key_for_device(device)
    if row:
        return jsonify({"status": "active", "key": row["key"],
                        "created_at": row["created_at"], "expires_at": row["expires_at"]})
    return jsonify({"status": "new"})

@app.route("/api/key/new", methods=["POST"])
def api_new_key():
    device = request.args.get("device", "").strip()
    if not device:
        return jsonify({"ok": False, "error": "missing device"}), 400
    if not is_unlocked(device):
        return jsonify({"ok": False, "error": "Chưa vượt link"}), 403
    if get_key_for_device(device):
        return jsonify({"ok": False, "error": "Bạn đã có key còn hiệu lực"}), 429
    res = create_key_for_device(device)
    return jsonify({"ok": True, **res})

@app.route("/api/verify", methods=["POST"])
def api_verify():
    """Tool verify key đã nhận từ web."""
    data = request.get_json(silent=True) or {}
    dev = (data.get("device_id") or "").strip()
    key = (data.get("key") or "").strip().upper()
    if not dev or not key:
        return jsonify({"ok": False, "error": "Thiếu dữ liệu"}), 400
    h = device_hash(dev)
    conn = get_db(); c = conn.cursor()
    row = c.execute("""SELECT * FROM keys WHERE device_id=? AND key=? AND expires_at>?""",
                    (h, key, ms_now())).fetchone()
    conn.close()
    if row:
        return jsonify({"ok": True, "expires_at": row["expires_at"]})
    return jsonify({"ok": False, "error": "Key không khớp hoặc đã hết hạn"})

@app.route("/health")
def health():
    return jsonify({"ok": True, "day": today_vn(), "ts": ms_now()})

init_db()
if __name__ == "__main__":
    import requests
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
