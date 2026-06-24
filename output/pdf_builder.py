"""Builds and writes the PDF pitch report using a WeasyPrint HTML-to-PDF pipeline."""

import html as _html_mod
from datetime import date

from analysis.valuation import compute_ebitda


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt(value, prefix: str = "$", suffix: str = "") -> str:
    """Format a numeric value as $XB / $XM / $XK, or 'N/A' if None."""
    if value is None:
        return "N/A"
    v = float(value)
    if abs(v) >= 1e12:
        return f"{prefix}{v / 1e12:.2f}T{suffix}"
    if abs(v) >= 1e9:
        return f"{prefix}{v / 1e9:.2f}B{suffix}"
    if abs(v) >= 1e6:
        return f"{prefix}{v / 1e6:.2f}M{suffix}"
    return f"{prefix}{v:,.2f}{suffix}"


def _fmt_price(value) -> str:
    """Format a per-share price as $X.XX."""
    if value is None:
        return "N/A"
    return f"${float(value):.2f}"


def _h(text) -> str:
    """HTML-escape a value for safe embedding."""
    return _html_mod.escape(str(text)) if text is not None else "N/A"


# ── Design logic helpers ──────────────────────────────────────────────────────

def _flag_category(flag_text: str):
    """Return (border_color, tag_label) for a risk flag string."""
    fl = flag_text.lower()
    if "dcf" in fl or "premium exceeds" in fl or "overvalued" in fl:
        return "#1a1a2e", "DCF"
    if "tuck-in" in fl or "leverage" in fl or "revenue is" in fl:
        return "#EF9F27", "SIZE / LEVERAGE"
    return "#E24B4A", "VALUATION"


def _verdict(flag_count: int):
    """Return (background_color, text_color, label) for the verdict pill."""
    if flag_count <= 1:
        return "#3B6D11", "#ffffff", "DEAL VIABLE"
    if flag_count == 2:
        return "#EF9F27", "#ffffff", "PROCEED WITH CAUTION"
    return "#E24B4A", "#ffffff", "HIGH RISK"


def _bottom_line(acq_name, tgt_name, target_val, premium, flags) -> str:
    """Generate one-sentence deal summary for the cover bottom-line box."""
    mult = target_val.get("ev_ebitda_multiple")
    prem = premium.get("premium_pct")
    flag_count = len(flags)
    parts = [f"{acq_name} proposes to acquire {tgt_name}"]
    if mult is not None:
        parts.append(f"at {mult:.1f}x EV/EBITDA")
    if prem is not None:
        direction = "premium" if prem >= 0 else "discount"
        parts.append(f"with a DCF-implied {abs(prem):.1f}% {direction}")
    if flag_count == 0:
        parts.append("— no automated risk flags raised.")
    elif flag_count == 1:
        parts.append("— 1 risk flag identified.")
    else:
        parts.append(f"— {flag_count} risk flags identified.")
    return " ".join(parts[:1]) + " " + " ".join(parts[1:])


def _rationale(acq_name, tgt_name, target_val, dcf_with_premium, flags) -> str:
    """Return 4-sentence M&A rationale paragraph."""
    ev_mult = target_val.get("ev_ebitda_multiple")
    prem_pct = dcf_with_premium.get("premium_pct")
    is_accretive = dcf_with_premium.get("is_accretive")
    flag_count = len(flags)

    s1 = (
        f"{acq_name} is evaluating an acquisition of {tgt_name} at an EV/EBITDA of {ev_mult:.1f}x."
        if ev_mult is not None
        else f"{acq_name} is evaluating an acquisition of {tgt_name} (EV/EBITDA unavailable — verify financials)."
    )

    if prem_pct is not None:
        direction = "premium" if prem_pct >= 0 else "discount"
        s2 = f"DCF analysis implies a {abs(prem_pct):.1f}% {direction} to the current market price."
    else:
        s2 = "DCF analysis could not compute an implied premium — revenue or share data missing."

    s3 = (
        f"{flag_count} risk flag{'s were' if flag_count != 1 else ' was'} identified by automated screening."
    )

    if flag_count == 0:
        rec = "Analyst recommendation: proceed to second-stage diligence — no automated flags raised."
    elif flag_count <= 2:
        rec = "Analyst recommendation: exercise caution — review flagged items before proceeding."
    else:
        rec = "Analyst recommendation: full review required — multiple risk flags warrant detailed scrutiny."

    return f"{s1} {s2} {s3} {rec}"


