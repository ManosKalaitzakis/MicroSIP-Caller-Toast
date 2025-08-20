# -*- coding: utf-8 -*-
"""
MicroSIP Caller Toast (Demo, Imaginary DB) — styled v5
- Known caller: profile, tags, services, unpaid, call stats (today/week/totals).
- Unknown caller: "Unknown caller" pill + spaced phone, web results with the
  phone highlighted in bold lightgreen even if formatted with spaces/dashes.
- Safe offline demo. No real DB or network.
"""

import sys, os, re, html, csv
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, QPoint, QSize
from PySide6.QtGui import QGuiApplication, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QGraphicsDropShadowEffect, QSizePolicy
)

# === CONFIG ===
URL = "https://test.com/2822031693"
PHONE = "2827047400"   # number to check (set to an unknown number for demo)

IMG_BY_PROGRAM = {
    "Retail":      r"C:\Users\Administrator\PycharmProjects\MicroSipCalls\Retail.png",
    "Energy":      r"C:\Users\Administrator\PycharmProjects\MicroSipCalls\Energy.png",
    "Restaurant":  r"C:\Users\Administrator\PycharmProjects\MicroSipCalls\Restaurant.png",
}
IMG_UNKNOWN = r"C:\Users\Administrator\PycharmProjects\MicroSipCalls\Unknown.png"

PROGRAM_COLORS = {
    "Retail":     "#8fbfff",
    "Energy":     "#a3ffcc",
    "Restaurant": "#ffd37a",
    "Unknown":    "#dddddd",
}

TIMEOUT_MS = 10000
INI_PATH   = r"C:\Users\Administrator\AppData\Roaming\MicroSIP\microsip.ini"  # optional
LOG_PATH   = "debug.log"
CSV_PATH   = "unknown_calls.csv"

# === IMAGINARY DB (in-memory tables) ===
CUSTOMERS = {
    1: {"business_name": "Acme Bakery", "sector": "Restaurant", "program": "Restaurant"},
    2: {"business_name": "VoltGrid SA", "sector": "Energy", "program": "Energy"},
}
CONTACTS = {
    "2827047400": 1,   # PHONE above is unknown for demo
    "2105551234": 2,
}
PROFILES = {
    1: {"vat": "EL123456789","email":"info@acmebakery.gr","owner_first":"Eleni","owner_last":"Papadaki",
        "notes":"Prefers morning visits. Gluten-free line launched in June."},
    2: {"vat": "EL987654321","email":"ops@voltgrid.gr","owner_first":"Giorgos","owner_last":"Marinos",
        "notes":"Critical SLA customer. Site expansions Q4."},
}
SERVICES = {
    1: [
        {"desc":"Website redesign","amount":500.0,"date":"2025-05-18","paid":True},
        {"desc":"Monthly maintenance","amount":150.0,"date":"2025-08-01","paid":False},
    ],
    2: [
        {"desc":"Smart meter rollout","amount":1200.0,"date":"2025-07-05","paid":True},
        {"desc":"Outage dashboard","amount":800.0,"date":"2025-07-22","paid":False},
    ],
}
LABELS = {
    1: [{"name":"Owes money","color":"#FFA500"},{"name":"Invoiced","color":"#CCE5FF"},
        {"name":"Kind customer","color":"#D4EDDA"},{"name":"Priority","color":"#FFB3B3"}],
    2: [{"name":"VIP","color":"#E5CCFF"},{"name":"Net-30","color":"#FFF3CD"}],
}

# === HELPERS ===
def fs(px):  # UI font scale
    return f"{int(px * 1.2)}px"

def log(msg):
    line = f"{datetime.now()} - {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def norm_phone(p: str) -> str:
    return "".join(ch for ch in p if ch.isdigit())

def bottom_right_pos(widget_size: QSize) -> QPoint:
    screen = QGuiApplication.primaryScreen().availableGeometry()
    x = screen.right() - widget_size.width() - 24
    y = screen.bottom() - widget_size.height() - 24
    return QPoint(x, y)

def clean_line(s: str) -> str:
    s = re.sub(r"[\x00-\x1F\x7F]", "", s)
    s = s.replace(" ", "").replace("\t", "")
    return s.strip()

def strip_html(s: str) -> str:
    if not s:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", s, flags=re.S)
    no_tags = re.sub(r"\s+", " ", no_tags).strip()
    return html.unescape(no_tags)

