#!/usr/bin/env python3
"""
Smart-Stua IoT Simulation Engine v1.0
Mimics ESP32+SIM800L grain-silo sensor nodes.

Usage:
    python simulator.py
    python simulator.py --url http://192.168.1.179:8000/api --interval 10
    python simulator.py --nodes NODE_001 NODE_002 --anomaly-rate 0.15
"""
import argparse
import io
import math
import os
import random
import signal
import sys
import threading
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Force UTF-8 so box-drawing / emoji render on Windows PowerShell / CMD
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── ANSI colours ──────────────────────────────────────────────────────────────
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.kernel32.SetConsoleMode(
        ctypes.windll.kernel32.GetStdHandle(-11), 7)

G, Y, R, M, C, B = '\033[92m', '\033[93m', '\033[91m', '\033[95m', '\033[96m', '\033[1m'
DIM, RST = '\033[2m', '\033[0m'

# ── Defaults (override in simulator/.env) ────────────────────────────────────
URL          = os.getenv('SIMULATOR_BASE_URL',   'http://127.0.0.1:8000/api')
API_KEY      = os.getenv('SIMULATOR_API_KEY',    'dev-sensor-api-key')
INTERVAL_S   = int(os.getenv('SIMULATOR_INTERVAL_S',   '5'))
ANOMALY_RATE = float(os.getenv('SIMULATOR_ANOMALY_RATE', '0.08'))

# node_identifier → (location_label, temp_offset_°C)
DEFAULT_NODES = {
    'NODE_001': ('Gulu Main Store - Section A', +2.0),
    'NODE_002': ('Gulu Main Store - Section B',  0.0),
    'NODE_003': ('Lira Transit Depot - Bay 1',  -1.5),
}

_PRINT_LOCK = threading.Lock()


# ── Physics engine ────────────────────────────────────────────────────────────
class SensorPhysics:
    """Generates realistic DHT22-style readings with natural diurnal variation."""

    BASE_TEMP      = 27.0   # °C ambient
    DIURNAL_AMP    = 4.5    # °C peak-to-trough
    BASE_HUM       = 65.0   # % afternoon baseline
    HUM_TEMP_COEFF = -1.2   # %/°C (humidity drops as temp rises)
    DRIFT_T_STD    = 0.25   # °C Gaussian noise
    DRIFT_H_STD    = 0.40   # % Gaussian noise

    def __init__(self, node_id, temp_offset=0.0, anomaly_rate=0.08):
        self.node_id       = node_id
        self.temp_offset   = temp_offset
        self.anomaly_rate  = anomaly_rate
        self._drift_t      = 0.0
        self._drift_h      = 0.0
        self._battery      = random.uniform(85.0, 100.0)
        self._anom_active  = False
        self._anom_ticks   = 0
        self._anom_type    = None

    def _diurnal(self):
        h = datetime.now().hour + datetime.now().minute / 60.0
        return self.BASE_TEMP + self.DIURNAL_AMP * math.cos(2*math.pi*(h-14)/24) + self.temp_offset

    def _step_drift(self):
        s = 0.15  # mean-reversion speed
        self._drift_t = (1-s)*self._drift_t + random.gauss(0, self.DRIFT_T_STD)
        self._drift_h = (1-s)*self._drift_h + random.gauss(0, self.DRIFT_H_STD)

    def _step_battery(self):
        self._battery -= random.uniform(0.005, 0.025)
        if self._battery < 20.0 and random.random() < 0.05:
            self._battery = random.uniform(85.0, 100.0)
        self._battery = max(0.0, min(100.0, self._battery))
        return round(self._battery, 1)

    def _maybe_anomaly(self):
        if not self._anom_active and random.random() < self.anomaly_rate:
            self._anom_type   = random.choice(['spike', 'high_risk_burst', 'dropout', 'offline'])
            self._anom_active = True
            self._anom_ticks  = random.randint(1, 4)

    def _apply_anomaly(self, t, h):
        """Returns (temperature, humidity, anomaly_tag, skip_send)."""
        tag = self._anom_type
        skip = False
        if tag == 'spike':
            d = random.choice([-1, 1])
            t = max(-40, min(80, t + d*random.uniform(8, 15)))
            h = max(0,   min(100, h + d*random.uniform(10, 20)))
        elif tag == 'high_risk_burst':
            t = random.uniform(28.5, 33.0)
            h = random.uniform(80.0, 90.0)
        elif tag in ('dropout', 'offline'):
            t, h, skip = None, None, True
        return round(t, 2) if t is not None else None, \
               round(h, 2) if h is not None else None, \
               tag.upper(), skip

    def tick(self):
        self._step_drift()
        self._maybe_anomaly()

        base_t = self._diurnal() + self._drift_t
        base_h = self.BASE_HUM + self.HUM_TEMP_COEFF*(base_t - self.BASE_TEMP) + self._drift_h
        t = round(max(-40, min(80,  base_t)), 2)
        h = round(max(0,   min(100, base_h)), 2)

        anomaly_tag, skip = '', False
        if self._anom_active:
            t, h, anomaly_tag, skip = self._apply_anomaly(t, h)
            self._anom_ticks -= 1
            if self._anom_ticks <= 0:
                self._anom_active = False

        return {
            'node_id':     self.node_id,
            'temperature': t,
            'humidity':    h,
            'device_ts':   datetime.now(timezone.utc).isoformat(),
            '_battery':    self._step_battery(),
            '_anomaly':    anomaly_tag,
            '_skip':       skip,
        }


