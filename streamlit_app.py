"""
Angi Leads Report - Streamlit App
==================================
Upload an Angi Leads CRM export (CSV) and get an interactive performance
report: financials, lead quality/refunds, outreach, field ops, and
conversions - plus a downloadable HTML version.

Deploy on Streamlit Community Cloud pointing at this file
(`streamlit_app.py`) as the entry point.
"""

import streamlit as st
import pandas as pd

from angi_report_lib import COL, build_report, render_html, render_pdf, money, pct

st.set_page_config(page_title="Angi Leads Report", page_icon="📊", layout="wide")

st.title("📊 Angi Leads Performance Report")
st.caption("Upload your Angi Leads CRM export (CSV) to generate the report.")

uploaded = st.file_uploader("Angi Leads export (CSV or Excel)", type=["csv", "xlsx", "xls"])

if uploaded is None:
    st.info("Upload a CSV or Excel file exported from your CRM (e.g. 'Export_Contacts_Angi_Leads_*.csv') to get started.")
    st.stop()

try:
    if uploaded.name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded, dtype=str)
    else:
        df = pd.read_csv(uploaded, encoding="utf-8-sig", dtype=str)
except Exception as e:
    st.error(f"Couldn't read this file: {e}")
    st.stop()

missing = [name for name in COL.values() if name not in df.columns]
if missing:
    st.warning(
        "The following expected columns are missing from this CSV, so related metrics will show as N/A: "
        + ", ".join(missing)
    )

data = build_report(df)
s1, s2, s3, s4, s5 = data["s1"], data["s2"], data["s3"], data["s4"], data["s5"]

# ---------------------------------------------------------------- Section 1
st.header("1. Executive Summary & Financial Overview")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Leads", s1["total_leads"])
c2.metric("Gross Spend", money(s1["gross_spend"]))
c3.metric("Refunded", money(s1["total_refunded"]))
c4.metric("Net Spend", money(s1["net_spend"]))

c5, c6, c7, c8 = st.columns(4)
c5.metric("Total Potential Revenue (Signed Contracts)", money(s1["total_revenue"]),
          help="Sum of Final Contract Amount for signed contracts — not guaranteed until payment is actually collected.")
c6.metric("Return on Investment (ROI) — Net Spend", f"{s1['roi_net']:.1f}%" if s1["roi_net"] is not None else "N/A",
          help="(Revenue − Spend) / Spend × 100" + (f" · Gross-spend ROI: {s1['roi_gross']:.1f}%" if s1["roi_gross"] is not None else ""))
c7.metric("Cost Per Lead (CPL) — Net", money(s1["cpl_net"]) if s1["cpl_net"] is not None else "N/A",
          help="Spend / Total Leads")
c8.metric("Cost Per Acquisition (CAC) — Net", money(s1["cac_net"]) if s1["cac_net"] is not None else "N/A",
          help="Spend / Total Signed Contracts")

st.metric("Average Deal Size", money(s1["avg_deal_size"]) if s1["avg_deal_size"] is not None else "N/A",
          help="Total Revenue / Total Signed Contracts")
st.caption(
    "Net Spend = Gross Spend − Approved Refunds. Approved refunds assume the full Angi Lead Cost was credited back. "
    "\"Total Potential Revenue\" reflects signed contract value, not confirmed/collected payment."
)

# ---------------------------------------------------------------- Section 2
st.header("2. Lead Quality & Refund Management")
col_a, col_b = st.columns(2)
with col_a:
    st.metric("Total Invalid / Fake Leads", s2["fake_count"])
    st.metric("Fake Leads Percentage", s2["fake_pct"])
with col_b:
    st.subheader("Refund Pipeline Status")
    refund_df = pd.DataFrame(
        {"Status": list(s2["refund_counts"].keys()), "Count": list(s2["refund_counts"].values())}
    )
    st.bar_chart(refund_df.set_index("Status"))

# ---------------------------------------------------------------- Section 3
st.header("3. Outreach & Engagement Performance")
c1, c2, c3 = st.columns(3)
c1.metric("Total Engaged Leads", s3["engaged_count"])
c2.metric("Lead Engagement Rate", s3["engagement_rate"])
c3.metric("Missed Opportunities (Never Contacted)", s3["missed_count"])

c4, c5, c6 = st.columns(3)
c4.metric("Attempted, No Answer (CNA)", s3["cna_count"])
c5.metric("Called at least 1 Time", s3["called1_count"])
c6.metric("Called at least 3 Times", s3["called3_count"])

st.metric("Visited at least 1 Time", s3["visited1_count"])

top_name, top_n = s3["top_performer"]
st.subheader(f"Top Performer (First Engagement): {top_name or 'N/A'} ({top_n})")
if s3["engaged_reps"]:
    st.dataframe(pd.DataFrame(s3["engaged_reps"], columns=["Rep", "First-Engagement Leads"]),
                 use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Section 4
st.header("4. Field Operations & Pipeline Metrics")
c1, c2, c3 = st.columns(3)
c1.metric("Total Inspections Completed", s4["inspections_completed"])
c2.metric("Operations Sync (Sent to JobNimbus)", s4["ops_sync_count"])
c3.metric("Total Quoted Value in Pipeline", "N/A", help="No 'Quoted Amount' column in this export")

if s4["visit_reps"]:
    st.subheader("Inspections by Rep (1st Visit)")
    st.dataframe(pd.DataFrame(s4["visit_reps"], columns=["Rep", "Visits"]),
                 use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Section 5
st.header("5. Conversions & Loss Analysis")
c1, c2, c3 = st.columns(3)
c1.metric("Total Signed Contracts", s5["signed_count"])
c2.metric("Lead-to-Customer Conversion Rate", s5["conversion_rate"])
c3.metric("Inspection-to-Close Rate", s5["insp_to_close_rate"])

st.subheader("Loss Reasons Breakdown")
loss_df = pd.DataFrame(
    {"Reason": list(s5["loss_breakdown"].keys()), "Count": list(s5["loss_breakdown"].values())}
)
st.bar_chart(loss_df.set_index("Reason"))

if s5["other_detail"]:
    with st.expander("Other / Unclassified detail"):
        st.dataframe(pd.DataFrame(sorted(s5["other_detail"].items(), key=lambda x: -x[1]),
                                   columns=["Raw Reason", "Count"]),
                     use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Download
st.header("Download")
st.caption(
    "Streamlit apps don't keep a permanent public URL for an uploaded file, so instead of a broken "
    "link, the original CSV is bundled here as its own download — it always travels with the report."
)

source_bytes = uploaded.getvalue()
html = render_html(data, uploaded.name)
pdf_bytes = render_pdf(data, uploaded.name)

d1, d2, d3 = st.columns(3)
with d1:
    st.download_button(
        "⬇️ HTML report",
        data=html,
        file_name="angi_report.html",
        mime="text/html",
        use_container_width=True,
    )
with d2:
    st.download_button(
        "⬇️ PDF report",
        data=pdf_bytes,
        file_name="angi_report.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
with d3:
    name_lower = uploaded.name.lower()
    if name_lower.endswith(".xlsx"):
        source_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif name_lower.endswith(".xls"):
        source_mime = "application/vnd.ms-excel"
    else:
        source_mime = "text/csv"
    st.download_button(
        f"⬇️ Source data ({uploaded.name})",
        data=source_bytes,
        file_name=uploaded.name,
        mime=source_mime,
        use_container_width=True,
    )