def euro(amount: float) -> str:
    return f"€{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def highlight_phone(text: str, num: str, color="lightgreen") -> str:
    """
    Highlight the phone number in text even if spaced/dashed:
    2104848484, 210 484 8484, 210-484-8484, (210) 484 8484, etc.
    Works on escaped text to avoid HTML issues.
    """
    if not text or not num:
        return html.escape(text or "")
    seps = r"[ \u00A0\u2007\u202F\-\.\(\)]*"  # spaces, nbsp variants, dash, dot, parens
    pattern = r'(?<!\d)' + seps.join(map(re.escape, num)) + r'(?!\d)'
    import re as _re
    safe = html.escape(text)
    return _re.sub(pattern,
                   lambda m: f"<span style='color:{color}; font-weight:bold;'>{m.group(0)}</span>",
                   safe)

# === CALL HISTORY (optional) ===
def parse_calls_from_ini(path: str):
    calls = []
    if not os.path.exists(path):
        log(f"microsip.ini not found at {path} (skipping)")
        return calls
    log(f"Found calls file at {path}, opening...")
    in_calls = False
    raw_seen = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            compact = clean_line(line)
            if not compact:
                continue
            if compact.startswith("[") and compact.endswith("]"):
                sec = compact[1:-1].lower()
                if sec == "calls":
                    in_calls = True
                    continue
                if in_calls:
                    break
            if not in_calls or "=" not in compact:
                continue
            _, val = compact.split("=", 1)
            if not val or val.lower() == "null":
                continue
            raw_seen += 1
            parts = val.split(";")
            if len(parts) < 6:
                continue
            phone_raw, disp, direction, epoch_str, duration, status = parts[:6]
            phone = norm_phone(phone_raw)
            epoch_digits = "".join(ch for ch in epoch_str if ch.isdigit())
            if not epoch_digits:
                continue
            try:
                epoch = int(epoch_digits)
                dt = datetime.fromtimestamp(epoch)
            except Exception:
                continue
            calls.append({
                "phone": phone,
                "disp": disp,
                "direction": direction,
                "epoch": epoch,
                "dt": dt,
                "duration": duration,
                "status": status.strip()
            })
    log(f"Parsed {len(calls)} calls total (raw seen {raw_seen})")
    return calls

def stats_for_number(phone: str, calls: list):
    phone = norm_phone(phone)
    stats, statuses = {}, {}
    direction_map = {"0": "Outgoing", "2": "Incoming", "3": "Missed"}
    today = datetime.now().date()
    week_ago = datetime.now() - timedelta(days=7)

    def norm_status(s: str) -> str:
        s = s.lower()
        if "answer" in s:   return "Answered"
        if "cancel" in s:   return "Canceled"
        if "forbid" in s:   return "Forbidden"
        if "busy" in s:     return "Busy"
        return s.title() if s else "Other"

    for c in calls:
        if not c["phone"].endswith(phone):
            continue
        label = direction_map.get(c["direction"], "Other")
        stats.setdefault(label, {"today": 0, "week": 0, "total": 0})
        stats[label]["total"] += 1
        if c["dt"].date() == today:
            stats[label]["today"] += 1
        if c["dt"] >= week_ago:
            stats[label]["week"] += 1
        st = norm_status(c["status"])
        statuses[st] = statuses.get(st, 0) + 1
    return stats, statuses

# === IMAGINARY DB LOOKUP ===
def fetch_person_by_phone(phone: str):
    info = {
        "customer_id": None,"business_name": None,"sector": None,"program_name": None,
        "vat": None,"email": None,"owner_full": None,"notes": None,
        "tags": [],"services": [],"unpaid_total": 0.0,
    }
    num = norm_phone(phone)
    cid = CONTACTS.get(num)
    if not cid:
        log(f"No customer found for phone {num}")
        return info
    cust = CUSTOMERS.get(cid, {})
    prof = PROFILES.get(cid, {})
    svcs = SERVICES.get(cid, [])
    lbls = LABELS.get(cid, [])
    unpaid = sum((row["amount"] for row in svcs if not row.get("paid", False)), 0.0)
    info.update({
        "customer_id": cid,
        "business_name": cust.get("business_name"),
        "sector": cust.get("sector"),
        "program_name": cust.get("program"),
        "vat": prof.get("vat"),
        "email": prof.get("email"),
        "owner_full": " ".join([prof.get("owner_first",""), prof.get("owner_last","")]).strip(),
        "notes": prof.get("notes"),
        "tags": lbls[:],
        "services": svcs[:],
        "unpaid_total": unpaid,
    })
    log(f"[DEMO] Business: {info['business_name']} | Sector: {info['sector']} | Program: {info['program_name']}")
    log(f"[DEMO] VAT: {info['vat']} | Email: {info['email']} | Owner: {info['owner_full']}")
    for r in info["services"]:
        log(f"[DEMO] Service: {r['desc']} | Amount: {euro(r['amount'])} | Date: {r['date']} | Paid: {'yes' if r['paid'] else 'no'}")
    log(f"[DEMO] Unpaid total: {euro(info['unpaid_total'])}")
    return info

