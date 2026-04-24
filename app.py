import io
import os
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ===== CONFIG =====
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1c27MnpzjFIJrL5q6rn_PjS50KdFBxhXX2xzjIxqTDxs/edit?gid=602481885#gid=602481885"
SHEET_VIEW_URL = "https://docs.google.com/spreadsheets/d/1c27MnpzjFIJrL5q6rn_PjS50KdFBxhXX2xzjIxqTDxs/edit#gid=602481885"

GROUP_COL = "Group number for which you are reporting a bug"
TYPE_COL = "Type of bug"
STATUS_COL = "Demonstrate Impact of the bug.1"
NAME_COL = "Name"
EMAIL_COL = "Email Address"
ROLL_COL = "Roll No."
CATEGORY_COL = "Category of Attack"
REBUTTAL_COL = "Rebuttal"
COMMENTS_COL = "Comments"

REFRESH_INTERVAL = 30
BLANK_TEXT_TOKENS = {"", "-", "--", "na", "n/a", "nan", "none", "null", "nil"}
TIMESTAMP_PRIORITY = ["Timestamp", "Submission Timestamp", "Submitted At", "Created At"]
TIMESTAMP_HINTS = ("timestamp", "time", "date", "submitted", "created")

ACTION_LABELS = {
    "Pending Validation": "is_pending_validation",
    "Needs Reviewer Comment": "needs_reviewer_reply",
    "Needs Student Rebuttal": "needs_student_reply",
}


def get_csv_url():
    if "CSV_URL" in st.secrets:
        return st.secrets["CSV_URL"]
    return os.getenv("CSV_URL", DEFAULT_SHEET_URL)


CSV_URL = get_csv_url()


def build_sheet_url_candidates(raw_url):
    source = str(raw_url).strip()
    if not source:
        return []

    if "docs.google.com/spreadsheets/d/" not in source:
        return [source]

    try:
        parsed = urlparse(source)
        parts = [p for p in parsed.path.split("/") if p]
        sid = parts[parts.index("d") + 1] if "d" in parts else None
    except Exception:
        sid = None

    if not sid:
        return [source]

    query = parse_qs(parsed.query)
    fragment_params = parse_qs(parsed.fragment)
    gid = (
        (query.get("gid") or [None])[0]
        or (fragment_params.get("gid") or [None])[0]
        or "0"
    )

    candidates = [
        source,
        f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sid}/pub?gid={gid}&single=true&output=csv",
    ]

    # Remove duplicates while preserving order.
    seen = set()
    deduped = []
    for url in candidates:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped

# ===== Page Setup =====
st.set_page_config(page_title="Bug Dashboard", page_icon="🐞", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { font-family: 'Inter', sans-serif; }

.stApp {
    background: #111827;
}
.block-container {
    padding-top: 1rem;
    max-width: 1400px;
}

/* Title */
h1 {
    text-align: center;
    font-size: 2.2rem !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg, #c4b5fd 0%, #a78bfa 50%, #818cf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem !important;
}
h3 {
    color: #e0d4ff !important;
    font-weight: 600 !important;
    margin-top: 1.5rem !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    justify-content: center;
    gap: 6px;
    border-bottom: 1px solid #1e1e30;
    padding-bottom: 6px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #9ca3c0;
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-weight: 600;
    font-size: 0.95rem;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: #fff !important;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0f0f1a;
    border-right: 1px solid #1e1e30;
}

/* Metrics */
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, #1e2335, #252d42);
    border: 1px solid #374160;
    border-radius: 14px;
    padding: 18px 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    text-align: center;
}
div[data-testid="stMetric"] label {
    color: #b0b8d0 !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
}

