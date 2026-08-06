"""
Angi Leads Report - Core Library
==================================
Shared metric-computation and HTML-rendering logic for the Angi Leads
report. Used by both generate_angi_report.py (CLI) and streamlit_app.py
(web UI) so the two stay in sync.
"""


import sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import pandas as pd

# =====================================================================
# CONFIG -- edit this section to match your CRM export / definitions
# =====================================================================

# Column names as they appear in the CSV export
COL = {
    "signed": "Contract Signed?",
    "sent_jobnimbus": "Sent to JobNimbus",          # NOTE: export has no "Synced to JobNimbus" column
    "loss_fake_reason": "Loss / Fake Reason",         # NOTE: export combines "Loss Reason" and "Fake Reason" into ONE column
    "refund_status": "Angi Refund Status",
    "final_contract_amount": "Final Contract Amount",
    "lead_cost": "Angi Lead Cost",
    "inspection_completed": "Inspection Completed?",
    "first_engaged_by": "First Engaged By",
    "first_call_by": "1st Call By",
    "third_call_by": "3rd Call By",
    "first_visit_by": "1st Visit By",
    "created": "Created",
}

# Values in "Loss / Fake Reason" that represent an INVALID / FAKE lead
# (i.e. leads you would dispute with Angi for a credit).
# Adjust this set to match how your team actually classifies fake leads.
FAKE_REASONS = {"Wrong Number", "Wrong Address", "No Info"}

# How to group the remaining "Loss / Fake Reason" values into the
# Section 5 loss-reason breakdown. Anything not listed here falls into
# "Other / Unclassified".
LOSS_REASON_GROUPS = {
    "Decided Not to Proceed": {"Decided Not to Move Forward"},
    "Price Too High": {"Price High"},
    "Competitor": {"Hired Competitor"},
    "Ghosted": {"Ghosted"},
    "Never Contacted": {"Never Contacted"},
    "Not Interested": {"Not Intersted", "Not Interested"},
    "Called - No Answer (CNA)": {"CNA"},  # attempted contact, customer never picked up
    "Fake / Invalid Lead": set(FAKE_REASONS),
}

REFUND_STATUS_ORDER = ["Approved", "Under Negotiation", "Requested", "Denied", "Not Requsted"]

YES_VALUES = {"yes"}


# =====================================================================
# Helpers
# =====================================================================

def is_yes(val) -> bool:
    return str(val).strip().lower() in YES_VALUES


def not_empty(val) -> bool:
    return str(val).strip() not in ("", "nan", "None")


def split_reps(val: str):
    """Some rep columns contain multiple comma-separated names, e.g. 'Jayden, Jeremy'."""
    if not not_empty(val):
        return []
    return [p.strip() for p in str(val).split(",") if p.strip()]


def pct(n, d) -> str:
    if not d:
        return "N/A"
    return f"{(n / d) * 100:.1f}%"


def money(n) -> str:
    return f"${n:,.2f}"


# =====================================================================
# Report computation
# =====================================================================

