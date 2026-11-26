# SkySentinel implementation plan

## Operator journey
Open the flight chart, select Alpha-Wing, Beta-Rotor or Gamma-Glide, and start a demonstration. Follow its reported and expected positions, inspect its six sensor readings, acknowledge an incident, and review recovery history after a refresh. Every flight and recovery action is simulated.

## Architecture and milestones
1. React with TypeScript and Vite serves the console. FastAPI owns scenario execution, validation and persistence. Neon PostgreSQL stores drone identity, telemetry and incident history. SQLAlchemy and Alembic manage access and schema revisions. Credentials live only in the backend environment.
2. The simulator submits per-device AES-GCM authenticated measurements. Check device identity, integrity, sequence and message frequency before a measurement can change a flight track. Replay recorded rejection scenarios through the UI.
3. Train a reproducible Random Forest using latitude, longitude, speed, acceleration, gyroscope and signal strength. Generate 1,000 normal and 1,000 anomalous samples. Hold out complete flights totaling 400 readings. Publish actual evaluation metrics and confusion matrix.
4. Compare expected and reported paths. Two consecutive anomalous readings open one incident and trigger a simulated hold. Record acknowledgement and return-to-home on the same incident. Preserve the last trusted fix.
5. Finish with a repeatable normal flight, network rejection, GPS deviation and recovery demo.

## Interface and movement
Use a daylight aviation-chart palette, ink labels, pale blue graph paper, teal expected paths and vermilion reported deviations. Pair a serif editorial heading with instrument-style numerals. Use a wide route plot beside a narrow flight strip and an incident ledger below. Stack the plot and controls on phones. Animate changes to aircraft position and new incident entries. Respect reduced motion, keyboard focus and text status labels.

## Verification
Exercise all three drones, replay and integrity rejection, rate checks, GPS detection, incident deduplication, acknowledgement, recovery and persistence. Build and type-check React. Exercise controls in a browser. Run migrations and repeat the demo against Neon when its connection string is available. Use a temporary database for isolated tests.

## Verification results
The initial migration completed on Neon. The isolated API test covered the rejection fixtures, last trusted fix, recovery state transitions, invalid commands and database persistence across an application restart. The React type check and production build passed. Two Edge browser tests exercised continuous patrol, aircraft selection, rejection, acknowledgement, recovery, reload and results display against the Neon-backed API. The mobile check used a 390 px viewport and verified the chart was visible without horizontal overflow.

The Random Forest classified 397 of 400 held-out synthetic readings correctly. It flagged two normal readings and missed one anomalous reading. Spoofing-class precision was 99.00%, recall was 99.50% and F1 was 0.9925. These figures evaluate the classifier on the simulator's data distribution. Field performance requires independently collected flight data.