/* Group cards */
.group-card {
    background: linear-gradient(145deg, #1e2335, #252d42);
    border: 1px solid #374160;
    border-radius: 14px;
    padding: 12px 8px 8px 8px;
    text-align: center;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    transition: border-color 0.2s, box-shadow 0.2s;
}
.group-card:hover {
    border-color: #818cf8;
    box-shadow: 0 8px 30px rgba(99, 102, 241, 0.2);
}
.group-label {
    color: #e0d4ff;
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 2px;
}
.group-sub {
    color: #9ca3c0;
    font-size: 0.75rem;
    margin-top: 2px;
}

/* Legend */
.legend-row {
    display: flex;
    justify-content: center;
    gap: 28px;
    margin: 8px 0 12px 0;
}
.legend-item {
    display: flex; align-items: center; gap: 6px;
    color: #c8cfe0; font-size: 0.85rem; font-weight: 600;
}
.legend-dot {
    width: 10px; height: 10px; border-radius: 50%; display: inline-block;
}

/* DataFrame */
.stDataFrame { border-radius: 12px; overflow: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

refresh_count = st_autorefresh(interval=REFRESH_INTERVAL * 1000, key="refresh")
st.title("🐞 Bug Validation Dashboard")

st.markdown(
    """
<div class="legend-row">
    <span class="legend-item"><span class="legend-dot" style="background:#22c55e"></span> Valid</span>
    <span class="legend-item"><span class="legend-dot" style="background:#ef4444"></span> Invalid</span>
    <span class="legend-item"><span class="legend-dot" style="background:#334155; border: 1px solid #64748b"></span> Pending</span>
</div>
""",
    unsafe_allow_html=True,
)


# ===== Helpers =====
def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def has_meaningful_text_series(series):
    cleaned = series.fillna("").astype(str).str.strip().str.lower()
    return ~cleaned.isin(BLANK_TEXT_TOKENS)


def classify_status(value):
    s = clean_text(value).lower()
    if s == "valid":
        return "valid"
    if s == "invalid":
        return "invalid"
    return "pending"


def classify_bug_type_series(series):
    cleaned = series.fillna("").astype(str).str.lower().str.strip()
    result = pd.Series("other", index=series.index, dtype="object")
    result.loc[cleaned.str.contains("function", na=False)] = "functionality"
    result.loc[cleaned.str.contains("security", na=False)] = "security"
    return result


def apply_bug_type_filter(data, bug_type_filter):
    if bug_type_filter == "All":
        return data
    if bug_type_filter == "Security":
        return data[data["bug_type"] == "security"]
    return data[data["bug_type"] == "functionality"]


def apply_discussion_filter(data, discussion_filter):
    if discussion_filter == "All":
        return data
    if discussion_filter == "Both rebuttal and comments":
        return data[data["has_discussion"]]
    if discussion_filter == "Waiting reviewer comment":
        return data[data["needs_reviewer_reply"]]
    if discussion_filter == "Waiting student rebuttal":
        return data[data["needs_student_reply"]]
    return data[(~data["has_rebuttal"]) & (~data["has_comment"])]


def apply_action_filters(data, selected_actions):
    if not selected_actions:
        return data.iloc[0:0]
    mask = pd.Series(False, index=data.index)
    for action_label in selected_actions:
        col = ACTION_LABELS[action_label]
        mask = mask | data[col]
    return data[mask]


def sort_group_values(values):
    cleaned = pd.Series(values).dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""].unique().tolist()

    def key_func(val):
        num = pd.to_numeric(val, errors="coerce")
        if pd.notna(num):
            return (0, float(num), val.lower())
        return (1, val.lower())

    return sorted(cleaned, key=key_func)


def status_counts(data):
    return (
        int((data["status"] == "valid").sum()),
        int((data["status"] == "invalid").sum()),
        int((data["status"] == "pending").sum()),
    )


def acceptance_rate(valid, invalid):
    evaluated = valid + invalid
    if evaluated == 0:
        return 0.0, 0
    return round(valid / evaluated * 100, 1), evaluated


def discussion_counts(data):
    return {
        "Both Present": int(data["has_discussion"].sum()),
        "Need Reviewer": int(data["needs_reviewer_reply"].sum()),
        "Need Student": int(data["needs_student_reply"].sum()),
        "No Text": int(((~data["has_rebuttal"]) & (~data["has_comment"])).sum()),
    }


def render_status_metrics(data):
    total = len(data)
    valid, invalid, pending = status_counts(data)
    hit_rate = round(valid / total * 100, 1) if total > 0 else 0
    acceptance_pct, evaluated = acceptance_rate(valid, invalid)

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("🐛 Total", total)
    m2.metric("✅ Valid", valid)
    m3.metric("❌ Invalid", invalid)
    m4.metric("⏳ Pending", pending)
    m5.metric("🎯 Hit Rate", f"{hit_rate}%")
    m6.metric("🧪 Acceptance Rate", f"{acceptance_pct}%")


def render_discussion_metrics(data):
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("📝 Rebuttal Text", int(data["has_rebuttal"].sum()))
    d2.metric("💬 Comment Text", int(data["has_comment"].sum()))
    d3.metric("🤝 Both Present", int(data["has_discussion"].sum()))
    d4.metric("⏱️ Need Reviewer", int(data["needs_reviewer_reply"].sum()))
    d5.metric("⏱️ Need Student", int(data["needs_student_reply"].sum()))


def render_action_metrics(data):
    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("⚡ Actionable Rows", int(data["is_actionable"].sum()))
    a2.metric("⏳ Pending Validation", int(data["is_pending_validation"].sum()))
    a3.metric("🧑‍🏫 Need Reviewer", int(data["needs_reviewer_reply"].sum()))
    a4.metric("🎓 Need Student", int(data["needs_student_reply"].sum()))
    critical = int(data["SLA Band"].astype(str).str.contains("Critical", case=False, na=False).sum())
    a5.metric("🚨 Critical Aging", critical)


def discussion_state_label(value):
    mapping = {
        "both": "🤝 Both Present",
        "waiting_reviewer": "⏱️ Need Reviewer",
        "waiting_student": "⏱️ Need Student",
        "none": "No text",
    }
    return mapping.get(value, "No text")


def status_donut(valid, invalid, pending, title="", height=190):
    custom_text = []
    for label, val in [("Valid", valid), ("Invalid", invalid), ("Pending", pending)]:
        if val > 0 and label != "Pending":
            custom_text.append(str(val))
        else:
            custom_text.append("")

    fig = go.Figure(
        go.Pie(
            labels=["Valid", "Invalid", "Pending"],
            values=[valid, invalid, pending],
            hole=0.6,
            marker=dict(
                colors=["#22c55e", "#ef4444", "#334155"],
                line=dict(color="#111827", width=2),
            ),
            text=custom_text,
            textinfo="text",
            textfont=dict(size=13, color="#ffffff", family="Inter"),
            textposition="inside",
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
            sort=False,
        )
    )

    if pending > 0:
        center_text = f"<b>{pending}</b><br><span style='font-size:10px;color:#94a3b8'>left</span>"
    else:
        center_text = "<b>✓</b><br><span style='font-size:10px;color:#22c55e'>done</span>"

    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color="#c8cfe0"), x=0.5, xanchor="center", y=0.97),
        annotations=[
            dict(
                text=center_text,
                x=0.5,
                y=0.5,
                font_size=18,
                font_color="#f1f5f9",
                font_family="Inter",
                showarrow=False,
            )
        ],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(t=28, b=0, l=0, r=0),
        height=height,
    )
    return fig


