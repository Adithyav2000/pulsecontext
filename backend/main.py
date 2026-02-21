from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from typing import List
from datetime import datetime, timedelta, timezone
import random

from models import EventIn
from repo_events import EventRepo
from service_events import EventService
from settings import settings

app = FastAPI(title="PulseContext Backend")

# Instantiate the repo + service here so the routes remain thin and
# replaceable for testing. A future enhancement could inject mocks in
# tests or use a factory pattern to swap implementations.
repo = EventRepo()
svc = EventService(repo)

@app.get("/health")
def health():
    try:
        svc.health_check()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB health check failed: {e}")

@app.post("/ingest")
def ingest(events: List[EventIn]):
    try:
        inserted = svc.ingest_events(events, caller_user=None)  # later: auth user here
        return {"inserted": inserted}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")

@app.get("/timeline")
def timeline(user_id: str = Query(...), limit: int = 200):
    try:
        return svc.get_timeline(user_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Timeline failed: {e}")

@app.post("/seed")
def seed(user_id: str = settings.default_user, days_ago: int = 0):
    now = datetime.now(timezone.utc) - timedelta(days=days_ago)
    start = now.replace(hour=6, minute=0, second=0, microsecond=0)

    events: List[EventIn] = []
    ts = start

    for _ in range(200):
        hour = ts.hour
        if 8 <= hour <= 9:
            motion = random.choice(["walking", "automotive"])
            hr = random.randint(95, 120)
            place = "commute"
        elif 10 <= hour <= 17:
            motion = random.choice(["sedentary", "walking"])
            hr = random.randint(65, 90)
            place = "work"
        elif 18 <= hour <= 19:
            motion = random.choice(["workout", "walking"])
            hr = random.randint(110, 155)
            place = "gym"
        else:
            motion = random.choice(["sedentary", "walking"])
            hr = random.randint(60, 85)
            place = "home"

        events.append(EventIn(
            user_id=user_id,
            ts=ts,
            type="context_snapshot",
            source="simulator",
            payload={"motion": motion, "heart_rate": hr, "place": place, "v": 1},
        ))
        ts += timedelta(minutes=5)

    # NOTE: call the facade/service, NOT the raw repo
    inserted = svc.ingest_events(events, caller_user=None)
    return {"inserted": inserted}

@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>PulseContext Timeline</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    input, button { padding: 8px; }
    .row { padding: 10px; border: 1px solid #ddd; margin: 8px 0; border-radius: 8px; }
    .ts { color: #666; font-size: 12px; }
    pre { background: #f7f7f7; padding: 10px; border-radius: 8px; overflow:auto; }
  </style>
</head>
<body>
  <h2>PulseContext Timeline</h2>
  <div>
    User: <input id="user" value="adithya"/>
    Limit: <input id="limit" value="50" style="width:60px"/>
    <button onclick="load()">Load</button>
    <button onclick="seed()">Seed Demo</button>
  </div>
  <div id="out"></div>

<script>
async function seed(){
  await fetch('/seed', {method:'POST'});
  await load();
}
async function load(){
  const user = document.getElementById('user').value;
  const limit = document.getElementById('limit').value;
  const res = await fetch(`/timeline?user_id=${encodeURIComponent(user)}&limit=${limit}`);
  const data = await res.json();
  const out = document.getElementById('out');
  out.innerHTML = '';
  data.forEach(e => {
    const div = document.createElement('div');
    div.className='row';
    div.innerHTML = `
      <div><b>${e.type}</b> <span style="color:#999">(${e.source})</span></div>
      <div class="ts">${e.ts}</div>
      <pre>${JSON.stringify(e.payload, null, 2)}</pre>
    `;
    out.appendChild(div);
  });
}
load();
</script>
</body>
</html>
"""
