import json
import os
import random
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from db import drones, events, samples
from model import FEATURES, NAMES, position, reading, trained


def now():
    return datetime.now(timezone.utc).isoformat()


def log(c, device, kind, detail, severity="Info", status="Recorded", score=None, incident=None):
    return c.execute(events.insert().values(drone=device, time=now(), kind=kind, detail=detail,
                     severity=severity, status=status, score=score, incident=incident)).inserted_primary_key[0]


class FlightWatch:
    def __init__(self):
        self.keys = {i: AESGCM(AESGCM.generate_key(bit_length=256)) for i in range(3)}
        self.arrivals = defaultdict(deque)

    def seed(self, c):
        for i, name in enumerate(NAMES):
            if not c.scalar(select(drones.c.name).where(drones.c.id == i)):
                c.execute(drones.insert().values(id=i, name=name, mode="Patrol", seq=0, streak=0,
                                                trusted=position(i, 0)))
                self.advance(c, i)
                log(c, i, "Flight online", "Authenticated telemetry established.")

    def seal(self, device, seq, row):
        nonce = os.urandom(12)
        header = f"{device}/{seq}".encode()
        return nonce, self.keys[device].encrypt(nonce, json.dumps(row).encode(), header)

    def receive(self, c, drone, sender, seq, envelope, arrived=None):
        device = drone["id"]
        if sender != device or sender not in self.keys:
            return "Unknown sender"
        nonce, payload = envelope
        try:
            raw = self.keys[sender].decrypt(nonce, payload, f"{sender}/{seq}".encode())
        except InvalidTag:
            return "Integrity failure"
        if seq <= drone["seq"]:
            return "Duplicate sequence"
        times = self.arrivals[device]
        clock = time.monotonic() if arrived is None else arrived
        while times and times[0] <= clock - 1:
            times.popleft()
        if len(times) >= 8:
            return "Rate limit"
        row = json.loads(raw)
        score = float(trained()[0].predict_proba([[row[f] for f in FEATURES]])[0, 1])
        expected = position(device, seq)
        suspect = score >= .5 or max(abs(row[f] - v) for f, v in zip(FEATURES, expected)) > .0015
        streak = drone["streak"] + 1 if suspect else 0
        mode = drone["mode"]
        if streak >= 2 and mode == "Patrol":
            mode = "Attitude hold"
            incident = log(c, device, "GPS deviation", "Two consecutive suspect fixes.", "High", "Open", score)
            log(c, device, "Attitude hold", "Simulator holds the last trusted fix.", incident=incident)
        c.execute(samples.insert().values(drone=device, seq=seq, time=now(), reading=row,
                                          expected=expected, score=score))
        c.execute(drones.update().where(drones.c.id == device).values(seq=seq, mode=mode, streak=streak,
                  trusted=drone["trusted"] if suspect or mode != "Patrol" else [row["latitude"],row["longitude"]]))
        times.append(clock)
        return None

    def advance(self, c, device, case="normal", arrived=None):
        drone = c.execute(select(drones).where(drones.c.id == device).with_for_update()).mappings().one()
        seq = drone["seq"] + (case != "duplicate")
        row = reading(device, seq, case == "gps", random.Random(device * 100000 + seq))
        nonce, data = self.seal(device, seq, row)
        if case == "integrity":
            data = data[:-1] + bytes([data[-1] ^ 1])
        error = self.receive(c, drone, -1 if case == "unknown" else device, seq, (nonce, data), arrived)
        if error:
            log(c, device, error, "Message rejected before telemetry update.", "Medium", "Open")
        return error