def acceptance_donut(valid, invalid, title="Acceptance", height=190):
    acceptance_pct, evaluated = acceptance_rate(valid, invalid)
    if evaluated == 0:
        labels = ["No Evaluated Bugs"]
        values = [1]
        colors = ["#475569"]
        center_text = "<b>0%</b><br><span style='font-size:10px;color:#94a3b8'>0 evaluated</span>"
    else:
        labels = ["Valid", "Invalid"]
        values = [valid, invalid]
        colors = ["#22c55e", "#ef4444"]
        center_text = (
            f"<b>{acceptance_pct}%</b><br>"
            f"<span style='font-size:10px;color:#94a3b8'>{valid}/{evaluated}</span>"
        )

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.58,
            marker=dict(colors=colors, line=dict(color="#111827", width=2)),
            textinfo="value",
            textfont=dict(size=12, color="#ffffff", family="Inter"),
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
            sort=False,
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color="#c8cfe0"), x=0.5, xanchor="center", y=0.97),
        annotations=[
            dict(
                text=center_text,
                x=0.5,
                y=0.5,
                font_size=16,
                font_color="#f1f5f9",
                font_family="Inter",
                showarrow=False,
            )
        ],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(t=28, b=0, l=0, r=0),
        height=height,
    )
    return fig


def generic_donut(labels, values, colors, title="", height=190):
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.58,
            marker=dict(colors=colors, line=dict(color="#111827", width=2)),
            textinfo="value",
            textfont=dict(size=12, color="#ffffff", family="Inter"),
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
            sort=False,
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color="#c8cfe0"), x=0.5, xanchor="center", y=0.97),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(t=28, b=0, l=0, r=0),
        height=height,
    )
    return fig


def discussion_donut(data, title="Discussion", height=190):
    counts = discussion_counts(data)
    labels = ["Both", "Need Reviewer", "Need Student", "No Text"]
    values = [
        counts["Both Present"],
        counts["Need Reviewer"],
        counts["Need Student"],
        counts["No Text"],
    ]
    colors = ["#22c55e", "#f59e0b", "#0ea5e9", "#475569"]
    return generic_donut(labels, values, colors, title=title, height=height)


def queue_donut(data, title="Queue Mix", height=210):
    labels = ["Pending Validation", "Needs Reviewer", "Needs Student"]
    values = [
        int(data["is_pending_validation"].sum()),
        int(data["needs_reviewer_reply"].sum()),
        int(data["needs_student_reply"].sum()),
    ]
    colors = ["#334155", "#f59e0b", "#0ea5e9"]
    return generic_donut(labels, values, colors, title=title, height=height)


def sla_donut(data, title="SLA Mix", height=210):
    order = ["Critical (7d+)", "Aging (3d+)", "Watchlist (1d+)", "Fresh (<1d)"]
    if data["age_mode"].eq("relative").any():
        order = ["Critical (oldest 10%)", "Watchlist (oldest 25%)", "Recent"]

    counts = data["SLA Band"].value_counts()
    labels = [lbl for lbl in order if lbl in counts.index]
    if not labels:
        labels = counts.index.tolist()
    values = [int(counts.get(lbl, 0)) for lbl in labels]

    color_map = {
        "Critical (7d+)": "#ef4444",
        "Aging (3d+)": "#f97316",
        "Watchlist (1d+)": "#f59e0b",
        "Fresh (<1d)": "#22c55e",
        "Critical (oldest 10%)": "#ef4444",
        "Watchlist (oldest 25%)": "#f59e0b",
        "Recent": "#22c55e",
    }
    colors = [color_map.get(lbl, "#64748b") for lbl in labels]
    return generic_donut(labels, values, colors, title=title, height=height)