# ── CSS (module-level constant to avoid f-string brace escaping) ──────────────

_CSS = """
@page {
    size: A4;
    margin: 18mm 15mm;
}
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}
body {
    background: #ffffff;
    color: #222222;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
}
.page + .page {
    page-break-before: always;
}

/* ── Cover ─────────────────────────────────────────────────── */
.cover-header {
    background: #1a1a2e;
    margin: -18mm -15mm 0 -15mm;
    padding: 14mm 15mm 12px 15mm;
    position: relative;
}
.cover-date {
    position: absolute;
    top: 14mm;
    right: 15mm;
    color: #8a8aaa;
    font-size: 9pt;
}
.cover-deal {
    color: #ffffff;
    font-size: 28pt;
    font-weight: bold;
    letter-spacing: 1px;
    margin-bottom: 6pt;
}
.cover-subtitle {
    color: #8a8aaa;
    font-size: 11pt;
}
.verdict-wrap {
    text-align: center;
    margin: 20pt 0 16pt 0;
}
.verdict-pill {
    display: inline-block;
    padding: 6px 28px;
    border-radius: 20px;
    font-size: 11pt;
    font-weight: bold;
    letter-spacing: 1px;
}

/* ── Stat grid ──────────────────────────────────────────────── */
.stat-grid {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20pt;
}
.stat-grid td {
    width: 25%;
    text-align: center;
    padding: 12px 6px;
    border: 1px solid #e0e0e0;
    background: #f7f7f9;
    vertical-align: middle;
}
.stat-label {
    font-size: 8pt;
    color: #777777;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.stat-value {
    font-size: 15pt;
    font-weight: bold;
    color: #1a1a2e;
}
.bottom-line-box {
    border-left: 4px solid #1a1a2e;
    background: #f0f0f4;
    padding: 10px 14px;
    font-size: 10pt;
    color: #333333;
}
.page-footer {
    border-top: 1px solid #e0e0e0;
    padding-top: 8pt;
    margin-top: 24pt;
    font-size: 8pt;
    color: #999999;
    text-align: center;
}

/* ── Section titles ────────────────────────────────────────── */
.section-title {
    font-size: 12pt;
    font-weight: bold;
    color: #1a1a2e;
    border-bottom: 2.5px solid #1a1a2e;
    padding-bottom: 5px;
    margin: 18pt 0 12pt 0;
}

/* ── Company profile tables ─────────────────────────────────── */
.profile-outer {
    width: 100%;
    border-collapse: separate;
    border-spacing: 8px 0;
    margin-bottom: 6pt;
}
.profile-outer td {
    width: 50%;
    vertical-align: top;
    padding: 0;
}
.profile-header {
    background: #1a1a2e;
    color: #ffffff;
    font-weight: bold;
    font-size: 10pt;
    padding: 6px 10px;
}
.profile-inner {
    width: 100%;
    border-collapse: collapse;
}
.tbl-label {
    font-size: 9pt;
    color: #777777;
    padding: 5px 10px;
    width: 50%;
    border-bottom: 1px solid #e8e8e8;
}
.tbl-value {
    font-size: 9pt;
    color: #222222;
    font-weight: bold;
    padding: 5px 10px;
    border-bottom: 1px solid #e8e8e8;
}

/* ── Valuation bridge ───────────────────────────────────────── */
.bridge-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 8pt;
}
.bridge-table th {
    background: #1a1a2e;
    color: #ffffff;
    font-weight: bold;
    font-size: 9pt;
    padding: 7px 10px;
    text-align: center;
    border: 1px solid #1a1a2e;
}
.bridge-table th.left {
    text-align: left;
}
.bridge-table td {
    font-size: 9pt;
    color: #222222;
    padding: 6px 10px;
    border: 1px solid #dddddd;
    text-align: center;
}
.bridge-table td.left {
    text-align: left;
    color: #444444;
}
.bridge-table tr:nth-child(odd) td {
    background: #f9f9f9;
}
.bridge-note {
    font-style: italic;
    font-size: 9pt;
    color: #777777;
    margin-top: 6pt;
    line-height: 1.5;
}

/* ── DCF table ──────────────────────────────────────────────── */
.dcf-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 14pt;
}
.dcf-table td {
    padding: 7px 12px;
    border-bottom: 1px solid #e8e8e8;
    font-size: 10pt;
}
.dcf-table td.dcf-row-label {
    background: #f5f5f5;
    color: #555555;
    width: 60%;
}
.dcf-table td.dcf-row-value {
    font-weight: bold;
    color: #1a1a2e;
}
.dcf-box {
    border: 1.5px solid #cccccc;
    border-radius: 4px;
    padding: 10px 0;
    margin-bottom: 12pt;
    width: 100%;
    border-collapse: collapse;
}
.dcf-box td {
    text-align: center;
    padding: 4px 12px;
    width: 33%;
    border-right: 1px solid #dddddd;
}
.dcf-box td:last-child {
    border-right: none;
}
.dcf-box-label {
    font-size: 8pt;
    color: #777777;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.dcf-box-value {
    font-size: 13pt;
    font-weight: bold;
}
.dcf-interp {
    font-style: italic;
    font-size: 9.5pt;
    color: #444444;
    line-height: 1.5;
}

/* ── Rationale & flags ──────────────────────────────────────── */
.rationale-para {
    font-size: 11pt;
    line-height: 1.6;
    color: #222222;
    margin-bottom: 14pt;
}
.flags-divider {
    background: #1a1a2e;
    color: #ffffff;
    font-weight: bold;
    font-size: 10pt;
    padding: 7px 12px;
    margin-bottom: 10pt;
}
.flag-card {
    border-left: 4px solid #cccccc;
    background: #fafafa;
    padding: 10px 12px;
    margin-bottom: 8px;
    width: 100%;
    border-collapse: collapse;
}
.flag-card td {
    vertical-align: middle;
    padding: 0;
}
.flag-text {
    font-size: 10pt;
    color: #222222;
    line-height: 1.5;
    padding-right: 12px;
}
.flag-tag {
    font-size: 8pt;
    color: #888888;
    background: #eeeeee;
    padding: 2px 8px;
    border-radius: 10px;
    white-space: nowrap;
    text-align: right;
}
.flag-disclaimer {
    font-style: italic;
    font-size: 9pt;
    color: #888888;
    margin-top: 10pt;
    line-height: 1.4;
}

/* ── Source table ───────────────────────────────────────────── */
.source-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16pt;
}
.source-table td {
    padding: 7px 12px;
    border-bottom: 1px solid #e8e8e8;
    font-size: 10pt;
    line-height: 1.8;
}
.source-table td.src-label {
    background: #f5f5f5;
    color: #555555;
    font-size: 9pt;
    width: 38%;
}
.disclaimer-box {
    background: #f5f5f7;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 12px 16px;
    font-size: 9pt;
    color: #666666;
    line-height: 1.6;
}
"""