# === MOCK SEARCH + CSV for unknown ===
def ddg_top3_greek(phone: str):
    num = norm_phone(phone)
    return [
        (f"{num} Κατάστημα αρτοποιίας στο Ηράκλειο — στοιχεία επικοινωνίας", "https://example.com/heraklion-bakery"),
        (f"{num} Επιχειρηματικός κατάλογος — καταχώριση τηλεφώνου", "https://example.com/business-directory"),
        (f"{num} Αναζήτηση τηλεφώνου — πιθανός πελάτης", "https://example.com/reverse-lookup"),
    ]

def write_unknown_csv(phone: str, web_results):
    need_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if need_header:
            w.writerow(["timestamp","phone","title1","url1","title2","url2","title3","url3"])
        fixed = (web_results or [])[:3]
        fixed += [("", "")] * (3 - len(fixed))
        row = [datetime.now().isoformat(), norm_phone(phone)]
        for title, url in fixed:
            row.extend([title, url])
        w.writerow(row)
    log(f"[CSV] Logged unknown {phone} -> {CSV_PATH}")

# === AVATAR HELPERS ===
def program_color(name: str) -> QColor:
    hexcol = PROGRAM_COLORS.get(name or "Unknown", PROGRAM_COLORS["Unknown"])
    return QColor(hexcol)

def pixmap_for_program(name: str, size=56) -> QPixmap:
    path = IMG_BY_PROGRAM.get(name or "", "")
    pm = QPixmap(size, size)
    if path and os.path.exists(path):
        pm = QPixmap(path).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    else:
        pm.fill(program_color(name))
    return pm

def pixmap_for_unknown(size=56) -> QPixmap:
    if os.path.exists(IMG_UNKNOWN):
        return QPixmap(IMG_UNKNOWN).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pm = QPixmap(size, size); pm.fill(QColor("#dddddd")); return pm

# === HTML RENDERING ===
def render_tags_html(tags):
    if not tags:
        return ""
    pills = []
    for t in tags:
        name = html.escape(str(t.get("name", "")).strip())
        col  = (t.get("color") or "#f1f1f1").strip()
        pill = (
            f"<span style='display:inline-block; padding:3px 10px; border-radius:14px; "
            f"font-size:{fs(11)}; font-weight:600; border:1px solid #2b2b2b; "
            f"background:{col}; color:#101010;'>&nbsp;{name}&nbsp;</span>"
        )
        pills.append(pill)
    return "&nbsp;".join(pills)

def render_services_table(services):
    if not services:
        return ""
    rows_html = []
    for r in services:
        desc  = html.escape(r["desc"])
        amt   = r["amount"]
        date  = html.escape(r["date"])
        paid  = "yes" if r.get("paid", False) else "no"
        color = "#00cc66" if paid == "yes" else "#ff9900"
        row = (
            "<tr style='line-height:0.95;'>"
            f"<td style='padding:2px 8px 2px 0;'>{desc}</td>"
            f"<td style='padding:2px 0; text-align:right; width:110px; font-weight:700; color:{color};'>{html.escape(euro(amt))}</td>"
            f"<td style='padding:2px 8px; width:110px;'>{date}</td>"
            f"<td style='padding:2px 8px; width:52px;'>{paid}</td>"
            "</tr>"
        )
        rows_html.append(row)

    table = (
        "<table style='border-collapse:collapse; width:100%; font-size:{fsz}; color:#ddd; table-layout:fixed;'>"
        "<thead>"
        "<tr style='line-height:1.05;'>"
        "<th style='text-align:left; padding:2px 8px 2px 0; color:#ffd37a;'>job descr</th>"
        "<th style='text-align:right; padding:2px 0 2px 0; color:#ffd37a;'>euro amount</th>"
        "<th style='text-align:left; padding:2px 8px 2px 8px; color:#ffd37a;'>date</th>"
        "<th style='text-align:left; padding:2px 8px 2px 8px; color:#ffd37a;'>paid</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{''.join(rows_html)}"
        "</tbody>"
        "</table>"
    ).format(fsz=fs(11))
    return table