def dataframe_with_links(data, height=480):
    cfg = {}
    if hasattr(st, "column_config") and "Sheet Link" in data.columns:
        cfg["Sheet Link"] = st.column_config.LinkColumn("Open Row", display_text="Open")
    st.dataframe(
        data,
        width="stretch",
        hide_index=True,
        height=min(height, 42 + len(data) * 35),
        column_config=cfg if cfg else None,
    )


def build_bug_table(data, include_group=True, include_reporter=False, include_action=False):
    show = data.copy()
    show["Status"] = show["status"].map({"valid": "✅ Valid", "invalid": "❌ Invalid", "pending": "⏳ Pending"})
    show["Rebuttal?"] = show["has_rebuttal"].map({True: "✅ Yes", False: "No"})
    show["Comment?"] = show["has_comment"].map({True: "✅ Yes", False: "No"})
    show["Discussion"] = show["discussion_state"].map(discussion_state_label)

    cols = ["Sheet Row", "Sheet Link"]
    if include_group:
        cols.append(GROUP_COL)
    if include_reporter:
        cols += [NAME_COL, EMAIL_COL, ROLL_COL]
    cols += [TYPE_COL, CATEGORY_COL, "Status", "Discussion", "Rebuttal?", "Comment?"]
    if include_action:
        cols += ["Action Needed", "Age", "SLA Band"]
    cols += [STATUS_COL, REBUTTAL_COL, COMMENTS_COL]
    cols = [c for c in cols if c in show.columns]
    return show[cols]


def render_lookup_charts(data, selected_bug_filter, key_prefix):
    if selected_bug_filter == "All":
        sec = data[data["is_security"]]
        func = data[data["is_functional"]]
        all_valid, all_invalid, all_pending = status_counts(data)
        sec_valid, sec_invalid, sec_pending = status_counts(sec)
        func_valid, func_invalid, func_pending = status_counts(func)

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.plotly_chart(
                status_donut(all_valid, all_invalid, all_pending, "Overall", 190),
                width="stretch",
                key=f"{key_prefix}_overall",
            )
        with c2:
            st.plotly_chart(
                status_donut(sec_valid, sec_invalid, sec_pending, "🔐 Security", 190),
                width="stretch",
                key=f"{key_prefix}_sec",
            )
        with c3:
            st.plotly_chart(
                status_donut(func_valid, func_invalid, func_pending, "⚙️ Functional", 190),
                width="stretch",
                key=f"{key_prefix}_func",
            )
        with c4:
            st.plotly_chart(
                discussion_donut(data, "💬 Discussion", 190),
                width="stretch",
                key=f"{key_prefix}_disc",
            )
        with c5:
            st.plotly_chart(
                acceptance_donut(all_valid, all_invalid, "🧪 Acceptance", 190),
                width="stretch",
                key=f"{key_prefix}_acceptance",
            )
    else:
        valid, invalid, pending = status_counts(data)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.plotly_chart(
                status_donut(valid, invalid, pending, f"{selected_bug_filter} Bugs", 220),
                width="stretch",
                key=f"{key_prefix}_status",
            )
        with c2:
            st.plotly_chart(
                discussion_donut(data, "💬 Discussion", 220),
                width="stretch",
                key=f"{key_prefix}_disc_filtered",
            )
        with c3:
            st.plotly_chart(
                acceptance_donut(valid, invalid, "🧪 Acceptance", 220),
                width="stretch",
                key=f"{key_prefix}_acceptance_filtered",
            )


def detect_timestamp_column(data):
    ordered = []
    for col in TIMESTAMP_PRIORITY:
        if col in data.columns:
            ordered.append(col)
    for col in data.columns:
        lower = col.lower()
        if any(token in lower for token in TIMESTAMP_HINTS) and col not in ordered:
            ordered.append(col)

    best_col = None
    best_ratio = 0.0
    best_parsed = pd.Series(pd.NaT, index=data.index, dtype="datetime64[ns, UTC]")

    for col in ordered:
        parsed = pd.to_datetime(data[col], errors="coerce", utc=True)
        ratio = float(parsed.notna().mean())
        if ratio > best_ratio:
            best_ratio = ratio
            best_col = col
            best_parsed = parsed

    if best_col and best_ratio >= 0.6:
        return best_col, best_parsed
    return None, best_parsed


def age_label_from_hours(hours):
    if pd.isna(hours):
        return "N/A"
    if hours < 1:
        return "<1h"
    if hours < 24:
        return f"{int(round(hours))}h"
    days = hours / 24
    if days < 7:
        return f"{days:.1f}d"
    return f"{int(days)}d"


def sla_band_from_hours(hours):
    if pd.isna(hours):
        return "Unknown"
    if hours >= 168:
        return "Critical (7d+)"
    if hours >= 72:
        return "Aging (3d+)"
    if hours >= 24:
        return "Watchlist (1d+)"
    return "Fresh (<1d)"


def relative_sla_band(score):
    if score >= 0.9:
        return "Critical (oldest 10%)"
    if score >= 0.75:
        return "Watchlist (oldest 25%)"
    return "Recent"