# ── HTTP transmitter ──────────────────────────────────────────────────────────
class Transmitter:
    def __init__(self, base_url, api_key):
        self.url     = base_url.rstrip('/') + '/readings/'
        self.api_key = api_key
        self.sess    = requests.Session()
        self.sess.headers.update({'Content-Type': 'application/json'})

    def send(self, payload):
        body = {k: v for k, v in payload.items() if not k.startswith('_')}
        body['api_key'] = self.api_key
        try:
            r = self.sess.post(self.url, json=body, timeout=10)
            return r.status_code == 201, r.json()
        except requests.ConnectionError:
            return False, {'error': 'Connection refused — Django server not running?'}
        except requests.Timeout:
            return False, {'error': 'Timeout'}
        except Exception as e:
            return False, {'error': str(e)}


# ── Console logger ────────────────────────────────────────────────────────────
def log_line(payload, success, resp):
    ts    = datetime.now().strftime('%H:%M:%S')
    nid   = payload['node_id']
    t, h  = payload['temperature'], payload['humidity']
    batt  = payload['_battery']
    anom  = payload['_anomaly']
    skip  = payload['_skip']

    if t is None:
        ts_str = f'{DIM}  NULL  C {RST}'
    elif t > 32 or (h is not None and h > 79):
        ts_str = f'{R}{t:>6.2f}C {RST}'
    elif t > 28 or (h is not None and h > 70):
        ts_str = f'{Y}{t:>6.2f}C {RST}'
    else:
        ts_str = f'{G}{t:>6.2f}C {RST}'

    h_str   = f'{h:>6.2f}%' if h is not None else f'{DIM}  NULL %{RST}'
    b_str   = f'{DIM}{batt:>5.1f}%{RST}'

    if skip:
        st = f'{M}[{anom:^16}]{RST}'
    elif success:
        st = f'{G}[OK rid={resp.get("reading_id","?")}]{RST}'
    else:
        st = f'{R}[!! {str(resp.get("error",resp))[:28]}]{RST}'

    anom_str = f' {Y}** {anom}{RST}' if anom and not skip else ''
    with _PRINT_LOCK:
        print(f'{DIM}{ts}{RST} {C}{B}{nid:<10}{RST} T={ts_str} H={h_str} Bat={b_str} {st}{anom_str}')