def render_direction_stats_columns(dir_stats):
    blue  = "#00bfff"
    green = "#00ff00"
    label_colors = {"Outgoing": "#a3ffcc", "Incoming": "#ffffff", "Missed": "#ffaaaa"}
    order = ["Outgoing", "Incoming", "Missed"]
    lines = []
    for label in order:
        d = dir_stats.get(label, {"today": 0, "week": 0, "total": 0})
        lc = label_colors.get(label, "#cccccc")
        lines.append(
            f"<div style='margin:0 0 2px 0;'>"
            f"<span style='color:{lc}; font-size:{fs(11)};'>{label}:</span> "
            f"<span style='color:{blue}; font-size:{fs(11)};'>T</span>"
            f"<span style='color:{green}; font-size:{fs(11)};'> {d.get('today', 0)}</span> "
            f"<span style='color:{blue}; font-size:{fs(11)};'>W</span>"
            f"<span style='color:{green}; font-size:{fs(11)};'> {d.get('week', 0)}</span>"
            f"</div>"
        )
    return "".join(lines)

# === TOAST ===
def show_toast(phone: str, dir_stats: dict, status_stats: dict, web_results=None, person=None):
    app = QApplication(sys.argv)

    flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    toast = QWidget(None, flags)
    toast.setAttribute(Qt.WA_TranslucentBackground)
    toast.setAttribute(Qt.WA_DeleteOnClose, True)
    toast.setObjectName("toast")

    def finish():
        if toast.isVisible():
            toast.close()
        app.quit()

    def open_url_and_quit():
        import webbrowser
        try:
            webbrowser.open(URL)
        finally:
            finish()

    # Card + shadow
    card = QWidget(toast); card.setObjectName("card")
    shadow = QGraphicsDropShadowEffect(blurRadius=22, xOffset=0, yOffset=6)
    shadow.setColor(Qt.black)
    card.setGraphicsEffect(shadow)

    outer = QVBoxLayout(toast); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(card)
    layout = QVBoxLayout(card); layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(8)

    row = QHBoxLayout(); row.setSpacing(10)

    # Avatar: known -> program avatar/color, unknown -> IMG_UNKNOWN
    known = bool(person and person.get("customer_id"))
    avatar = QLabel()
    if known:
        pm = pixmap_for_program((person or {}).get("program_name") or "Unknown", size=56)
    else:
        pm = pixmap_for_unknown(size=56)
    avatar.setPixmap(pm)
    row.addWidget(avatar)

    # Text block
    text_block = QLabel()
    text_block.setTextFormat(Qt.RichText)
    text_block.setWordWrap(True)
    text_block.setMinimumWidth(380)
    text_block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    accent_label = "#ffd37a"

    # Content
    person_html = ""
    if known:
        epon  = person.get("business_name") or ""
        notes = strip_html(person.get("notes") or "")
        notes_short = (notes[:200] + "…") if len(notes) > 200 else notes
        prog  = person.get("program_name") or ""
        sector= person.get("sector") or ""
        vat   = person.get("vat") or ""
        email = person.get("email") or ""
        owner = person.get("owner_full") or ""
        owes  = person.get("unpaid_total") or 0.0

        header_line = f"{html.escape(epon)}"
        if prog:
            header_line += f" <span style='color:#9de39d; font-size:{fs(11)};'>( {html.escape(prog)} )</span>"
        if sector:
            header_line += f" <span style='color:#9ddfff; font-size:{fs(11)};'>[{html.escape(sector)}]</span>"
        header_line += f" <span style='color:#ffb347; font-size:{fs(12)}; font-weight:bold;'> | Owes: {html.escape(euro(owes))}</span>"

        person_html += f"<span style='color:#dbeafe; font-size:18px; font-weight:bold;'>{header_line}</span><br>"

        sub = []
        if owner: sub.append(f"Owner: {html.escape(owner)}")
        if vat:   sub.append(f"VAT: {html.escape(vat)}")
        if email: sub.append(f"Email: {html.escape(email)}")
        if sub:
            person_html += f"<span style='color:#cdd6f4; font-size:{fs(11)};'>{' | '.join(sub)}</span><br>"

        if notes_short:
            person_html += f"<span style='color:{accent_label}; font-size:{fs(12)}; font-weight:bold;'>Note:</span> " \
                           f"<span style='color:#cccccc; font-size:{fs(12)};'>{html.escape(notes_short)}</span><br>"

        tags_html = render_tags_html(person.get("tags") or [])
        if tags_html:
            person_html += f"<div style='margin-top:6px;'>{tags_html}</div>"

        services_html = render_services_table(person.get("services") or [])
        if services_html:
            person_html += f"<div style='margin-top:6px;'>{services_html}</div>"

        right_stats = render_direction_stats_columns(dir_stats or {})
        bottom_html = (
            "<div style='margin-top:6px; display:block;'>"
            f"<div style='color:#ffcc99; font-size:{fs(12)}; font-weight:700;'>Unpaid total: {html.escape(euro(owes))}</div>"
            f"{right_stats}"
            "</div>"
        )
        person_html += bottom_html
    else:
        # Unknown-caller layout
        phone_str = html.escape(phone)
        pill = (f"<span style='display:inline-block; padding:2px 10px; border-radius:12px; "
                "border:1px solid #7efc7e; color:#7efc7e; background:#1a1a1a; "
                f"font-size:{fs(11)}; font-weight:bold;'> Unknown Caller 📞  </span>")
        header_html = (
            f"{pill}&nbsp;&nbsp;"
            f"<span style='color:#00ff99; font-size:18px; font-weight:800; text-shadow:0 0 6px #00ff99;'>"
            f"{phone_str}</span><br>"
        )

        # Web results list with phone highlighting
        web_html = ""
        if web_results:
            items = []
            num = norm_phone(phone)
            for title, _ in web_results:
                t = highlight_phone(title, num, color="lightgreen")
                items.append(f"<li style='margin:2px 0 0 18px; color:#dddddd; font-size:{fs(11)};'>{t}</li>")
            web_html = (
                f"<div style='margin-top:6px;'>"
                f"<div style='color:{accent_label}; font-size:{fs(11)}; font-weight:bold; margin-bottom:2px;'>Web results</div>"
                f"<ul style='margin:0; padding-left:14px;'>{''.join(items)}</ul>"
                f"</div>"
            )
        person_html = header_html + web_html

    text_block.setText(person_html)
    row.addWidget(text_block)
    layout.addLayout(row)
    layout.addStretch(1)

    # Buttons
    btn_row = QHBoxLayout()
    open_btn = QPushButton("Open URL"); open_btn.clicked.connect(open_url_and_quit)
    close_btn = QPushButton("Dismiss");  close_btn.clicked.connect(finish)
    btn_row.addStretch(1); btn_row.addWidget(open_btn); btn_row.addWidget(close_btn)
    layout.addLayout(btn_row)

    toast.setStyleSheet("""
    #card { background:#1f1f1f; border-radius:16px; }
    QPushButton { background:#2b2b2b; color:white; border:1px solid #3a3a3a;
                  padding:6px 12px; border-radius:10px; font-size:13px; }
    QPushButton:hover { background:#343434; }
    QPushButton:pressed { background:#444; }
    """)

    # Height estimate
    rows  = 3 if not known else 0  # unknown header + list space
    if known:
        rows += 5
        if person and person.get("tags"): rows += 1 + (len(person["tags"]) // 3)
        if person and person.get("services"): rows += len(person["services"]) + 2
        rows += 3
    rows += (len(web_results or []) if not known else 0)
    est_height = 43 + rows * 17 + 56
    toast.resize(560, est_height)

    toast.move(bottom_right_pos(toast.size()))
    toast.show()

    QTimer.singleShot(TIMEOUT_MS, finish)
    sys.exit(app.exec())

# === MAIN ===
def main():
    log(f"Launching toast for {PHONE}")
    calls = parse_calls_from_ini(INI_PATH)
    dir_stats, status_stats = stats_for_number(PHONE, calls)

    person = fetch_person_by_phone(PHONE)
    known = bool(person and person.get("customer_id"))

    web_results = None
    if not known:
        web_results = ddg_top3_greek(PHONE)
        write_unknown_csv(PHONE, web_results)

    if not dir_stats and not web_results and not known:
        log("No local stats, no web notes, and no customer match.")

    show_toast(PHONE, dir_stats, status_stats, web_results, person)

if __name__ == "__main__":
    main()
