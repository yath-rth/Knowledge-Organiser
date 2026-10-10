import os
import sys
import json
import glob
import re
import html
from datetime import datetime

DEFAULT_INPUT_DIR = "comparison_output"
DEFAULT_COMBINED_FILE = os.path.join(DEFAULT_INPUT_DIR, "all_models_comparison.json")
DEFAULT_OUTPUT_FILE = "email_comparison_report.html"

# Aesthetic styling colors (accent border, light badge background, dark badge text)
PALETTE = [
    ("#6366f1", "#e0e7ff", "#3730a3"),  # Indigo
    ("#f97316", "#ffedd5", "#9a3412"),  # Orange
    ("#10b981", "#d1fae5", "#065f46"),  # Emerald
    ("#8b5cf6", "#ede9fe", "#5b21b6"),  # Purple
    ("#ef4444", "#fee2e2", "#991b1b"),  # Red
    ("#06b6d4", "#ecfeff", "#0891b2"),  # Cyan
    ("#eab308", "#fef9c3", "#854d0e"),  # Yellow
    ("#ec4899", "#fce7f3", "#9d174d"),  # Pink
]

def load_comparison_data(input_path):
    # Try loading combined file first
    if os.path.exists(input_path):
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "results_by_model" in data and "emails" in data:
                    return data
        except Exception as e:
            print(f"Warning: Failed to load combined file at {input_path} ({e})")

    # Fallback: scan for individual files and combine them
    print("Combined comparison file not found or invalid. Reconstructing from individual model JSONs...")
    model_files = glob.glob(os.path.join(DEFAULT_INPUT_DIR, "model_*_results.json"))
    if not model_files:
        print(f"Error: No results found in '{DEFAULT_INPUT_DIR}' directory.")
        return None

    emails_map = {}
    results_by_model = {}
    models_compared = []

    for path in model_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = json.load(f)
            metadata = content.get("metadata", {})
            model_name = metadata.get("model", os.path.basename(path))
            models_compared.append(model_name)
            
            results = content.get("results", [])
            results_by_model[model_name] = results

            # Reconstruct the basic email list
            for r in results:
                g_id = r.get("gmail_id")
                if g_id and g_id not in emails_map:
                    emails_map[g_id] = {
                        "gmail_id": g_id,
                        "subject": r.get("raw_subject", "No Subject"),
                        "sender": r.get("sender", "Unknown")
                    }
        except Exception as e:
            print(f"Warning: Failed to parse {path} ({e})")

    if not results_by_model:
        return None

    sorted_emails = sorted(emails_map.values(), key=lambda x: int(x["gmail_id"]))

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_emails_processed": len(sorted_emails),
            "models_compared": models_compared
        },
        "emails": sorted_emails,
        "results_by_model": results_by_model
    }

def calculate_stats(data):
    emails = data["emails"]
    results_by_model = data["results_by_model"]
    
    total_emails = len(emails)
    num_models = len(results_by_model)
    
    total_runs = 0
    failures = 0
    high_priority_count = 0
    total_latency = 0.0
    latency_counts = 0

    model_latencies = {}

    for model, results in results_by_model.items():
        model_latencies[model] = {"total": 0.0, "count": 0}
        for r in results:
            total_runs += 1
            if not r.get("success", False):
                failures += 1
            else:
                if (r.get("priority") or "").lower() == "high":
                    high_priority_count += 1
                
            lat = r.get("latency_seconds")
            if lat is not None:
                total_latency += lat
                latency_counts += 1
                model_latencies[model]["total"] += lat
                model_latencies[model]["count"] += 1

    avg_latencies = {}
    for model, stats in model_latencies.items():
        if stats["count"] > 0:
            avg_latencies[model] = stats["total"] / stats["count"]
        else:
            avg_latencies[model] = 0.0

    # Calculate agreement rates
    agreement_count = 0
    for em in emails:
        g_id = em["gmail_id"]
        types = set()
        priorities = set()
        for model, results in results_by_model.items():
            r = next((item for item in results if item.get("gmail_id") == g_id), None)
            if r and r.get("success", False):
                types.add((r.get("type") or "").strip().lower())
                priorities.add((r.get("priority") or "").strip().lower())
        
        # If all successful models returned the exact same type and priority
        if len(types) <= 1 and len(priorities) <= 1:
            agreement_count += 1

    agreement_rate = (agreement_count / total_emails * 100) if total_emails > 0 else 0.0

    return {
        "total_emails": total_emails,
        "num_models": num_models,
        "total_runs": total_runs,
        "failures": failures,
        "high_priority_count": high_priority_count,
        "avg_latency": (total_latency / latency_counts) if latency_counts > 0 else 0.0,
        "avg_latencies_by_model": avg_latencies,
        "agreement_rate": agreement_rate
    }

