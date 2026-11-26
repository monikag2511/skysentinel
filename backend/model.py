"""Synthetic flight-level holdout evaluation and simulation fixtures."""
from functools import lru_cache
import math
import random
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

FEATURES = ("latitude", "longitude", "speed", "acceleration", "gyroscope", "signal")
NAMES = ("Alpha-Wing", "Beta-Rotor", "Gamma-Glide")


def position(drone, step):
    angle = (step % 72) * math.tau / 72
    return (13.046 + drone * .001 + .002 * math.sin(angle),
            80.205 + drone * .003 + .003 * math.cos(angle))


def reading(drone, step, anomaly, rng):
    lat, lon = position(drone, step)
    offset = rng.uniform(.0018, .0034) if anomaly else 0
    values = [lat + offset, lon + offset, rng.gauss(31 if anomaly else 22, 5),
              abs(rng.gauss(2.3 if anomaly else 1.3, .65)),
              abs(rng.gauss(.95 if anomaly else .55, .25)),
              min(100, max(0, rng.gauss(70 if anomaly else 91, 7)))]
    return dict(zip(FEATURES, (round(v, 6) for v in values)))


@lru_cache
def trained():
    train_x, train_y, test_x, test_y = [], [], [], []
    for flight in range(100):
        rng = random.Random(4310 + flight)
        x, y = (test_x, test_y) if flight % 5 == 0 else (train_x, train_y)
        for step in range(20):
            row = reading(flight % 3, step + flight, flight % 2, rng)
            x.append(list(row.values()))
            y.append(flight % 2)
    model = RandomForestClassifier(n_estimators=100, random_state=4310).fit(train_x, train_y)
    predicted = model.predict(test_x)
    return model, {"train": len(train_y), "test": len(test_y), "seed": 4310,
                   "metrics": classification_report(test_y, predicted, output_dict=True),
                   "confusion_matrix": confusion_matrix(test_y, predicted).tolist()}


if __name__ == "__main__":
    import json
    print(json.dumps(trained()[1], indent=2))
