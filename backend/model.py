"""Synthetic flight-level holdout evaluation and simulation fixtures."""
from functools import lru_cache
import math
import random
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

FEATURES = ("latitude", "longitude", "speed", "acceleration", "gyroscope", "signal")
NAMES = ("Alpha-Wing", "Beta-Rotor", "Gamma-Glide")
MODEL_TYPES = ("Fixed-Wing UAV", "Quad-Rotor Interceptor", "VTOL Survey Glider")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two WGS84 coordinates."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def position(drone, step, base_lat=None, base_lon=None, route_config=None):
    if route_config and len(route_config) >= 2:
        pt = route_config[step % len(route_config)]
        return (float(pt[0]), float(pt[1]))
    lat0 = 13.046 + drone * 0.001 if base_lat is None else float(base_lat)
    lon0 = 80.205 + drone * 0.003 if base_lon is None else float(base_lon)
    angle = (step % 72) * math.tau / 72
    return (lat0 + 0.002 * math.sin(angle), lon0 + 0.003 * math.cos(angle))


def reading(drone, step, anomaly, rng, base_lat=None, base_lon=None, route_config=None):
    lat, lon = position(drone, step, base_lat=base_lat, base_lon=base_lon, route_config=route_config)
    offset = rng.uniform(0.0018, 0.0034) if anomaly else 0
    values = [
        lat + offset,
        lon + offset,
        rng.gauss(31 if anomaly else 22, 5),
        abs(rng.gauss(2.3 if anomaly else 1.3, 0.65)),
        abs(rng.gauss(0.95 if anomaly else 0.55, 0.25)),
        min(100, max(0, rng.gauss(70 if anomaly else 91, 7))),
    ]
    return dict(zip(FEATURES, (round(v, 6) for v in values)))


def dataset():
    for flight in range(100):
        rng = random.Random(4310 + flight)
        for step in range(20):
            row = reading(flight % 3, step + flight, flight % 2, rng)
            yield {"flight": flight, **row, "is_spoofed": flight % 2}


def fit(records):
    train_x, train_y, test_x, test_y = [], [], [], []
    for row in records:
        x, y = (test_x, test_y) if int(row["flight"]) % 5 == 0 else (train_x, train_y)
        x.append([float(row[f]) for f in FEATURES])
        y.append(int(row["is_spoofed"]))
    model = RandomForestClassifier(n_estimators=100, random_state=4310).fit(train_x, train_y)
    predicted = model.predict(test_x)
    return model, {
        "train": len(train_y),
        "test": len(test_y),
        "seed": 4310,
        "accuracy": float(accuracy_score(test_y, predicted)),
        "metrics": classification_report(test_y, predicted, output_dict=True),
        "confusion_matrix": confusion_matrix(test_y, predicted).tolist(),
        "importance": dict(zip(FEATURES, model.feature_importances_.tolist())),
    }


@lru_cache
def trained():
    return fit(dataset())


if __name__ == "__main__":
    import json

    print(json.dumps(trained()[1], indent=2))