_FOOTER_TEXT = (
    "Not financial advice &middot; For due diligence purposes only"
    " &middot; PitchOS &middot; github.com/zshqv/PitchOS"
)


# ── HTML builder ──────────────────────────────────────────────────────────────

def build_html(
    acquirer_data: dict,
    target_data: dict,
    acquirer_val: dict,
    target_val: dict,
    target_dcf: dict,
    premium: dict,
    flags: list,
) -> str:
    """Build and return the full 5-page HTML report string."""

    # ── Derived scalars ───────────────────────────────────────────────────────
    acq_ticker = (acquirer_data.get("ticker") or "ACQ").upper()
    tgt_ticker  = (target_data.get("ticker") or "TGT").upper()
    acq_name    = acquirer_data.get("company_name") or acq_ticker
    tgt_name    = target_data.get("company_name") or tgt_ticker
    deal_label  = f"{acq_ticker} → {tgt_ticker}"
    gen_date    = date.today().strftime("%d %b %Y")
    flag_count  = len(flags)

    dcf_with_premium = {**target_dcf, **premium}

    pill_bg, pill_fg, pill_text = _verdict(flag_count)

    ev_mult_raw   = target_val.get("ev_ebitda_multiple")
    ev_mult_str   = f"{ev_mult_raw:.1f}x" if ev_mult_raw is not None else "N/A"
    dcf_price_str = _fmt_price(target_dcf.get("implied_share_price"))
    prem_pct      = premium.get("premium_pct")
    prem_str      = f"{prem_pct:+.1f}%" if prem_pct is not None else "N/A"

    flag_color = "#E24B4A" if flag_count >= 3 else ("#EF9F27" if flag_count == 2 else "#3B6D11")

    bottom_sentence = _bottom_line(acq_name, tgt_name, target_val, premium, flags)

    # ── Profile table builder ─────────────────────────────────────────────────
    def _profile_rows(d: dict) -> str:
        ebitda = compute_ebitda(d)
        rows = [
            ("Ticker",        d.get("ticker") or "N/A"),
            ("Market Cap",    _fmt(d.get("market_cap"))),
            ("Revenue",       _fmt(d.get("revenue"))),
            ("EBITDA",        _fmt(ebitda)),
            ("Total Debt",    _fmt(d.get("total_debt"))),
            ("Current Price", _fmt_price(d.get("current_price"))),
        ]
        out = ""
        for i, (label, value) in enumerate(rows):
            bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
            out += (
                f'<tr style="background:{bg};">'
                f'<td class="tbl-label">{_h(label)}</td>'
                f'<td class="tbl-value">{_h(value)}</td>'
                f"</tr>"
            )
        return out

    # ── Valuation bridge ──────────────────────────────────────────────────────
    acq_mult_raw = acquirer_val.get("ev_ebitda_multiple")
    tgt_mult_raw = target_val.get("ev_ebitda_multiple")
    acq_mult_str = f"{acq_mult_raw:.1f}x" if acq_mult_raw is not None else "N/A"
    tgt_mult_str = f"{tgt_mult_raw:.1f}x" if tgt_mult_raw is not None else "N/A"

    if acq_mult_raw is not None and tgt_mult_raw is not None:
        if tgt_mult_raw > acq_mult_raw:
            mult_note = (
                f"{_h(tgt_ticker)} trades at a higher EV/EBITDA multiple ({tgt_mult_raw:.1f}x) "
                f"than {_h(acq_ticker)} ({acq_mult_raw:.1f}x), implying the deal is priced at a "
                "premium to the acquirer's own market valuation — synergy delivery is essential "
                "to justify the spread."
            )
        else:
            mult_note = (
                f"{_h(tgt_ticker)} trades at a lower EV/EBITDA multiple ({tgt_mult_raw:.1f}x) "
                f"than {_h(acq_ticker)} ({acq_mult_raw:.1f}x), suggesting the acquisition could "
                "be immediately accretive if integration costs remain contained."
            )
    else:
        mult_note = "Insufficient data to generate EV/EBITDA commentary — verify financials manually."

    # ── DCF premium box ───────────────────────────────────────────────────────
    is_accretive = premium.get("is_accretive")
    if is_accretive is True:
        dcf_box_bg     = "#e8f5e0"
        dcf_box_border = "#3B6D11"
        dcf_box_color  = "#3B6D11"
    elif is_accretive is False:
        dcf_box_bg     = "#fde8e8"
        dcf_box_border = "#E24B4A"
        dcf_box_color  = "#E24B4A"
    else:
        dcf_box_bg     = "#f5f5f5"
        dcf_box_border = "#888888"
        dcf_box_color  = "#555555"

    prem_label  = premium.get("label", "N/A")
    implied_str = _fmt_price(target_dcf.get("implied_share_price"))

    if prem_pct is not None:
        direction  = "premium" if is_accretive else "discount"
        stance     = "attractive at current terms" if is_accretive else "potentially expensive at current terms"
        dcf_interp = (
            f"DCF implies a {abs(prem_pct):.1f}% {direction} to the current market price. "
            f"Deal appears {stance}."
        )
    else:
        dcf_interp = "Insufficient data to generate DCF interpretation — verify revenue and share count."

    # ── Risk flag cards ───────────────────────────────────────────────────────
    if not flags:
        flag_cards_html = (
            '<p style="color:#3B6D11;font-weight:bold;font-size:10pt;">'
            "No material deal risks identified by automated screen.</p>"
        )
    else:
        parts = []
        for flag in flags:
            border_color, tag_label = _flag_category(flag)
            parts.append(
                f'<table class="flag-card" style="border-left-color:{border_color};">'
                f"<tr>"
                f'<td class="flag-text">{_h(flag)}</td>'
                f'<td class="flag-tag">{_h(tag_label)}</td>'
                f"</tr></table>"
            )
        flag_cards_html = "\n".join(parts)

    rationale_text = _rationale(acq_name, tgt_name, target_val, dcf_with_premium, flags)
    assumptions_str = "5yr projection · 5% revenue growth · 20% EBITDA margin · WACC 9% · terminal growth 2.5%"

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>{_CSS}</style>
</head>
<body>