def build_summary(data):
    def aggregate_status(chunk, prefix, total_col_name):
        grouped = chunk.groupby([GROUP_COL, "status"]).size().unstack(fill_value=0)
        grouped = grouped.reindex(columns=["valid", "invalid", "pending"], fill_value=0)
        grouped[total_col_name] = grouped.sum(axis=1)
        grouped.rename(
            columns={
                "valid": f"{prefix} Valid",
                "invalid": f"{prefix} Invalid",
                "pending": f"{prefix} Pending",
            },
            inplace=True,
        )
        return grouped[[total_col_name, f"{prefix} Valid", f"{prefix} Invalid", f"{prefix} Pending"]]

    all_stats = aggregate_status(data, "All", "Total")
    sec_stats = aggregate_status(data[data["is_security"]], "Sec", "Sec Total")
    func_stats = aggregate_status(data[data["is_functional"]], "Func", "Func Total")

    merged = all_stats.join(sec_stats, how="left").join(func_stats, how="left").fillna(0)
    merged = merged.reset_index().rename(columns={GROUP_COL: "Group"})

    numeric_cols = [c for c in merged.columns if c != "Group"]
    merged[numeric_cols] = merged[numeric_cols].astype(int)

    try:
        merged = merged.sort_values("Group", key=lambda x: x.astype(int))
    except (ValueError, TypeError):
        merged = merged.sort_values("Group")
    return merged.reset_index(drop=True)


def build_action_label(row):
    tags = []
    if row["is_pending_validation"]:
        tags.append("⏳ Pending Validation")
    if row["needs_reviewer_reply"]:
        tags.append("🧑‍🏫 Needs Reviewer Comment")
    if row["needs_student_reply"]:
        tags.append("🎓 Needs Student Rebuttal")
    return " | ".join(tags) if tags else "None"


def render_age_note(data):
    if data.empty:
        return
    mode = data["age_mode"].iloc[0]
    if mode == "timestamp":
        st.caption("Aging/SLA is based on parsed timestamp values in the sheet.")
    else:
        st.caption(
            "Aging/SLA is using relative row recency (no timestamp column detected in this sheet). "
            "Add a timestamp column for exact hours/days."
        )


