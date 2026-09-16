# -*- coding: utf-8 -*-
# PLP FREE KEY SERVER — Neon UI + Device Binding + 20min Key
from __future__ import annotations
import os, time, random, hashlib, sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, render_template_string, make_response

app = Flask(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DB_PATH = os.environ.get("DB_PATH", "freekey.db")
SESSION_MINUTES = 20
SERVER_SECRET = os.environ.get("SERVER_SECRET", "plp-free-2026")

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

def get_key_for_device(device_id: str):
    """Trả về key còn hạn của device, hoặc None."""
    if not device_id: return None
    h = device_hash(device_id)
    conn = get_db(); c = conn.cursor()
    row = c.execute("""SELECT * FROM keys WHERE device_id=? AND expires_at>?
                       ORDER BY created_at DESC LIMIT 1""", (h, ms_now())).fetchone()
    conn.close()
    return dict(row) if row else None

def create_key_for_device(device_id: str) -> dict:
    h = device_hash(device_id)
    k = gen_key()
    now = ms_now()
    exp = now + SESSION_MINUTES * 60 * 1000
    conn = get_db(); c = conn.cursor()
    # xoá key cũ của device này (nếu có)
    c.execute("DELETE FROM keys WHERE device_id=?", (h,))
    c.execute("""INSERT INTO keys (device_id, key, created_at, expires_at, day)
                 VALUES (?,?,?,?,?)""", (h, k, now, exp, today_vn()))
    conn.commit(); conn.close()
    return {"key": k, "created_at": now, "expires_at": exp}

# ============================================================
# NEON UI
# ============================================================
PAGE = """
<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ PLP KEY ⚡</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',system-ui,sans-serif}
@keyframes glow{0%,100%{box-shadow:0 0 20px #00ffff,0 0 40px #00ffff55,0 0 60px #00ffff22;border-color:#00ffff}
50%{box-shadow:0 0 30px #ff00ff,0 0 60px #ff00ff55,0 0 90px #ff00ff22;border-color:#ff00ff}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@keyframes scan{0%{transform:translateX(-100%)}100%{transform:translateX(200%)}}
@keyframes flicker{0%,100%{opacity:1}45%{opacity:1}50%{opacity:.6}55%{opacity:1}}
@keyframes rgb{0%{filter:hue-rotate(0deg)}100%{filter:hue-rotate(360deg)}}
body{
  background:radial-gradient(ellipse at top,#0a0e27 0%,#05060f 60%,#000 100%);
  color:#eaf2ff;min-height:100vh;padding:20px;
  display:flex;align-items:center;justify-content:center;overflow-x:hidden;
  font-family:'Segoe UI',sans-serif
}
body::before{
  content:'';position:fixed;inset:0;
  background-image:
    linear-gradient(rgba(0,255,255,0.04) 1px,transparent 1px),
    linear-gradient(90deg,rgba(255,0,255,0.04) 1px,transparent 1px);
  background-size:40px 40px;
  pointer-events:none;z-index:0
}
.card{
  position:relative;z-index:1;
  max-width:520px;width:100%;
  background:linear-gradient(145deg,rgba(10,15,35,.95),rgba(5,8,20,.98));
  border:2px solid #00ffff;
  border-radius:20px;
  padding:32px 24px;text-align:center;
  animation:glow 3s ease-in-out infinite,float 4s ease-in-out infinite;
  overflow:hidden
}
.card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,transparent,#00ffff,#ff00ff,#00ffff,transparent);
  animation:scan 3s linear infinite
}
h1{
  font-size:32px;font-weight:900;letter-spacing:4px;
  background:linear-gradient(135deg,#00ffff,#ff00ff,#00ffff);
  background-size:200% 200%;
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
  animation:rgb 4s linear infinite,flicker 3s infinite;
  margin-bottom:6px
}
.sub{
  color:#00ffff;font-size:11px;letter-spacing:4px;
  text-transform:uppercase;opacity:.7;margin-bottom:24px;
  text-shadow:0 0 10px #00ffff
}
.keybox{
  position:relative;
  background:rgba(0,0,0,.6);
  border:2px dashed #00ffff88;
  border-radius:14px;
  padding:28px 16px;margin:16px 0;
  transition:all .3s
}
.keybox.active{
  border:2px solid #00ff88;
  box-shadow:0 0 30px #00ff8855,inset 0 0 20px #00ff8822
}
.keybox.empty{
  border:2px dashed #ff0055aa;
  box-shadow:0 0 20px #ff005533
}
.key{
  font-family:'Consolas',monospace;font-size:44px;font-weight:900;
  letter-spacing:8px;color:#00ffff;user-select:all;
  text-shadow:0 0 10px #00ffff,0 0 20px #00ffff88,0 0 30px #00ffff44;
  word-break:break-all;margin:6px 0
}
.keybox.empty .key{
  color:#ff0055;font-size:22px;letter-spacing:3px;
  text-shadow:0 0 10px #ff0055
}
.timer{font-size:14px;color:#7a8ca3;margin-top:14px}
.timer b{color:#ffd740;font-family:monospace;font-size:20px;
  text-shadow:0 0 8px #ffd740}
.day{font-size:11px;color:#7a8ca3;margin-top:8px;letter-spacing:1px}
button{
  padding:16px 28px;border:none;border-radius:12px;
  font-weight:800;font-size:14px;cursor:pointer;
  letter-spacing:2px;text-transform:uppercase;
  background:linear-gradient(135deg,#00ffff,#0066ff);
  color:#000;width:100%;margin-top:8px;
  box-shadow:0 0 20px #00ffff55,inset 0 0 10px #ffffff33;
  transition:all .25s;font-family:inherit
}
button:hover{
  transform:translateY(-2px);
  box-shadow:0 0 30px #00ffff99,0 0 50px #00ffff55,inset 0 0 15px #ffffff66
}
button:active{transform:translateY(0)}
button:disabled{opacity:.5;cursor:not-allowed;filter:grayscale(.5)}
.btn-copy{
  background:linear-gradient(135deg,#00ff88,#00aa55);
  box-shadow:0 0 20px #00ff8855
}
.btn-copy:hover{box-shadow:0 0 30px #00ff88aa,0 0 50px #00ff8855}
.btn-reload{
  background:linear-gradient(135deg,#ff00ff,#8800ff);
  color:#fff;box-shadow:0 0 20px #ff00ff55
}
.btn-reload:hover{box-shadow:0 0 30px #ff00ffaa,0 0 50px #ff00ff55}
.footer{
  margin-top:22px;font-size:11px;color:#7a8ca3;letter-spacing:1px;
  line-height:1.8
}
.footer b{color:#00ffff;text-shadow:0 0 6px #00ffff}
.toast{
  position:fixed;top:20px;left:50%;transform:translateX(-50%) translateY(-100px);
  background:linear-gradient(135deg,#00ff88,#00aa55);color:#000;
  padding:14px 28px;border-radius:12px;font-weight:800;
  box-shadow:0 0 30px #00ff88aa;transition:transform .4s;
  z-index:9999;letter-spacing:1px
}
.toast.show{transform:translateX(-50%) translateY(0)}
.tag{
  display:inline-block;padding:4px 12px;border-radius:20px;
  background:rgba(0,255,255,.1);color:#00ffff;
  font-size:10px;letter-spacing:2px;
  border:1px solid #00ffff44;margin-bottom:12px;
  text-shadow:0 0 6px #00ffff
}
.tag.warn{background:rgba(255,0,85,.1);color:#ff0055;border-color:#ff005544;
  text-shadow:0 0 6px #ff0055}
</style></head><body>

<div id="toast" class="toast">✓ Đã copy key!</div>

<div class="card">
  <h1>⚡ PLP KEY ⚡</h1>
  <div class="sub">Free Key System</div>

  <div id="keybox" class="keybox empty">
    <div class="tag" id="tag">ĐANG TẢI</div>
    <div id="keytext" class="key">Đang tải...</div>
    <div id="timer" class="timer"></div>
    <div id="day" class="day"></div>
  </div>

  <div id="actions"></div>

  <div class="footer">
    ⚡ Key tự đổi mỗi <b>20 phút</b><br>
    🔒 Gắn cứng với thiết bị của bạn — không share được
  </div>
</div>

<script>
const box = document.getElementById('keybox');
const keyEl = document.getElementById('keytext');
const tagEl = document.getElementById('tag');
const timerEl = document.getElementById('timer');
const dayEl = document.getElementById('day');
const actionsEl = document.getElementById('actions');
const toastEl = document.getElementById('toast');

let currentEnd = 0, tickTimer = null, deviceId = '';

function showToast(msg){
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  setTimeout(()=>toastEl.classList.remove('show'), 1800);
}
function fmt(n){ return String(n).padStart(2,'0'); }
function renderTime(ms){
  if (ms<=0) return '00:00';
  const s = Math.floor(ms/1000);
  return fmt(Math.floor(s/60))+':'+fmt(s%60);
}
function getDeviceId(){
  // Lấy từ URL: ?device=xxx  hoặc localStorage
  const u = new URL(location.href);
  const q = u.searchParams.get('device');
  if (q){
    localStorage.setItem('plp_device', q);
    return q;
  }
  return localStorage.getItem('plp_device') || '';
}

async function load(){
  deviceId = getDeviceId();
  dayEl.textContent = '📅 ' + new Date().toLocaleDateString('vi-VN');

  if (!deviceId){
    box.className = 'keybox empty';
    tagEl.textContent = 'CHƯA CÓ DEVICE';
    tagEl.className = 'tag warn';
    keyEl.textContent = 'MỞ TOOL VÀ BẤM LẤY KEY';
    timerEl.innerHTML = '';
    actionsEl.innerHTML = '';
    return;
  }

  const r = await fetch('/api/key?device_id=' + encodeURIComponent(deviceId),
                        {cache:'no-store'});
  const j = await r.json();

  if (j.status === 'active'){
    box.className = 'keybox active';
    tagEl.textContent = '● KEY ĐANG HOẠT ĐỘNG';
    tagEl.className = 'tag';
    keyEl.textContent = j.key;
    currentEnd = j.expires_at;
    timerEl.innerHTML = '⏱️ Còn lại: <b id="cd">--:--</b>';
    actionsEl.innerHTML =
      '<button class="btn-copy" onclick="copyKey()">📋 COPY KEY</button>' +
      '<button class="btn-reload" style="margin-top:10px" onclick="location.reload()">🔄 LÀM MỚI</button>';
    startCountdown();
    return;
  }

  if (j.status === 'new'){
    box.className = 'keybox empty';
    tagEl.textContent = '● CHƯA CÓ KEY';
    tagEl.className = 'tag warn';
    keyEl.textContent = 'NHẤN NÚT ĐỂ NHẬN KEY';
    timerEl.innerHTML = '';
    actionsEl.innerHTML = '<button onclick="getKey()">🎁 NHẬN KEY NGAY</button>';
    return;
  }

  if (j.status === 'expired'){
    box.className = 'keybox empty';
    tagEl.textContent = '● KEY ĐÃ HẾT HẠN';
    tagEl.className = 'tag warn';
    keyEl.textContent = 'NHẤN LÀM MỚI ĐỂ LẤY KEY MỚI';
    timerEl.innerHTML = '';
    actionsEl.innerHTML = '<button class="btn-reload" onclick="location.reload()">🔄 LÀM MỚI</button>';
    return;
  }

  box.className = 'keybox empty';
  tagEl.textContent = 'LỖI';
  keyEl.textContent = 'KHÔNG CÓ KEY';
  timerEl.innerHTML = '';
  actionsEl.innerHTML = '<button class="btn-reload" onclick="location.reload()">🔄 THỬ LẠI</button>';
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
  actionsEl.innerHTML = '<button disabled>Đang tạo key...</button>';
  const r = await fetch('/api/key/new?device_id=' + encodeURIComponent(deviceId),
                        {method:'POST', cache:'no-store'});
  const j = await r.json();
  if (j.ok) load();
  else { showToast('❌ ' + (j.error||'Lỗi')); load(); }
}

function copyKey(){
  const k = keyEl.textContent.trim();
  if (k && k.length === 7){
    navigator.clipboard.writeText(k).then(()=>showToast('✓ Đã copy: ' + k));
  }
}

load();
setInterval(()=>{ if (!tickTimer) load(); }, 30000);
</script>
</body></html>
"""

@app.route("/")
def index():
    return render_template_string(PAGE)

# ============================================================
# API
# ============================================================
@app.route("/api/key", methods=["GET"])
def api_key():
    device_id = request.args.get("device_id", "").strip()
    if not device_id:
        return jsonify({"status": "locked", "error": "missing device_id"})

    row = get_key_for_device(device_id)
    if row:
        return jsonify({
            "status": "active",
            "key": row["key"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        })

    # chưa có key hoặc đã hết hạn → "new"
    return jsonify({"status": "new"})

@app.route("/api/key/new", methods=["POST"])
def api_new_key():
    device_id = request.args.get("device_id", "").strip()
    if not device_id:
        return jsonify({"ok": False, "error": "missing device_id"}), 400

    # check xem còn key chưa hết hạn không
    row = get_key_for_device(device_id)
    if row:
        return jsonify({"ok": False, "error": "Bạn đã có key còn hiệu lực"}), 429

    res = create_key_for_device(device_id)
    return jsonify({"ok": True, **res})

@app.route("/health")
def health():
    return jsonify({"ok": True, "day": today_vn(), "ts": ms_now()})

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