<!-- ═══════════════════════════════════════════════════════ PAGE 1  COVER -->
<div class="page">

  <div class="cover-header">
    <span class="cover-date">{_h(gen_date)}</span>
    <div class="cover-deal">{_h(deal_label)}</div>
    <div class="cover-subtitle">M&amp;A Rationale Report</div>
  </div>

  <div class="verdict-wrap">
    <span class="verdict-pill" style="background:{pill_bg};color:{pill_fg};">{_h(pill_text)}</span>
  </div>

  <table class="stat-grid">
    <tr>
      <td>
        <div class="stat-label">EV/EBITDA Multiple</div>
        <div class="stat-value">{_h(ev_mult_str)}</div>
      </td>
      <td>
        <div class="stat-label">DCF Implied Price</div>
        <div class="stat-value">{_h(dcf_price_str)}</div>
      </td>
      <td>
        <div class="stat-label">Acquisition Premium</div>
        <div class="stat-value">{_h(prem_str)}</div>
      </td>
      <td>
        <div class="stat-label">Risk Flags Raised</div>
        <div class="stat-value" style="color:{flag_color};">{flag_count}</div>
      </td>
    </tr>
  </table>

  <div class="bottom-line-box">{_h(bottom_sentence)}</div>

  <div class="page-footer">{_FOOTER_TEXT}</div>