def generate_html(data, stats, output_path):
    emails = data["emails"]
    # Sort emails to show the latest first (highest id descending)
    emails_sorted = sorted(emails, key=lambda x: int(x["gmail_id"]), reverse=True)
    results_by_model = data["results_by_model"]
    models = list(results_by_model.keys())

    # Map models to color palette
    model_colors = {}
    for i, model in enumerate(models):
        model_colors[model] = PALETTE[i % len(PALETTE)]

    title = "Email Model Comparison Report"
    processed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate model legend
    legend_html = ""
    for model in models:
        colors = model_colors[model]
        legend_html += f"""
        <span class="legend-item" style="border-left: 4px solid {colors[0]}; background: {colors[1]}; color: {colors[2]};">
            {html.escape(model)}
        </span>
        """

    # Generate stats cards
    stats_html = f"""
    <div class="stat-card">
        <h3>Total Emails</h3>
        <div class="stat-val">{stats['total_emails']}</div>
        <div class="stat-desc">Distinct items evaluated</div>
    </div>
    <div class="stat-card">
        <h3>Models Compared</h3>
        <div class="stat-val">{stats['num_models']}</div>
        <div class="stat-desc">Active LLM configurations</div>
    </div>
    <div class="stat-card">
        <h3>Consensus Rate</h3>
        <div class="stat-val">{stats['agreement_rate']:.1f}%</div>
        <div class="stat-desc">Complete type & priority agreement</div>
    </div>
    <div class="stat-card">
        <h3>Errors / Failures</h3>
        <div class="stat-val" style="color: { '#ef4444' if stats['failures'] > 0 else '#10b981' };">{stats['failures']}</div>
        <div class="stat-desc">API or format parsing faults</div>
    </div>
    """

    # Model latency comparison list
    latency_html = ""
    for model in models:
        colors = model_colors[model]
        avg_l = stats["avg_latencies_by_model"].get(model, 0.0)
        latency_html += f"""
        <div class="latency-row">
            <span class="latency-model" style="color: {colors[0]}; font-weight: 600;">{html.escape(model)}</span>
            <span class="latency-val">{avg_l:.2f}s avg</span>
        </div>
        """

    # Comparison Table Headers
    table_headers = "<th>Email Subject</th>"
    for model in models:
        colors = model_colors[model]
        table_headers += f"""<th style="background: {colors[1]}; color: {colors[2]}; border-bottom: 2px solid {colors[0]};">{html.escape(model)}</th>"""

    # Comparison Table Rows
    table_rows = ""
    for idx, em in enumerate(emails_sorted):
        g_id = em["gmail_id"]
        table_rows += f"<tr>"
        table_rows += f"""<td><div class="table-sub">#{g_id}</div><strong>{html.escape(em['subject'])}</strong><div class="table-sender">From: {html.escape(em['sender'])}</div></td>"""
        
        for model in models:
            results = results_by_model[model]
            r = next((item for item in results if item.get("gmail_id") == g_id), None)
            
            if not r:
                table_rows += f"""<td class="text-muted italic">No data</td>"""
            elif not r.get("success", False):
                table_rows += f"""<td class="cell-fail">✖ Error<br><small>{html.escape(r.get("error", "Unknown error")[:50])}</small></td>"""
            else:
                prio = (r.get("priority") or "LOW").upper()
                prio_class = "badge-high" if prio == "HIGH" else "badge-low"
                table_rows += f"""
                <td>
                    <div style="font-weight: 600; margin-bottom: 4px;">{html.escape(r.get("type") or "Other")}</div>
                    <span class="badge {prio_class}">{prio}</span>
                    <div class="cell-title">{html.escape(r.get("title") or "No title")}</div>
                </td>
                """
        table_rows += "</tr>"

    # Detailed Comparison Cards
    details_html = ""
    for idx, em in enumerate(emails_sorted):
        g_id = em["gmail_id"]
        details_html += f"""
        <div class="detail-block">
            <div class="detail-email-header">
                <h2>Email #{g_id}: {html.escape(em['subject'])}</h2>
                <div class="detail-sender">Sender: {html.escape(em['sender'])}</div>
            </div>
            <div class="model-cards-grid">
        """

        for model in models:
            colors = model_colors[model]
            results = results_by_model[model]
            r = next((item for item in results if item.get("gmail_id") == g_id), None)

            if not r:
                details_html += f"""
                <div class="model-card" style="border-top: 4px solid #cbd5e1;">
                    <div class="card-model-name" style="background: #f1f5f9; color: #475569;">{html.escape(model)}</div>
                    <div class="p-4 italic text-muted">No processing data found for this model.</div>
                </div>
                """
            elif not r.get("success", False):
                details_html += f"""
                <div class="model-card" style="border-top: 4px solid #ef4444;">
                    <div class="card-model-name" style="background: #fee2e2; color: #991b1b;">{html.escape(model)} (Failed)</div>
                    <div class="p-4">
                        <div class="error-box">
                            <strong>Extraction Failed:</strong><br>
                            {html.escape(r.get("error", "Unknown error"))}
                        </div>
                        <div class="meta-row mt-4">
                            <span>Latency: {r.get("latency_seconds", 0.0):.2f}s</span>
                        </div>
                    </div>
                </div>
                """
            else:
                prio = (r.get("priority") or "LOW").upper()
                prio_badge_class = "badge-high" if prio == "HIGH" else "badge-low"
                
                # Format bullets nicely
                summary = r.get("summary") or ""
                summary_items = []
                if isinstance(summary, list):
                    summary_items = summary
                elif isinstance(summary, str):
                    summary_items = [s.strip().lstrip("-* ").strip() for s in summary.split("\n") if s.strip()]

                bullets_html = ""
                if summary_items:
                    bullets_html += '<ul class="bullet-list">'
                    for item in summary_items:
                        if item:
                            bullets_html += f"<li>{html.escape(item)}</li>"
                    bullets_html += "</ul>"
                else:
                    bullets_html = '<div class="text-muted italic">No summary bullets provided</div>'

                details_html += f"""
                <div class="model-card" style="border-top: 4px solid {colors[0]};">
                    <div class="card-model-name" style="background: {colors[1]}; color: {colors[2]};">
                        {html.escape(model)}
                    </div>
                    <div class="card-body">
                        <div class="card-main-title">{html.escape(r.get("title") or "No Extracted Title")}</div>
                        
                        <div class="card-badges-row">
                            <span class="badge" style="background: {colors[1]}; color: {colors[2]};">{html.escape(r.get("type") or "Other")}</span>
                            <span class="badge {prio_badge_class}">{prio}</span>
                        </div>

                        <div class="fields-table">
                            <div class="field-item">
                                <span class="field-label">Date</span>
                                <span class="field-val">{html.escape(r.get("date") or "N/A")}</span>
                            </div>
                            <div class="field-item">
                                <span class="field-label">Time</span>
                                <span class="field-val">{html.escape(r.get("time") or "N/A")}</span>
                            </div>
                            <div class="field-item">
                                <span class="field-label">Location</span>
                                <span class="field-val">{html.escape(r.get("location") or "N/A")}</span>
                            </div>
                        </div>

                        <div class="summary-box">
                            <div class="summary-title">Extracted Summary</div>
                            {bullets_html}
                        </div>

                        <div class="meta-row">
                            <span>Latency: {r.get("latency_seconds", 0.0):.2f}s</span>
                            <span>Processed: {html.escape(r.get("processed_at", "")[:19].replace("T", " "))}</span>
                        </div>
                    </div>
                </div>
                """

        details_html += """
            </div>
        </div>
        """

    # Master template
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --primary: #4f46e5;
            --primary-light: #e0e7ff;
            --success: #10b981;
            --success-light: #d1fae5;
            --danger: #ef4444;
            --danger-light: #fee2e2;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.5;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 1440px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 32px;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}

        header h1 {{
            font-size: 2.25rem;
            font-weight: 800;
            margin-bottom: 8px;
            letter-spacing: -0.025em;
        }}

        header p {{
            color: #94a3b8;
            font-size: 1.1rem;
        }}

        .legend-container {{
            margin-top: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }}

        .legend-label {{
            font-weight: 600;
            font-size: 0.85rem;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .legend-item {{
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
        }}

        .dashboard {{
            display: grid;
            grid-template-columns: 3fr 1fr;
            gap: 24px;
            margin-bottom: 40px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
        }}

        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        }}

        .stat-card h3 {{
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 12px;
        }}

        .stat-val {{
            font-size: 2.25rem;
            font-weight: 800;
            color: var(--text-main);
            line-height: 1;
            margin-bottom: 8px;
        }}

        .stat-desc {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}

        .latency-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .latency-card h3 {{
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 16px;
        }}

        .latency-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.9rem;
        }}

        .latency-row:last-child {{
            border-bottom: none;
            padding-bottom: 0;
        }}

        .section-header {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 20px;
            letter-spacing: -0.02em;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .card-view-sec {{
            margin-top: 50px;
        }}

        /* Table Design */
        .table-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
            margin-bottom: 40px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}

        th, td {{
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 700;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover td {{
            background-color: #f8fafc;
        }}

        .table-sub {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: monospace;
            margin-bottom: 4px;
        }}

        .table-sender {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        .cell-title {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 6px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 200px;
        }}

        .cell-fail {{
            color: var(--danger);
            background-color: var(--danger-light);
            font-size: 0.85rem;
            font-weight: 500;
        }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }}

        .badge-high {{
            background-color: var(--danger-light);
            color: var(--danger);
        }}

        .badge-low {{
            background-color: #f1f5f9;
            color: #475569;
        }}

        /* Details Blocks */
        .detail-block {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 32px;
            margin-bottom: 32px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        }}

        .detail-email-header {{
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}

        .detail-email-header h2 {{
            font-size: 1.35rem;
            font-weight: 700;
            margin-bottom: 4px;
        }}

        .detail-sender {{
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        .model-cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            align-items: start;
        }}

        .model-card {{
            background: #f8fafc;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
        }}

        .card-model-name {{
            padding: 10px 16px;
            font-weight: 700;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .card-body {{
            padding: 18px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}

        .card-main-title {{
            font-weight: 700;
            font-size: 1.05rem;
            color: var(--text-main);
            line-height: 1.3;
        }}

        .card-badges-row {{
            display: flex;
            gap: 8px;
        }}

        .fields-table {{
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background: white;
            overflow: hidden;
        }}

        .field-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 12px;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.85rem;
        }}

        .field-item:last-child {{
            border-bottom: none;
        }}

        .field-label {{
            color: var(--text-muted);
            font-weight: 500;
        }}

        .field-val {{
            color: var(--text-main);
            font-weight: 600;
        }}

        .summary-box {{
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 12px 14px;
        }}

        .summary-title {{
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.025em;
            margin-bottom: 8px;
        }}

        .bullet-list {{
            list-style-position: outside;
            padding-left: 18px;
            font-size: 0.85rem;
            color: #334155;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .meta-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: auto;
            padding-top: 10px;
            border-top: 1px dashed var(--border-color);
        }}

        .error-box {{
            background-color: var(--danger-light);
            border: 1px solid #fca5a5;
            border-radius: 6px;
            padding: 12px;
            color: var(--danger);
            font-size: 0.85rem;
            font-family: monospace;
            word-break: break-all;
        }}

        .text-muted {{ color: var(--text-muted); }}
        .italic {{ font-style: italic; }}
        .mt-4 {{ margin-top: 16px; }}
        .p-4 {{ padding: 16px; }}

        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-top: 60px;
            border-top: 1px solid var(--border-color);
            padding-top: 24px;
        }}

        @media(max-width: 1024px) {{
            .dashboard {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📧 Email Classification Model Comparison</h1>
            <p>Evaluating and benchmarking the latest email summaries across LLMs</p>
            <div class="legend-container">
                <span class="legend-label">Models:</span>
                {legend_html}
            </div>
        </header>

        <section class="dashboard">
            <div class="stats-grid">
                {stats_html}
            </div>
            <div class="latency-card">
                <h3>Avg Latency</h3>
                <div>
                    {latency_html}
                </div>
            </div>
        </section>

        <section>
            <div class="section-header">
                <span>📊</span> Quick Comparison Grid
            </div>
            <div class="table-card">
                <table>
                    <thead>
                        <tr>
                            {table_headers}
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <section class="card-view-sec">
            <div class="section-header">
                <span>🔍</span> Detailed Side-By-Side Extraction
            </div>
            {details_html}
        </section>

        <footer>
            Report generated automatically on {processed_date} • Model Comparator pipeline
        </footer>
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"Successfully generated HTML comparison dashboard: {output_path}")

def main():
    input_path = DEFAULT_COMBINED_FILE
    output_path = DEFAULT_OUTPUT_FILE

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]

    print(f"Loading results from: {input_path}")
    data = load_comparison_data(input_path)
    if not data:
        print("Error: No data loaded. Could not generate HTML report.")
        sys.exit(1)

    print("Analyzing and calculating stats...")
    stats = calculate_stats(data)

    print("Generating HTML template...")
    generate_html(data, stats, output_path)
    print("Done!")

if __name__ == "__main__":
    main()