def build_report(df: pd.DataFrame) -> dict:
    total_leads = len(df)

    # ---------- Section 1: Financials ----------
    lead_cost = pd.to_numeric(df[COL["lead_cost"]], errors="coerce").fillna(0)
    contract_amt = pd.to_numeric(df[COL["final_contract_amount"]], errors="coerce")

    gross_spend = lead_cost.sum()

    refund_status = df[COL["refund_status"]].fillna("").str.strip()
    is_refunded = refund_status.eq("Approved")
    total_refunded = lead_cost[is_refunded].sum()
    net_spend = gross_spend - total_refunded  # <-- refunds ARE netted out of spend here

    total_revenue = contract_amt.fillna(0).sum()

    signed_mask = df[COL["signed"]].apply(is_yes)
    signed_count = int(signed_mask.sum())

    roi_gross = ((total_revenue - gross_spend) / gross_spend * 100) if gross_spend else None
    roi_net = ((total_revenue - net_spend) / net_spend * 100) if net_spend else None

    cpl_gross = gross_spend / total_leads if total_leads else None
    cpl_net = net_spend / total_leads if total_leads else None

    cac_gross = gross_spend / signed_count if signed_count else None
    cac_net = net_spend / signed_count if signed_count else None

    avg_deal_size = total_revenue / signed_count if signed_count else None

    section1 = dict(
        total_leads=total_leads,
        gross_spend=gross_spend,
        total_refunded=total_refunded,
        net_spend=net_spend,
        total_revenue=total_revenue,
        signed_count=signed_count,
        roi_gross=roi_gross,
        roi_net=roi_net,
        cpl_gross=cpl_gross,
        cpl_net=cpl_net,
        cac_gross=cac_gross,
        cac_net=cac_net,
        avg_deal_size=avg_deal_size,
    )

    # ---------- Section 2: Lead Quality & Refunds ----------
    reason_col = df[COL["loss_fake_reason"]].fillna("").str.strip()
    fake_mask = reason_col.isin(FAKE_REASONS)
    fake_count = int(fake_mask.sum())

    refund_counts = {status: int((refund_status == status).sum()) for status in REFUND_STATUS_ORDER}
    other_refund_statuses = set(refund_status.unique()) - set(REFUND_STATUS_ORDER) - {""}

    section2 = dict(
        fake_count=fake_count,
        fake_pct=pct(fake_count, total_leads),
        refund_counts=refund_counts,
        other_refund_statuses=sorted(other_refund_statuses),
    )

    # ---------- Section 3: Outreach & Engagement ----------
    engaged_mask = df[COL["first_engaged_by"]].apply(not_empty)
    engaged_count = int(engaged_mask.sum())

    missed_mask = reason_col.eq("Never Contacted")
    missed_count = int(missed_mask.sum())

    # CNA = team attempted a call but the customer never answered (not the same as "Never Contacted")
    cna_count = int(reason_col.eq("CNA").sum())

    called1_count = int(df[COL["first_call_by"]].apply(not_empty).sum())
    called3_count = int(df[COL["third_call_by"]].apply(not_empty).sum())

    visited1_count = int(df[COL["first_visit_by"]].apply(not_empty).sum())

    engaged_reps = Counter()
    for v in df[COL["first_engaged_by"]]:
        for rep in split_reps(v):
            engaged_reps[rep] += 1
    top_performer = engaged_reps.most_common(1)[0] if engaged_reps else (None, 0)

    section3 = dict(
        engaged_count=engaged_count,
        engagement_rate=pct(engaged_count, total_leads),
        missed_count=missed_count,
        cna_count=cna_count,
        called1_count=called1_count,
        called3_count=called3_count,
        visited1_count=visited1_count,
        top_performer=top_performer,
        engaged_reps=engaged_reps.most_common(),
    )

    # ---------- Section 4: Field Ops & Pipeline ----------
    inspections_completed = int(df[COL["inspection_completed"]].apply(is_yes).sum())

    visit_reps = Counter()
    for v in df[COL["first_visit_by"]]:
        for rep in split_reps(v):
            visit_reps[rep] += 1

    ops_sync_count = int(df[COL["sent_jobnimbus"]].apply(is_yes).sum())

    section4 = dict(
        inspections_completed=inspections_completed,
        visit_reps=visit_reps.most_common(),
        ops_sync_count=ops_sync_count,
        has_quoted_amount_field=False,  # not present in this export
    )

    # ---------- Section 5: Conversions & Loss Analysis ----------
    conversion_rate = pct(signed_count, total_leads)
    insp_to_close_rate = pct(signed_count, inspections_completed)

    remaining = Counter(reason_col[reason_col != ""])
    loss_breakdown = {}
    for label, values in LOSS_REASON_GROUPS.items():
        n = sum(remaining.pop(v, 0) for v in values)
        loss_breakdown[label] = n
    # whatever wasn't matched to a group (e.g. "CNA") goes to Other
    other_total = sum(remaining.values())
    loss_breakdown["Other / Unclassified"] = other_total
    other_detail = dict(remaining)

    section5 = dict(
        signed_count=signed_count,
        conversion_rate=conversion_rate,
        insp_to_close_rate=insp_to_close_rate,
        loss_breakdown=loss_breakdown,
        other_detail=other_detail,
    )

    return dict(s1=section1, s2=section2, s3=section3, s4=section4, s5=section5,
                total_leads=total_leads)