</div>


<!-- ══════════════════════════════════ PAGE 2  COMPANY PROFILES & VALUATION -->
<div class="page">

  <div class="section-title">Company Profiles</div>

  <table class="profile-outer">
    <tr>
      <td>
        <div class="profile-header">{_h(acq_name)}</div>
        <table class="profile-inner">
          {_profile_rows(acquirer_data)}
        </table>
      </td>
      <td>
        <div class="profile-header">{_h(tgt_name)}</div>
        <table class="profile-inner">
          {_profile_rows(target_data)}
        </table>
      </td>
    </tr>
  </table>

  <div class="section-title">Valuation Bridge</div>

  <table class="bridge-table">
    <thead>
      <tr>
        <th class="left">Metric</th>
        <th>{_h(acq_ticker)}</th>
        <th>{_h(tgt_ticker)}</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="left">EBITDA</td>
        <td>{_h(_fmt(acquirer_val.get("ebitda")))}</td>
        <td>{_h(_fmt(target_val.get("ebitda")))}</td>
      </tr>
      <tr>
        <td class="left">Enterprise Value</td>
        <td>{_h(_fmt(acquirer_val.get("enterprise_value")))}</td>
        <td>{_h(_fmt(target_val.get("enterprise_value")))}</td>
      </tr>
      <tr>
        <td class="left">EV/EBITDA Multiple</td>
        <td>{_h(acq_mult_str)}</td>
        <td>{_h(tgt_mult_str)}</td>
      </tr>
    </tbody>
  </table>

  <p class="bridge-note">{mult_note}</p>

</div>


