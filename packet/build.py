"""The evidence packet: templated narrative + verified exhibits, rendered
to print-ready HTML. Exhibit sections are keyed to Razorpay's contest-API
evidence slots (shipping_proof, customer_communication, ...) so the swap
to the live Disputes API is a payload mapping, not a rewrite.

  python -m packet.build disp_0015
"""
import datetime as dt
import json
import pathlib
import sys

from jinja2 import Template

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import db  # noqa: E402
from engine.checklists import completeness  # noqa: E402
from engine.contradictions import CACHE_DIR  # noqa: E402
from engine.retrieve import case_file  # noqa: E402

OUT_DIR = pathlib.Path("data/out/packets")

NARRATIVE = {
    "RC-FRAUD": ("The cardholder claims this transaction was unauthorized. "
                 "The payment was completed with successful two-factor "
                 "authentication (OTP) as mandated by RBI, from a device "
                 "previously associated with this customer's account, which "
                 "holds {prior} prior undisputed orders. Under liability-"
                 "shift rules for authenticated transactions, and given the "
                 "customer communications cited below, the merchant "
                 "respectfully contests this dispute."),
    "RC-INR": ("The cardholder claims the item was not received. Carrier "
               "records show the shipment as {ship_status}, with proof of "
               "delivery on file and the delivery address matching the "
               "order. The customer's own support messages, cited below, "
               "acknowledge receipt. The merchant respectfully contests "
               "this dispute."),
    "RC-NAD": ("The cardholder claims the item was not as described. The "
               "fulfilled item matches the listing, and the merchant "
               "offered a return/exchange in support chat prior to this "
               "dispute. The merchant respectfully contests this dispute."),
    "RC-DUP": ("The cardholder claims a duplicate charge. Payment records "
               "show two distinct orders with separate contents placed by "
               "this customer, each fulfilled independently. The merchant "
               "respectfully contests this dispute."),
}

TEMPLATE = Template("""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Representment · {{ d.id }}</title><style>
body{font-family:Georgia,serif;background:#FBFAF6;color:#1B1815;
     max-width:820px;margin:0 auto;padding:48px 32px;line-height:1.55}
h1{font-size:26px;margin:0 0 2px} h2{font-size:15px;letter-spacing:.12em;
   text-transform:uppercase;color:#9C7A1C;border-bottom:1px solid #E2DCCC;
   padding-bottom:6px;margin-top:34px}
.meta{color:#6F6857;font-size:13px;margin-bottom:22px}
.verdict{display:inline-block;padding:4px 14px;border-radius:99px;
  font-weight:bold;background:#F6E9E5;color:#A63D2F;border:1px solid #A63D2F}
table{width:100%;border-collapse:collapse;font-size:14px;margin:10px 0}
td,th{padding:7px 10px;border-bottom:1px solid #E2DCCC;text-align:left}
blockquote{background:#F7F0DC;border:1px solid #E8DCB4;border-radius:8px;
  padding:12px 16px;margin:10px 0;font-style:italic}
.tag{font-size:11px;color:#9C7A1C;letter-spacing:.08em;text-transform:uppercase}
.slot{font-family:monospace;font-size:12px;color:#6F6857}
footer{margin-top:40px;border-top:1px solid #1B1815;padding-top:10px;
  font-size:12px;color:#6F6857}
@media print{body{padding:0}}
</style></head><body>
<h1>Chargeback Representment</h1>
<div class="meta">{{ d.id }} · payment {{ d.payment_id }} ·
{{ d.reason_code }} — {{ d.reason_description }} ·
Rs {{ "%.2f"|format(d.amount/100) }} · respond by {{ respond_by }}</div>
<span class="verdict">RECOMMENDATION: {{ verdict }}{% if p %} ·
p(win) {{ "%.2f"|format(p) }} · EV Rs {{ "{:,.0f}".format(ev/100) }}{% endif %}
</span>

<h2>Merchant statement <span class="slot">explanation_letter</span></h2>
<p>{{ narrative }}</p>

<h2>Authentication record <span class="slot">access_activity_log</span></h2>
<table><tr><th>OTP</th><th>3DS</th><th>Device</th><th>Known device</th>
<th>Prior undisputed orders</th></tr>
<tr><td>{{ auth.otp_result }}</td><td>{{ auth.three_ds_result }}</td>
<td>{{ auth.device_id }}</td><td>{{ "yes" if auth.device_known else "no" }}</td>
<td>{{ prior }}</td></tr></table>

{% if ship %}
<h2>Delivery record <span class="slot">shipping_proof · proof_of_service</span></h2>
<table><tr><th>Carrier</th><th>Status</th><th>POD</th><th>Address match</th>
<th>Events</th></tr>
<tr><td>{{ ship.carrier }}</td><td>{{ ship.status }}</td>
<td>{{ ship.pod_url or "—" }}</td>
<td>{{ "yes" if ship.address_match else "no" }}</td>
<td>{{ ship.events|join(" → ") }}</td></tr></table>
{% endif %}

<h2>Customer communications <span class="slot">customer_communication</span></h2>
{% if exhibits %}{% for e in exhibits %}
<blockquote>“{{ e.quote }}”<br>
<span class="tag">{{ e.type }} · {{ e.source }} · {{ e.when }}</span><br>
<small>{{ e.explanation }}</small></blockquote>
{% endfor %}{% else %}<p>No contradicting statements were identified in
support transcripts.</p>{% endif %}

<h2>Evidence completeness</h2>
<table><tr><th>Check</th><th>Weight</th><th>Present</th></tr>
{% for b in breakdown %}<tr><td>{{ b.check }}</td><td>{{ b.weight }}</td>
<td>{{ "PASS" if b.passed else "—" }}</td></tr>{% endfor %}</table>
<p>Completeness score: <b>{{ c }}</b></p>

<footer>Generated by Parry · every underlying record and this packet's
creation are entered in an append-only, hash-chained audit log ·
submission simulated for Razorpay Buildathon Track 02</footer>
</body></html>""")


def _when(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%d %b %Y, %H:%M")


def build(con, dispute_id):
    cf = case_file(con, dispute_id)
    d = cf["dispute"]
    c, breakdown = completeness(cf)
    dec = con.execute("SELECT verdict, p_win, ev_paise FROM decisions "
                      "WHERE dispute_id=?", (dispute_id,)).fetchone()
    verdict, p, ev = (dec if dec else ("UNDECIDED", None, None))
    cache = CACHE_DIR / f"{dispute_id}.json"
    exhibits = []
    if cache.exists():
        for e in json.loads(cache.read_text()).get("exhibits", []):
            e = dict(e)
            e["when"] = _when(e["ts"])
            exhibits.append(e)
    narrative = NARRATIVE[d["reason_code"]].format(
        prior=cf["customer"]["prior_orders"],
        ship_status=(cf["shipment"] or {}).get("status", "unavailable"))
    html = TEMPLATE.render(
        d=d, verdict=verdict, p=p, ev=ev, narrative=narrative,
        auth=cf["auth"], ship=cf["shipment"],
        prior=cf["customer"]["prior_orders"], exhibits=exhibits,
        breakdown=breakdown, c=c, respond_by=_when(d["respond_by"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{dispute_id}.html"
    path.write_text(html)
    return path


if __name__ == "__main__":
    con = db.connect()
    print(build(con, sys.argv[1]))