# =====================================================================
# HTML rendering
# =====================================================================

def render_html(data: dict, source_file: str, source_url=None) -> str:
    s1, s2, s3, s4, s5 = data["s1"], data["s2"], data["s3"], data["s4"], data["s5"]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    def kpi(label, value, sub=None):
        sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
        return f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>{sub_html}</div>'

    def bar_row(label, n, total):
        p = (n / total * 100) if total else 0
        return f'''<div class="bar-row">
            <div class="bar-label">{label}</div>
            <div class="bar-track"><div class="bar-fill" style="width:{p:.1f}%"></div></div>
            <div class="bar-value">{n} ({p:.1f}%)</div>
        </div>'''

    refund_rows = "".join(
        bar_row(status, n, s1["total_leads"]) for status, n in s2["refund_counts"].items()
    )
    if s2["other_refund_statuses"]:
        refund_rows += "".join(
            bar_row(f'{status} (unmapped)', 0, s1["total_leads"]) for status in s2["other_refund_statuses"]
        )

    loss_rows = "".join(
        bar_row(label, n, s1["total_leads"]) for label, n in s5["loss_breakdown"].items()
    )

    engaged_rep_rows = "".join(
        f"<tr><td>{rep}</td><td>{n}</td></tr>" for rep, n in s3["engaged_reps"]
    ) or "<tr><td colspan='2'>No data</td></tr>"

    visit_rep_rows = "".join(
        f"<tr><td>{rep}</td><td>{n}</td></tr>" for rep, n in s4["visit_reps"]
    ) or "<tr><td colspan='2'>No data</td></tr>"

    other_detail_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in sorted(s5["other_detail"].items(), key=lambda x: -x[1])
    ) or "<tr><td colspan='2'>None</td></tr>"

    top_perf_name, top_perf_n = s3["top_performer"]

    recommendations = build_recommendations(data)
    rec_items = "".join(f"<li>{r}</li>" for r in recommendations)

    if source_url:
        source_line = f'Source data: <a href="{source_url}" target="_blank">{source_file}</a>'
    else:
        source_line = f"Source data: {source_file}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Angi Leads Performance Report</title>