# ── Worker thread ─────────────────────────────────────────────────────────────
class NodeWorker(threading.Thread):
    def __init__(self, node_id, temp_offset, tx, interval, anomaly_rate, stop):
        super().__init__(name=f'Worker-{node_id}', daemon=True)
        self.physics  = SensorPhysics(node_id, temp_offset, anomaly_rate)
        self.tx       = tx
        self.interval = interval
        self.stop     = stop

    def run(self):
        time.sleep(random.uniform(0, 1.5))  # stagger startup
        while not self.stop.is_set():
            t0      = time.monotonic()
            payload = self.physics.tick()
            if payload['_skip']:
                log_line(payload, False, {})
            else:
                ok, resp = self.tx.send(payload)
                log_line(payload, ok, resp)
            self.stop.wait(timeout=max(0, self.interval - (time.monotonic()-t0)))


# ── Pre-flight check ──────────────────────────────────────────────────────────
def preflight(base_url, api_key, node_ids):
    print(f'\n{B}--- Pre-flight Check ------------------------------------------{RST}')
    ok = True
    for nid in node_ids:
        probe = {'node_id': nid, 'temperature': 25.0,
                 'humidity': 60.0, 'api_key': api_key}
        try:
            r = requests.post(base_url.rstrip('/')+'/readings/', json=probe, timeout=8)
            if r.status_code == 201:
                print(f'  {G}OK{RST} {C}{nid}{RST} - active in DB')
            elif r.status_code == 400:
                body = r.json()
                det  = str(body.get('details', body))
                if 'api_key' in det:
                    print(f'  {R}!! {nid}: API key invalid{RST}')
                    print(f'    -> Check SENSOR_API_KEY in backend/.env and SIMULATOR_API_KEY in simulator/.env')
                else:
                    print(f'  {Y}!! {nid}: not in DB - run seed_nodes.py first{RST}')
                ok = False
            else:
                print(f'  {Y}?  {nid}: HTTP {r.status_code}{RST}')
        except requests.ConnectionError:
            print(f'  {R}!! Cannot reach {base_url}{RST}')
            print(f'    -> Start Django: python manage.py runserver 0.0.0.0:8000')
            return False
    print(f'{B}--------------------------------------------------------------{RST}\n')
    return ok


# ── Banner ────────────────────────────────────────────────────────────────────
def banner(nodes, url, interval, anom):
    print(f"""
{C}{B}+======================================================+
|      Smart-Stua  IoT Simulation Engine  v1.0         |
+======================================================+{RST}

  {B}Endpoint :{RST} {url}/readings/
  {B}Nodes    :{RST} {', '.join(nodes)}
  {B}Interval :{RST} {interval}s/node    {B}Anomaly rate:{RST} {anom*100:.0f}%
  {B}Started  :{RST} {datetime.now():%Y-%m-%d %H:%M:%S}

  Press {Y}CTRL+C{RST} to stop.   Legend: {G}safe {Y}medium {R}high-risk {M}anomaly{RST}
  {'-'*54}
""")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description='Smart-Stua IoT Node Simulator')
    p.add_argument('--url',           default=URL)
    p.add_argument('--api-key',       default=API_KEY)
    p.add_argument('--interval',      type=int,   default=INTERVAL_S)
    p.add_argument('--anomaly-rate',  type=float, default=ANOMALY_RATE)
    p.add_argument('--nodes',         nargs='+',  default=list(DEFAULT_NODES.keys()))
    p.add_argument('--skip-preflight', action='store_true')
    args = p.parse_args()

    tx   = Transmitter(args.url, args.api_key)
    banner(args.nodes, args.url, args.interval, args.anomaly_rate)

    if not args.skip_preflight:
        if not preflight(args.url, args.api_key, args.nodes):
            print(f'{Y}!! Fix above errors or use --skip-preflight{RST}')
            sys.exit(1)

    stop = threading.Event()
    workers = []
    for nid in args.nodes:
        _, offset = DEFAULT_NODES.get(nid, ('Unknown', 0.0))
        w = NodeWorker(nid, offset, tx, args.interval, args.anomaly_rate, stop)
        workers.append(w)
        w.start()

    def _shutdown(sig, frame):
        print(f'\n{Y}Stopping simulator...{RST}')
        stop.set()
        for w in workers:
            w.join(timeout=3)
        print(f'{G}Done. Goodbye!{RST}')
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
