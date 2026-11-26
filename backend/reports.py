"""PDF and CSV report generation with zero external binary dependencies."""
import csv
import io
from datetime import datetime, timezone


def _escape_pdf_text(text: str) -> str:
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf_report(summary: dict) -> bytes:
    """Build a valid multi-page PDF 1.4 security report."""
    lines: list[tuple[str, int]] = [
        ("SkySentinel Drone Cybersecurity Report", 16),
        (f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}", 10),
        ("", 8),
        ("1. Drone Activity Summary", 13),
        (
            f"Total Drones: {summary['overview']['total_drones']} | Active: {summary['overview']['active_drones']} | "
            f"Spoofed: {summary['overview']['spoofed_drones']}",
            10,
        ),
    ]
    for d in summary["drones"]:
        lines.append(
            (
                f"  - {d['code']} {d['name']}: mode={d['mode']}, gps={d['gps_status']}, "
                f"comm={d['comm_status']}, battery={d['battery']}%, alt={d['altitude']}m",
                9,
            )
        )

    lines.extend(
        [
            ("", 8),
            ("2. GPS Spoofing Detection Results", 13),
            (
                f"Normal Samples: {summary['gps_detection']['normal_count']} | "
                f"Spoofed Samples: {summary['gps_detection']['spoofed_count']} | "
                f"Route Deviations: {summary['gps_detection']['deviation_count']}",
                10,
            ),
            ("", 8),
            ("3. Network Security Incidents", 13),
            (
                f"Total Packets: {summary['network']['total_packets']} | "
                f"Threat Packets: {summary['network']['threat_packets']} | "
                f"Blocked Devices: {summary['network']['blocked_devices']}",
                10,
            ),
            ("", 8),
            ("4. Attack Statistics", 13),
        ]
    )
    for k, v in summary["attack_stats"].items():
        lines.append((f"  - {k}: {v}", 9))

    lines.extend([("", 8), ("5. Alert History (Latest 15)", 13)])
    for a in summary["alerts"][:15]:
        sim_tag = " [SIM]" if a["simulated"] else ""
        lines.append(
            (
                f"  - {a['alert_code']}{sim_tag} | {a['severity']} | {a['attack_type']} | "
                f"{a['status']} | {a['created_at'][:19]}",
                9,
            )
        )

    lines.extend([("", 8), ("6. Recovery History (Latest 15)", 13)])
    for r in summary["recoveries"][:15]:
        lines.append(
            (
                f"  - Drone #{r['drone_id']} | Rec: {r['recommended_action']} | "
                f"Sel: {r['selected_action'] or 'Pending'} | Status: {r['status']}",
                9,
            )
        )

    ml = summary["ml_performance"]
    lines.extend(
        [
            ("", 8),
            ("7. Machine Learning Performance", 13),
            (
                f"Accuracy: {ml['accuracy'] * 100:.2f}% | Precision: {ml['precision'] * 100:.2f}% | "
                f"Recall: {ml['recall'] * 100:.2f}% | F1: {ml['f1']:.4f}",
                10,
            ),
            (f"Confusion Matrix: {ml['confusion_matrix']} (Train={ml['train']}, Test={ml['test']})", 9),
        ]
    )

    # Paginate lines into PDF pages
    pages: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    y = 755
    for text, size in lines:
        step = size + 5
        if y - step < 50:
            pages.append(current)
            current = []
            y = 755
        current.append((text, size))
        y -= step
    if current or not pages:
        pages.append(current)

    objects: list[bytes] = []

    def add_obj(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    catalog_id = add_obj(b"")  # placeholder 1
    pages_id = add_obj(b"")    # placeholder 2
    font_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids = []
    for page_lines in pages:
        stream_parts = ["BT"]
        py = 755
        for text, size in page_lines:
            if text:
                escaped = _escape_pdf_text(text[:105])
                stream_parts.append(f"/F1 {size} Tf 1 0 0 1 45 {py} Tm ({escaped}) Tj")
            py -= size + 5
        stream_parts.append("ET")
        stream_bytes = "\n".join(stream_parts).encode("latin-1")
        content_id = add_obj(
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream"
        )
        pid = add_obj(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
        )
        page_ids.append(pid)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{idx} 0 obj\n".encode("ascii"))
        out.write(obj)
        out.write(b"\nendobj\n")

    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return out.getvalue()


def build_csv_report(summary: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SkySentinel Security Report", datetime.now(timezone.utc).isoformat()])
    w.writerow([])
    w.writerow(["SECTION 1: DRONE ACTIVITY SUMMARY"])
    w.writerow(["Code", "Name", "Mode", "GPS Status", "Comm Status", "Battery %", "Altitude m"])
    for d in summary["drones"]:
        w.writerow([d["code"], d["name"], d["mode"], d["gps_status"], d["comm_status"], d["battery"], d["altitude"]])

    w.writerow([])
    w.writerow(["SECTION 2: GPS SPOOFING & ML PERFORMANCE"])
    ml = summary["ml_performance"]
    w.writerow(["Normal Samples", "Spoofed Samples", "Deviations", "ML Accuracy", "Precision", "Recall", "F1"])
    w.writerow(
        [
            summary["gps_detection"]["normal_count"],
            summary["gps_detection"]["spoofed_count"],
            summary["gps_detection"]["deviation_count"],
            f"{ml['accuracy']:.4f}",
            f"{ml['precision']:.4f}",
            f"{ml['recall']:.4f}",
            f"{ml['f1']:.4f}",
        ]
    )

    w.writerow([])
    w.writerow(["SECTION 3: ALERT HISTORY"])
    w.writerow(["Alert Code", "Drone ID", "Attack Type", "Severity", "Confidence %", "Status", "Simulated", "Timestamp", "Description"])
    for a in summary["alerts"]:
        w.writerow(
            [
                a["alert_code"],
                a["drone_id"],
                a["attack_type"],
                a["severity"],
                a["confidence"],
                a["status"],
                a["simulated"],
                a["created_at"],
                a["description"],
            ]
        )

    w.writerow([])
    w.writerow(["SECTION 4: RECOVERY HISTORY"])
    w.writerow(["ID", "Drone ID", "Recommended", "Selected", "Status", "Initiated By", "Timestamp", "Detail"])
    for r in summary["recoveries"]:
        w.writerow(
            [
                r["id"],
                r["drone_id"],
                r["recommended_action"],
                r["selected_action"] or "",
                r["status"],
                r["initiated_by"],
                r["created_at"],
                r["detail"],
            ]
        )
    return buf.getvalue()