<style>
  :root {{
    --bg: #ffffff; --card: #f7f8fa; --card2: #eef0f4; --text: #1a1f2c; --muted: #5b6478;
    --accent: #ff6b35; --accent2: #c2410c; --green: #16a34a; --red: #dc2626; --line: #e2e5ec;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 40px 24px; background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; }}
  h1 {{ font-size: 26px; margin: 0 0 4px; }}
  .meta {{ color: var(--muted); font-size: 13px; margin-bottom: 32px; }}
  .meta a {{ color: var(--accent2); text-decoration: none; font-weight: 600; }}
  .meta a:hover {{ text-decoration: underline; }}
  h2 {{
    font-size: 16px; text-transform: uppercase; letter-spacing: .06em; color: var(--accent2);
    border-bottom: 1px solid var(--line); padding-bottom: 8px; margin: 40px 0 16px;
  }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
  .kpi {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 16px; }}
  .kpi-label {{ color: var(--muted); font-size: 12px; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 22px; font-weight: 700; }}
  .kpi-sub {{ color: var(--muted); font-size: 11px; margin-top: 4px; }}
  .bar-row {{ display: grid; grid-template-columns: 190px 1fr 110px; align-items: center; gap: 10px; margin: 8px 0; font-size: 13px; }}
  .bar-track {{ background: var(--card2); border-radius: 6px; height: 10px; overflow: hidden; }}
  .bar-fill {{ background: linear-gradient(90deg, var(--accent), var(--accent2)); height: 100%; }}
  .bar-value {{ color: var(--muted); text-align: right; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); }}
  th {{ color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .note {{ background: var(--card2); border-left: 3px solid var(--accent); padding: 10px 14px; border-radius: 6px; font-size: 12.5px; color: var(--muted); margin: 10px 0; }}
  ul.rec {{ padding-left: 20px; }}
  ul.rec li {{ margin: 8px 0; font-size: 14px; }}
  .pos {{ color: var(--green); }} .neg {{ color: var(--red); }}
  @media (max-width: 700px) {{ .two-col {{ grid-template-columns: 1fr; }} .bar-row {{ grid-template-columns: 120px 1fr 90px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Angi Leads Performance Report</h1>
  <div class="meta">{source_line} &middot; Generated {generated_at} &middot; {s1['total_leads']} leads analyzed</div>

  <h2>1. Executive Summary &amp; Financial Overview</h2>
  <div class="kpi-grid">
    {kpi("Total Leads Received", s1['total_leads'])}
    {kpi("Total Angi Spend (Gross)", money(s1['gross_spend']))}
    {kpi("Refunded Amount", money(s1['total_refunded']), "Approved refunds netted out below")}
    {kpi("Net Spend (after refunds)", money(s1['net_spend']))}
    {kpi("Total Generated Revenue", money(s1['total_revenue']), f"{s1['signed_count']} signed contracts")}
    {kpi("ROI (Net Spend)", f"{s1['roi_net']:.1f}%" if s1['roi_net'] is not None else "N/A", f"Gross-spend ROI: {s1['roi_gross']:.1f}%" if s1['roi_gross'] is not None else "")}
    {kpi("Cost Per Lead (Net)", money(s1['cpl_net']) if s1['cpl_net'] is not None else "N/A", f"Gross CPL: {money(s1['cpl_gross'])}" if s1['cpl_gross'] is not None else "")}
    {kpi("Cost Per Acquisition (Net)", money(s1['cac_net']) if s1['cac_net'] is not None else "N/A", f"Gross CAC: {money(s1['cac_gross'])}" if s1['cac_gross'] is not None else "")}
    {kpi("Average Deal Size", money(s1['avg_deal_size']) if s1['avg_deal_size'] is not None else "N/A")}
  </div>
  <div class="note">Refunds are netted out of spend: <b>Net Spend = Gross Spend − Approved Refunds</b>. Both gross and net figures are shown so you can see the impact. Refund amount is assumed equal to the full "Angi Lead Cost" for any lead where Refund Status = Approved.</div>

  <h2>2. Lead Quality &amp; Refund Management</h2>
  <div class="two-col">
    <div>
      <div class="kpi-grid">
        {kpi("Total Invalid / Fake Leads", s2['fake_count'])}
        {kpi("Fake Leads Percentage", s2['fake_pct'])}
      </div>
      <div class="note">Classified as fake using Loss/Fake Reason in: {", ".join(sorted(FAKE_REASONS))}. Adjust FAKE_REASONS in the script if your team defines this differently.</div>
    </div>
    <div>
      <h3 style="font-size:13px;color:var(--muted);margin:0 0 8px;">Refund Pipeline Status</h3>
      {refund_rows}
    </div>
  </div>

  <h2>3. Outreach &amp; Engagement Performance</h2>
  <div class="kpi-grid">
    {kpi("Total Engaged Leads", s3['engaged_count'])}
    {kpi("Lead Engagement Rate", s3['engagement_rate'])}
    {kpi("Missed Opportunities (Never Contacted)", s3['missed_count'])}
    {kpi("Attempted, No Answer (CNA)", s3['cna_count'], "Team called but customer never picked up")}
    {kpi("Called at least 1 Time", s3['called1_count'])}
    {kpi("Called at least 3 Times", s3['called3_count'])}
    {kpi("Visited at least 1 Time", s3['visited1_count'])}
  </div>
  <div class="two-col" style="margin-top:16px;">
    <div>
      <h3 style="font-size:13px;color:var(--muted);">Top Performer (First Engagement): {top_perf_name or "N/A"} ({top_perf_n})</h3>
      <table><tr><th>Rep</th><th>First-Engagement Leads</th></tr>{engaged_rep_rows}</table>
    </div>
  </div>

  <h2>4. Field Operations &amp; Pipeline Metrics</h2>
  <div class="kpi-grid">
    {kpi("Total Inspections Completed", s4['inspections_completed'])}
    {kpi("Operations Sync (Sent to JobNimbus)", s4['ops_sync_count'])}
    {kpi("Total Quoted Value in Pipeline", "N/A")}
  </div>
  <div class="note">"Quoted Amount" is not a column in this export, so pipeline value can't be calculated &mdash; see recommendations below. Also note the export has "Sent to JobNimbus", not "Synced to JobNimbus"; treated as the same metric.</div>
  <table style="margin-top:12px;"><tr><th>Rep (1st Visit)</th><th>Visits</th></tr>{visit_rep_rows}</table>

  <h2>5. Conversions &amp; Loss Analysis</h2>
  <div class="kpi-grid">
    {kpi("Total Signed Contracts", s5['signed_count'])}
    {kpi("Lead-to-Customer Conversion Rate", s5['conversion_rate'])}
    {kpi("Inspection-to-Close Rate", s5['insp_to_close_rate'])}
  </div>
  <h3 style="font-size:13px;color:var(--muted);margin:20px 0 8px;">Loss Reasons Breakdown</h3>
  {loss_rows}
  <div class="note">"Other / Unclassified" breakdown (e.g. CNA &mdash; meaning not confirmed, please clarify with your team):</div>
  <table><tr><th>Raw Reason</th><th>Count</th></tr>{other_detail_rows}</table>

  <h2>Recommendations</h2>
  <ul class="rec">{rec_items}</ul>

</div>
</body>
</html>"""
    return html


def build_recommendations(data: dict) -> list:
    s1, s2, s3, s4, s5 = data["s1"], data["s2"], data["s3"], data["s4"], data["s5"]
    total = data["total_leads"]
    recs = []

    if s5["loss_breakdown"].get("Other / Unclassified", 0) / total > 0.15:
        recs.append(
            "A meaningful share of leads still fall into 'Other / Unclassified' in the loss-reason breakdown. "
            "Review the raw reasons listed in the table below and add any recurring ones to LOSS_REASON_GROUPS so they're categorized correctly."
        )

    cna_share = s3["cna_count"] / total if total else 0
    if cna_share > 0.2:
        recs.append(
            f"'CNA' (called, no answer) is now the single largest loss reason ({s3['cna_count']} of {total} leads, {cna_share*100:.0f}%). "
            "This is a live, contactable lead the team simply couldn't reach by phone — it's worth adding a text/SMS follow-up step or a required voicemail + retry-next-day rule before marking these lost, since they're not fake and not truly 'never contacted'."
        )

    if s4["has_quoted_amount_field"] is False:
        recs.append(
            "Add a 'Quoted Amount' field to the CRM export so this report can track total quoted pipeline value and quote-to-close rate, not just signed contracts."
        )

    if s1["signed_count"] and s1["total_revenue"]:
        pass

    if s1["signed_count"] < 5:
        recs.append(
            "Only a handful of leads in this export have a recorded Final Contract Amount / signed status. "
            "Revenue-based metrics (ROI, CAC, Avg Deal Size) will be volatile until more leads move through the pipeline — treat them as directional, not final, until sample size grows."
        )

    call_drop = s3["called1_count"] - s3["called3_count"]
    if s3["called1_count"] and call_drop / s3["called1_count"] > 0.5:
        recs.append(
            f"Call follow-through drops sharply between the 1st and 3rd attempt ({s3['called1_count']} → {s3['called3_count']}, a "
            f"{call_drop / s3['called1_count'] * 100:.0f}% drop-off). Consider a required 3-call cadence before a lead is marked lost."
        )

    if s2["fake_pct"] not in ("N/A",) and float(s2["fake_pct"].rstrip('%')) > 15:
        recs.append(
            f"Fake/invalid leads are {s2['fake_pct']} of total volume — worth escalating to your Angi account rep as a lead-quality issue, "
            "and worth tracking refund turnaround time (date requested → date approved) as its own metric."
        )

    recs.append(
        "Track a 'Refund Requested Date' and 'Refund Approved Date' to measure average days-to-refund — useful for holding Angi accountable on SLA."
    )
    recs.append(
        "Standardize rep names in the CRM (e.g. 'Harrison' vs 'Harriosn' typo, 'ANR Support Team' vs individual reps) so per-rep leaderboards are accurate."
    )
    recs.append(
        "Add a lead source/channel timestamp-to-first-contact metric (Created → First Engagement Date) to measure speed-to-lead, which is one of the strongest predictors of Angi lead conversion."
    )
    recs.append(
        "Consider a weekly/monthly trend view (this report is a snapshot) so you can see whether CPL, ROI, and fake-lead % are improving or worsening over time — rerun this script on each new export and compare."
    )
    return recs


# =====================================================================
# PDF rendering (pure Python via reportlab — no system dependencies,
# so it works on Streamlit Community Cloud out of the box)
# =====================================================================

def render_pdf(data: dict, source_file: str, source_url=None) -> bytes:
    """Build a downloadable PDF version of the report. Returns raw PDF bytes."""
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, ListFlowable, ListItem
    )

    s1, s2, s3, s4, s5 = data["s1"], data["s2"], data["s3"], data["s4"], data["s5"]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    ACCENT = colors.HexColor("#c2410c")
    MUTED = colors.HexColor("#5b6478")
    LINE = colors.HexColor("#e2e5ec")
    CARD = colors.HexColor("#f7f8fa")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        title="Angi Leads Performance Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], textColor=colors.HexColor("#1a1f2c"), fontSize=20)
    meta_style = ParagraphStyle("MetaX", parent=styles["Normal"], textColor=MUTED, fontSize=9, spaceAfter=14)
    h2_style = ParagraphStyle("H2X", parent=styles["Heading2"], textColor=ACCENT, fontSize=12, spaceBefore=16, spaceAfter=8)
    note_style = ParagraphStyle("NoteX", parent=styles["Normal"], textColor=MUTED, fontSize=8.5, spaceBefore=4, spaceAfter=10, leftIndent=6, borderColor=ACCENT, borderWidth=0)
    body_style = ParagraphStyle("BodyX", parent=styles["Normal"], fontSize=9.5, leading=13)

    story = []
    story.append(Paragraph("Angi Leads Performance Report", title_style))
    if source_url:
        meta_text = f'Source data: <link href="{source_url}" color="#c2410c"><u>{source_file}</u></link> &nbsp;&middot;&nbsp; Generated {generated_at} &middot; {s1["total_leads"]} leads analyzed'
    else:
        meta_text = f'Source data: {source_file} &nbsp;&middot;&nbsp; Generated {generated_at} &middot; {s1["total_leads"]} leads analyzed'
    story.append(Paragraph(meta_text, meta_style))

    def kv_table(rows, col_widths=(6.5 * cm, 5.5 * cm)):
        t = Table([[Paragraph(str(k), body_style), Paragraph(f"<b>{v}</b>", body_style)] for k, v in rows],
                   colWidths=col_widths)
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, LINE),
            ("BACKGROUND", (0, 0), (-1, -1), CARD),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return t

    def bar_table(rows, total):
        # rows: list of (label, count)
        tdata = [["Category", "Count", "% of total"]]
        for label, n in rows:
            p = f"{(n / total * 100):.1f}%" if total else "N/A"
            tdata.append([label, str(n), p])
        t = Table(tdata, colWidths=(7 * cm, 2.5 * cm, 2.5 * cm))
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, LINE),
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    # ---- Section 1 ----
    story.append(Paragraph("1. Executive Summary &amp; Financial Overview", h2_style))
    story.append(kv_table([
        ("Total Leads Received", s1["total_leads"]),
        ("Total Angi Spend (Gross)", money(s1["gross_spend"])),
        ("Refunded Amount", money(s1["total_refunded"])),
        ("Net Spend (after refunds)", money(s1["net_spend"])),
        ("Total Generated Revenue", money(s1["total_revenue"])),
        ("ROI (Net Spend)", f"{s1['roi_net']:.1f}%" if s1["roi_net"] is not None else "N/A"),
        ("ROI (Gross Spend)", f"{s1['roi_gross']:.1f}%" if s1["roi_gross"] is not None else "N/A"),
        ("Cost Per Lead (Net)", money(s1["cpl_net"]) if s1["cpl_net"] is not None else "N/A"),
        ("Cost Per Acquisition (Net)", money(s1["cac_net"]) if s1["cac_net"] is not None else "N/A"),
        ("Average Deal Size", money(s1["avg_deal_size"]) if s1["avg_deal_size"] is not None else "N/A"),
    ]))
    story.append(Paragraph(
        "Net Spend = Gross Spend − Approved Refunds. Approved refunds assume the full Angi Lead Cost was credited back.",
        note_style))

    # ---- Section 2 ----
    story.append(Paragraph("2. Lead Quality &amp; Refund Management", h2_style))
    story.append(kv_table([
        ("Total Invalid / Fake Leads", s2["fake_count"]),
        ("Fake Leads Percentage", s2["fake_pct"]),
    ]))
    story.append(Spacer(1, 8))
    story.append(bar_table(list(s2["refund_counts"].items()), s1["total_leads"]))

    # ---- Section 3 ----
    story.append(Paragraph("3. Outreach &amp; Engagement Performance", h2_style))
    story.append(kv_table([
        ("Total Engaged Leads", s3["engaged_count"]),
        ("Lead Engagement Rate", s3["engagement_rate"]),
        ("Missed Opportunities (Never Contacted)", s3["missed_count"]),
        ("Attempted, No Answer (CNA)", s3["cna_count"]),
        ("Called at least 1 Time", s3["called1_count"]),
        ("Called at least 3 Times", s3["called3_count"]),
        ("Visited at least 1 Time", s3["visited1_count"]),
    ]))
    top_name, top_n = s3["top_performer"]
    story.append(Paragraph(f"Top Performer (First Engagement): <b>{top_name or 'N/A'}</b> ({top_n})", body_style))
    if s3["engaged_reps"]:
        story.append(Spacer(1, 6))
        story.append(bar_table(s3["engaged_reps"], s1["total_leads"]))

    # ---- Section 4 ----
    story.append(Paragraph("4. Field Operations &amp; Pipeline Metrics", h2_style))
    story.append(kv_table([
        ("Total Inspections Completed", s4["inspections_completed"]),
        ("Operations Sync (Sent to JobNimbus)", s4["ops_sync_count"]),
        ("Total Quoted Value in Pipeline", "N/A"),
    ]))
    if s4["visit_reps"]:
        story.append(Spacer(1, 8))
        story.append(bar_table(s4["visit_reps"], s1["total_leads"]))
    story.append(Paragraph(
        "\u201cQuoted Amount\u201d is not a column in this export, so pipeline value can't be calculated.",
        note_style))

    # ---- Section 5 ----
    story.append(Paragraph("5. Conversions &amp; Loss Analysis", h2_style))
    story.append(kv_table([
        ("Total Signed Contracts", s5["signed_count"]),
        ("Lead-to-Customer Conversion Rate", s5["conversion_rate"]),
        ("Inspection-to-Close Rate", s5["insp_to_close_rate"]),
    ]))
    story.append(Spacer(1, 8))
    story.append(bar_table(list(s5["loss_breakdown"].items()), s1["total_leads"]))

    # ---- Recommendations ----
    story.append(Paragraph("Recommendations", h2_style))
    recs = build_recommendations(data)
    story.append(ListFlowable(
        [ListItem(Paragraph(r, body_style), spaceBefore=4) for r in recs],
        bulletType="bullet",
    ))

    doc.build(story)
    return buf.getvalue()