# ===== Data Load + Prep =====
@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def load_data():
    failures = []
    for candidate in build_sheet_url_candidates(CSV_URL):
        try:
            req = Request(candidate, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            loaded = pd.read_csv(io.StringIO(raw))
            loaded.columns = loaded.columns.str.strip()
            return loaded
        except Exception as exc:
            failures.append((candidate, exc))

    # Re-raise a useful final exception for upstream handlers.
    if failures:
        _, last_exc = failures[-1]
        raise last_exc
    raise RuntimeError("No URL candidates generated for CSV loading.")


try:
    df = load_data()
except HTTPError as e:
    if e.code in (401, 403):
        st.error("Failed to load data: Google Sheet is not publicly accessible from Streamlit Cloud (HTTP 401/403).")
        st.markdown(
            """
### Fix This
1. Open the sheet and set **Share -> General access -> Anyone with the link (Viewer)**.
2. If org policies block export links, use **File -> Share -> Publish to web**, then copy CSV URL.
3. Set that URL as `CSV_URL` in Streamlit **App Settings -> Secrets** and redeploy.
"""
        )
    else:
        st.error(f"Failed to load data: HTTP {e.code} for URL: {CSV_URL}")
    st.stop()
except URLError as e:
    st.error(f"Failed to load data: network error while fetching sheet ({e}).")
    st.stop()
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

df = df.copy()
df[GROUP_COL] = df[GROUP_COL].astype(str).str.strip()
df[TYPE_COL] = df[TYPE_COL].astype(str).str.lower().str.strip()

if STATUS_COL in df.columns:
    df[STATUS_COL] = df[STATUS_COL].astype(str).str.lower().str.strip()
else:
    df[STATUS_COL] = "pending"

if REBUTTAL_COL not in df.columns:
    df[REBUTTAL_COL] = ""
if COMMENTS_COL not in df.columns:
    df[COMMENTS_COL] = ""
if EMAIL_COL not in df.columns:
    df[EMAIL_COL] = ""
if ROLL_COL not in df.columns:
    df[ROLL_COL] = ""

df["status"] = df[STATUS_COL].apply(classify_status)
df["bug_type"] = classify_bug_type_series(df[TYPE_COL])
df["is_security"] = df["bug_type"] == "security"
df["is_functional"] = df["bug_type"] == "functionality"

df["Sheet Row"] = df.index + 2
df["Sheet Link"] = df["Sheet Row"].apply(lambda row_num: f"{SHEET_VIEW_URL}&range=A{int(row_num)}")

df["has_rebuttal"] = has_meaningful_text_series(df[REBUTTAL_COL])
df["has_comment"] = has_meaningful_text_series(df[COMMENTS_COL])
df["has_discussion"] = df["has_rebuttal"] & df["has_comment"]
df["needs_reviewer_reply"] = df["has_rebuttal"] & (~df["has_comment"])
df["needs_student_reply"] = df["has_comment"] & (~df["has_rebuttal"])

df["discussion_state"] = "none"
df.loc[df["has_discussion"], "discussion_state"] = "both"
df.loc[df["needs_reviewer_reply"], "discussion_state"] = "waiting_reviewer"
df.loc[df["needs_student_reply"], "discussion_state"] = "waiting_student"

timestamp_col, parsed_timestamp = detect_timestamp_column(df)
if timestamp_col:
    now_utc = pd.Timestamp.now(tz="UTC")
    age_hours = (now_utc - parsed_timestamp).dt.total_seconds() / 3600
    age_hours = age_hours.clip(lower=0)
    df["age_hours"] = age_hours
    df["Age"] = df["age_hours"].apply(age_label_from_hours)
    df["SLA Band"] = df["age_hours"].apply(sla_band_from_hours)
    df["age_mode"] = "timestamp"
else:
    position = pd.Series(range(len(df)), index=df.index)
    relative_score = (len(df) - position) / max(len(df), 1)
    df["age_hours"] = pd.NA
    df["Age"] = relative_score.apply(lambda score: "Oldest 10%" if score >= 0.9 else ("Oldest 25%" if score >= 0.75 else "Recent"))
    df["SLA Band"] = relative_score.apply(relative_sla_band)
    df["age_mode"] = "relative"

df["is_pending_validation"] = df["status"] == "pending"
df["is_actionable"] = df["is_pending_validation"] | df["needs_reviewer_reply"] | df["needs_student_reply"]
df["Action Needed"] = df.apply(build_action_label, axis=1)
df["age_sort"] = df["age_hours"].fillna(0)
if timestamp_col is None:
    pos = pd.Series(range(len(df)), index=df.index)
    df["age_sort"] = (len(df) - pos) / max(len(df), 1)

summary = build_summary(df)

# ===== Tabs =====
tab_overview, tab_rankings, tab_queue, tab_student, tab_group = st.tabs(
    ["📊 Group Overview", "🏆 Rankings", "⚡ Action Queue", "🔍 Student Lookup", "🧭 Group Lookup"]
)

# ============================================================
# TAB 1: OVERVIEW
# ============================================================
with tab_overview:
    total_bugs = int(summary["Total"].sum())
    total_valid = int(summary["All Valid"].sum())
    total_invalid = int(summary["All Invalid"].sum())
    total_pending = int(summary["All Pending"].sum())
    hit_rate = round(total_valid / total_bugs * 100, 1) if total_bugs > 0 else 0
    acceptance_pct, _ = acceptance_rate(total_valid, total_invalid)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Bugs", total_bugs)
    c2.metric("✅ Valid", total_valid)
    c3.metric("❌ Invalid", total_invalid)
    c4.metric("⏳ Pending", total_pending)
    c5.metric("Hit Rate %", f"{hit_rate}%")
    c6.metric("Acceptance %", f"{acceptance_pct}%")

    st.markdown("")

    cols_per_row = 4
    for i in range(0, len(summary), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(summary):
                break
            row = summary.iloc[idx]
            with col:
                st.markdown(
                    f"""
                <div class="group-card">
                    <div class="group-label">Group {row['Group']}</div>
                    <div class="group-sub">{int(row['Total'])} bugs reported</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
                gid = row["Group"]
                d1, d2 = st.columns(2)
                with d1:
                    st.plotly_chart(
                        status_donut(
                            int(row["Sec Valid"]),
                            int(row["Sec Invalid"]),
                            int(row["Sec Pending"]),
                            "🔐 Security",
                            150,
                        ),
                        width="stretch",
                        key=f"overview_sec_{gid}",
                    )
                with d2:
                    st.plotly_chart(
                        status_donut(
                            int(row["Func Valid"]),
                            int(row["Func Invalid"]),
                            int(row["Func Pending"]),
                            "⚙️ Functional",
                            150,
                        ),
                        width="stretch",
                        key=f"overview_func_{gid}",
                    )
        st.markdown("")

    st.caption(f"🔄 Auto-refresh every {REFRESH_INTERVAL}s  ·  {len(summary)} groups tracked")

# ============================================================
# TAB 2: RANKINGS
# ============================================================
with tab_rankings:
    f1, f2, f3 = st.columns([2, 2, 1])
    with f1:
        rank_by = st.selectbox(
            "Rank by",
            [
                "Validated Security Bugs",
                "Validated Functional Bugs",
                "Total Validated Bugs",
                "Validation %",
                "Total Bugs Reported",
            ],
            key="rank_by",
        )
    with f2:
        show_cols = st.multiselect(
            "Show columns",
            ["Security", "Functional", "All", "Percentage"],
            default=["Security", "Functional", "Percentage"],
            key="show_cols",
        )
    with f3:
        sort_order = st.radio("Order", ["Desc", "Asc"], horizontal=True, key="sort_dir")

    lb = summary.copy()
    lb["Validation %"] = (lb["All Valid"] / lb["Total"] * 100).round(1).fillna(0)

    sort_map = {
        "Validated Security Bugs": "Sec Valid",
        "Validated Functional Bugs": "Func Valid",
        "Total Validated Bugs": "All Valid",
        "Validation %": "Validation %",
        "Total Bugs Reported": "Total",
    }
    lb = lb.sort_values(sort_map[rank_by], ascending=(sort_order == "Asc")).reset_index(drop=True)
    lb.insert(0, "Rank", range(1, len(lb) + 1))
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lb["Rank"] = lb["Rank"].apply(lambda r: f"{medals.get(r, '')} {r}".strip())

    cols = ["Rank", "Group", "Total"]
    if "Security" in show_cols:
        cols += ["Sec Valid", "Sec Total"]
    if "Functional" in show_cols:
        cols += ["Func Valid", "Func Total"]
    if "All" in show_cols:
        cols += ["All Valid", "All Invalid", "All Pending"]
    if "Percentage" in show_cols:
        cols += ["Validation %"]

    display = lb[cols].copy()
    display.rename(
        columns={
            "Total": "Bugs",
            "Sec Valid": "Sec ✅",
            "Sec Total": "Sec Total",
            "Func Valid": "Func ✅",
            "Func Total": "Func Total",
            "All Valid": "All ✅",
            "All Invalid": "All ❌",
            "All Pending": "All ⏳",
            "Validation %": "Valid %",
        },
        inplace=True,
    )
    st.dataframe(display, width="stretch", hide_index=True, height=min(720, 42 + len(display) * 35))

    st.markdown("")
    st.subheader(f"📊 {rank_by}")
    top = lb.head(15)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Security ✅", x=top["Group"], y=top["Sec Valid"], marker_color="#8b5cf6"))
    fig.add_trace(go.Bar(name="Functional ✅", x=top["Group"], y=top["Func Valid"], marker_color="#3b82f6"))
    fig.update_layout(
        barmode="stack",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c4b5fd", family="Inter"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="center",
            x=0.5,
            font=dict(size=12),
        ),
        margin=dict(t=10, b=50, l=50, r=20),
        height=380,
        xaxis=dict(title="Group", showgrid=False, type="category", tickfont=dict(size=12)),
        yaxis=dict(title="Validated Bugs", showgrid=True, gridcolor="#1e1e30", tickfont=dict(size=11)),
        bargap=0.25,
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(f"🔄 Auto-refresh every {REFRESH_INTERVAL}s")

# ============================================================
# TAB 3: ACTION QUEUE
# ============================================================
with tab_queue:
    st.subheader("⚡ Action Queue and Aging/SLA")

    q1, q2, q3, q4 = st.columns([1.8, 1, 1.5, 1.5])
    with q1:
        selected_actions = st.multiselect(
            "Queue filters",
            list(ACTION_LABELS.keys()),
            default=list(ACTION_LABELS.keys()),
            key="queue_actions",
        )
    with q2:
        queue_bug_type = st.selectbox(
            "Bug type",
            ["All", "Security", "Functionality"],
            key="queue_bug_type",
        )
    with q3:
        all_groups = sort_group_values(df[GROUP_COL])
        selected_groups = st.multiselect(
            "Group filter",
            all_groups,
            default=[],
            placeholder="All groups",
            key="queue_groups",
        )
    with q4:
        reporter_query = st.text_input(
            "Reporter search",
            "",
            placeholder="name or email",
            key="queue_reporter_search",
        )

    queue_base = apply_bug_type_filter(df, queue_bug_type)
    if selected_groups:
        queue_base = queue_base[queue_base[GROUP_COL].isin(selected_groups)]
    if reporter_query.strip():
        query = reporter_query.strip()
        reporter_mask = (
            queue_base[NAME_COL].astype(str).str.contains(query, case=False, na=False)
            | queue_base[EMAIL_COL].astype(str).str.contains(query, case=False, na=False)
        )
        queue_base = queue_base[reporter_mask]

    queue_view = apply_action_filters(queue_base, selected_actions)
    queue_view = queue_view.sort_values(["age_sort", "Sheet Row"], ascending=[False, True])

    st.markdown(
        f"""
    <div class="group-card" style="max-width:760px; margin: 10px auto 14px auto;">
        <div class="group-label" style="font-size:1.2rem;">📌 Actionable Backlog</div>
        <div class="group-sub">{len(queue_view)} rows in queue view · {len(queue_base)} rows in filtered base</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if queue_base.empty:
        st.info("No rows match the current Action Queue filters.")
    else:
        render_action_metrics(queue_base)
        st.markdown("")
        render_age_note(queue_base)

        queue_valid, queue_invalid, _ = status_counts(queue_base)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.plotly_chart(
                queue_donut(queue_base, "Queue Mix", 220),
                width="stretch",
                key="queue_mix",
            )
        with c2:
            st.plotly_chart(
                sla_donut(queue_base[queue_base["is_actionable"]], "Aging / SLA Mix", 220),
                width="stretch",
                key="queue_sla",
            )
        with c3:
            st.plotly_chart(
                acceptance_donut(queue_valid, queue_invalid, "🧪 Acceptance", 220),
                width="stretch",
                key="queue_acceptance",
            )

        st.markdown("")
        st.subheader("📋 Queue Rows")
        if queue_view.empty:
            st.info("No rows remain after applying the selected queue categories.")
        else:
            dataframe_with_links(
                build_bug_table(
                    queue_view,
                    include_group=True,
                    include_reporter=True,
                    include_action=True,
                ),
                height=760,
            )

# ============================================================
# TAB 4: STUDENT LOOKUP
# ============================================================
with tab_student:
    st.subheader("🔍 Search by Student Name")

    if NAME_COL in df.columns:
        s1, s2, s3 = st.columns([2, 1, 1])
        with s1:
            search = st.text_input(
                "Type a student's name",
                "",
                key="student_search",
                placeholder="e.g. Harsh, Damera, etc.",
            )
        with s2:
            student_bug_filter = st.selectbox(
                "Bug type filter",
                ["All", "Security", "Functionality"],
                key="student_bug_type",
            )
        with s3:
            student_disc_filter = st.selectbox(
                "Discussion filter",
                [
                    "All",
                    "Both rebuttal and comments",
                    "Waiting reviewer comment",
                    "Waiting student rebuttal",
                    "No text in both",
                ],
                key="student_disc_filter",
            )

        if search.strip():
            mask = df[NAME_COL].astype(str).str.contains(search.strip(), case=False, na=False)
            matches = df.loc[mask, NAME_COL].dropna().unique()

            if len(matches) == 0:
                st.warning(f'No students found matching "{search}"')
            else:
                selected_name = (
                    st.selectbox("Multiple matches - pick one:", sorted(matches), key="name_pick")
                    if len(matches) > 1
                    else matches[0]
                )

                student_all = df[df[NAME_COL] == selected_name]
                student_filtered = apply_bug_type_filter(student_all, student_bug_filter)

                st.markdown(
                    f"""
                <div class="group-card" style="max-width:680px; margin: 12px auto;">
                    <div class="group-label" style="font-size:1.2rem;">👤 {selected_name}</div>
                    <div class="group-sub">{len(student_filtered)} in view · {len(student_all)} total reported</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
                st.markdown("")

                if student_filtered.empty:
                    st.info(f"No {student_bug_filter.lower()} bugs found for this student.")
                else:
                    render_status_metrics(student_filtered)
                    st.markdown("")
                    render_discussion_metrics(student_filtered)
                    st.markdown("")
                    render_age_note(student_filtered)
                    render_lookup_charts(student_filtered, student_bug_filter, "student")

                    st.subheader(f"📋 Bugs by {selected_name}")
                    student_table = apply_discussion_filter(student_filtered, student_disc_filter)
                    dataframe_with_links(
                        build_bug_table(student_table, include_group=True, include_reporter=False, include_action=True),
                        height=680,
                    )
        else:
            st.info("Start typing a name above to search.")
    else:
        st.error(f'Column "{NAME_COL}" not found in the data.')

# ============================================================
# TAB 5: GROUP LOOKUP
# ============================================================
with tab_group:
    st.subheader("🧭 Search by Group")

    if GROUP_COL in df.columns:
        group_values = sort_group_values(df[GROUP_COL])
        g1, g2, g3 = st.columns([1.4, 1, 1])
        with g1:
            selected_group = st.selectbox("Pick a group", group_values, key="group_pick")
        with g2:
            group_bug_filter = st.selectbox(
                "Bug type filter",
                ["All", "Security", "Functionality"],
                key="group_bug_type",
            )
        with g3:
            group_disc_filter = st.selectbox(
                "Discussion filter",
                [
                    "All",
                    "Both rebuttal and comments",
                    "Waiting reviewer comment",
                    "Waiting student rebuttal",
                    "No text in both",
                ],
                key="group_disc_filter",
            )

        group_all = df[df[GROUP_COL] == selected_group]
        group_filtered = apply_bug_type_filter(group_all, group_bug_filter)

        st.markdown(
            f"""
        <div class="group-card" style="max-width:760px; margin: 12px auto;">
            <div class="group-label" style="font-size:1.2rem;">👥 Group {selected_group}</div>
            <div class="group-sub">{len(group_filtered)} in view · {len(group_all)} total bugs reported against this group</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown("")

        if group_filtered.empty:
            st.info(f"No {group_bug_filter.lower()} bugs found for this group.")
        else:
            render_status_metrics(group_filtered)
            st.markdown("")
            render_discussion_metrics(group_filtered)
            st.markdown("")
            render_age_note(group_filtered)
            render_lookup_charts(group_filtered, group_bug_filter, "group")

            st.subheader(f"📋 Bugs Reported for Group {selected_group}")
            group_table = apply_discussion_filter(group_filtered, group_disc_filter)
            dataframe_with_links(
                build_bug_table(group_table, include_group=False, include_reporter=True, include_action=True),
                height=720,
            )
    else:
        st.error(f'Column "{GROUP_COL}" not found in the data.')

st.caption(f"🔄 Auto-refresh every {REFRESH_INTERVAL}s  ·  refresh #{refresh_count}")