<!-- ══════════════════════════════════════════════ PAGE 3  DCF VALUATION -->
<div class="page" style="page-break-before: always;">

  <div class="section-title">DCF Valuation — 5-Year Projection + Terminal Value</div>

  <table class="dcf-table">
    <tr>
      <td class="dcf-row-label">PV of Free Cash Flows</td>
      <td class="dcf-row-value">{_h(_fmt(target_dcf.get("total_pv_fcf")))}</td>
    </tr>
    <tr>
      <td class="dcf-row-label">PV of Terminal Value</td>
      <td class="dcf-row-value">{_h(_fmt(target_dcf.get("pv_terminal_value")))}</td>
    </tr>
    <tr>
      <td class="dcf-row-label">DCF Enterprise Value</td>
      <td class="dcf-row-value">{_h(_fmt(target_dcf.get("enterprise_value_dcf")))}</td>
    </tr>
    <tr>
      <td class="dcf-row-label">Implied Share Price</td>
      <td class="dcf-row-value">{_h(_fmt_price(target_dcf.get("implied_share_price")))}</td>
    </tr>
  </table>

  <table class="dcf-box" style="background:{dcf_box_bg};border-color:{dcf_box_border};">
    <tr>
      <td>
        <div class="dcf-box-label">DCF Implied Price</div>
        <div class="dcf-box-value" style="color:{dcf_box_color};">{_h(implied_str)}</div>
      </td>
      <td>
        <div class="dcf-box-label">Premium / Discount</div>
        <div class="dcf-box-value" style="color:{dcf_box_color};">{_h(prem_label)}</div>
      </td>
      <td>
        <div class="dcf-box-label">Premium %</div>
        <div class="dcf-box-value" style="color:{dcf_box_color};">{_h(prem_str)}</div>
      </td>
    </tr>
  </table>

  <p class="dcf-interp">{_h(dcf_interp)}</p>

</div>


<!-- ══════════════════════════════════════════ PAGE 4  RATIONALE & FLAGS -->
<div class="page" style="page-break-before: always;">

  <div class="section-title">M&amp;A Rationale Summary</div>
  <p class="rationale-para">{_h(rationale_text)}</p>

  <div class="flags-divider">Automated Deal Risk Flags ({flag_count})</div>

  {flag_cards_html}

  <p class="flag-disclaimer">
    Flags are algorithmically generated based on publicly available financial data.
    Analyst review required before distribution or investment decision.
  </p>

</div>


<!-- ═══════════════════════════════════ PAGE 5  SOURCE & METHODOLOGY -->
<div class="page">

  <div class="section-title">Source &amp; Reproducibility</div>

  <table class="source-table">
    <tr>
      <td class="src-label">Acquirer</td>
      <td>{_h(acq_name)} ({_h(acq_ticker)})</td>
    </tr>
    <tr>
      <td class="src-label">Target</td>
      <td>{_h(tgt_name)} ({_h(tgt_ticker)})</td>
    </tr>
    <tr>
      <td class="src-label">Data Source</td>
      <td>Yahoo Finance via yfinance Python library (live pull at generation time)</td>
    </tr>
    <tr>
      <td class="src-label">Generated On</td>
      <td>{_h(gen_date)}</td>
    </tr>
    <tr>
      <td class="src-label">Valuation Method</td>
      <td>EV/EBITDA relative valuation + 5-year DCF with terminal value (Gordon Growth Model)</td>
    </tr>
    <tr>
      <td class="src-label">DCF Assumptions</td>
      <td>{_h(assumptions_str)}</td>
    </tr>
    <tr>
      <td class="src-label">GitHub</td>
      <td>github.com/zshqv/PitchOS</td>
    </tr>
  </table>

  <div class="disclaimer-box">
    <strong>Disclaimer.</strong> This report is generated automatically by PitchOS using publicly
    available financial data sourced from Yahoo Finance. All figures are based on trailing
    twelve-month (TTM) financials and are provided for informational and due diligence purposes
    only. This report does not constitute financial advice, investment advice, or a recommendation
    to buy, sell, or hold any security. Valuation outputs are model-derived estimates and may
    differ materially from actual transaction values. Users should conduct their own independent
    analysis and consult qualified financial advisors before making any investment decision.
    PitchOS and its contributors accept no liability for decisions made on the basis of this report.
  </div>

  <div class="page-footer">{_FOOTER_TEXT}</div>

</div>


</body>
</html>"""


# ── Public entry point ────────────────────────────────────────────────────────

def build_report(
    acquirer_data: dict,
    target_data: dict,
    acquirer_val: dict,
    target_val: dict,
    target_dcf: dict,
    premium: dict,
    flags: list,
    output_path: str,
) -> None:
    """Assemble and save the full PitchOS PDF via WeasyPrint HTML pipeline."""
    from xhtml2pdf import pisa

    html_str = build_html(
        acquirer_data, target_data, acquirer_val, target_val,
        target_dcf, premium, flags,
    )
    with open(output_path, "wb") as pdf_file:
        pisa.CreatePDF(html_str, dest=pdf_file)
