"""Streamlit dashboard for the AI Newsjacking Agent."""

import httpx
import streamlit as st

from src.config import API_BASE_URL

# --- API Client Helpers ---


def api_get(path: str, params: dict | None = None) -> dict | list | None:
    """GET request to the FastAPI backend. Returns parsed JSON or None on error."""
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{API_BASE_URL}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, json: dict | None = None) -> dict | None:
    """POST request to the FastAPI backend. Returns parsed JSON or None on error."""
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{API_BASE_URL}{path}", json=json)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# --- Page Functions ---


def page_dashboard():
    """Overview page with key metrics and latest run info."""
    st.header("Dashboard")

    runs = api_get("/runs", params={"limit": 1})
    if not runs:
        st.info("No pipeline runs yet. Trigger one from the sidebar!")
        return

    latest = runs[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", latest["status"].upper())
    col2.metric("Articles", latest["news_count"])
    col3.metric("Variants", latest["variants_generated"])
    col4.metric("Posted", latest["variants_posted"])

    st.subheader("Latest Run")
    st.json(latest)

    # Show top variants from latest run
    run_data = api_get(f"/runs/{latest['id']}")
    if run_data and run_data.get("top_variants"):
        st.subheader("Top Variants")
        for v in run_data["top_variants"]:
            _render_variant_card(v)


def page_runs():
    """Pipeline run history."""
    st.header("Pipeline Runs")

    runs = api_get("/runs")
    if not runs:
        st.info("No pipeline runs found.")
        return

    for run in runs:
        status_icon = {"completed": "✅", "failed": "❌", "running": "⏳"}.get(run["status"], "❓")
        label = f"{status_icon} {run['id'][:8]} — {run['status']} ({run['news_count']} articles, {run['variants_generated']} variants)"

        with st.expander(label):
            col1, col2 = st.columns(2)
            col1.write(f"**Trigger:** {run['trigger']}")
            col1.write(f"**Started:** {run['started_at']}")
            col2.write(f"**Max Chars:** {run.get('max_chars', 280)}")
            col2.write(f"**Completed:** {run.get('completed_at', 'N/A')}")
            col2.write(f"**Error:** {run.get('error') or 'None'}")

            if run.get("stage_errors"):
                st.write("**Stage Errors:**", run["stage_errors"])

            # Load variants for this run
            run_data = api_get(f"/runs/{run['id']}")
            if run_data and run_data.get("top_variants"):
                st.write("**Top Variants:**")
                for v in run_data["top_variants"]:
                    _render_variant_card(v)


def page_news():
    """Latest crypto news feed."""
    st.header("Latest News")

    if st.button("Refresh News"):
        st.rerun()

    news = api_get("/news")
    if not news:
        st.info("No news articles available.")
        return

    for item in news:
        tickers = " ".join(f"`{t}`" for t in item.get("tickers", []))
        st.markdown(f"### {item['title']}")
        st.caption(f"{item['source']} — {item['published_at']} {tickers}")
        st.write(item.get("content", "")[:300])
        if item.get("url"):
            st.markdown(f"[Read more]({item['url']})")
        st.divider()


def page_variants():
    """Browse all generated content variants."""
    st.header("Content Variants")

    # Optional run filter
    runs = api_get("/runs")
    run_options = {"All runs": None}
    if runs:
        for r in runs:
            run_options[f"{r['id'][:8]} — {r['status']}"] = r["id"]

    selected_label = st.selectbox("Filter by run", options=list(run_options.keys()))
    run_id = run_options[selected_label]

    params = {}
    if run_id:
        params["run_id"] = run_id

    variants = api_get("/variants", params=params)
    if not variants:
        st.info("No variants found.")
        return

    for v in variants:
        _render_variant_card(v)


def page_post():
    """Post content variants to Twitter (stub until P4)."""
    st.header("Post Variants")

    variants = api_get("/variants")
    if not variants:
        st.info("No variants available to post.")
        return

    # Build selection options
    options = {}
    for v in variants:
        score_str = f"{v['score']:.1f}" if v.get("score") is not None else "N/A"
        label = f"[{v['style']}] score={score_str} — {v['text'][:60]}..."
        options[label] = v["id"]

    selected = st.multiselect("Select variants to post", options=list(options.keys()))

    if st.button("Post Selected", disabled=not selected):
        variant_ids = [options[label] for label in selected]
        if len(variant_ids) == 1:
            result = api_post("/post", json={"variant_id": variant_ids[0]})
            if result:
                st.success(f"Posted! Status: {result['status']}")
        else:
            result = api_post("/post/batch", json={"variant_ids": variant_ids})
            if result:
                for r in result.get("results", []):
                    if r["status"] == "failed":
                        st.error(f"Failed: {r.get('error', 'unknown')}")
                    else:
                        st.success(f"Variant {r['variant_id'][:8]}: {r['status']}")


# --- Helpers ---


def _render_variant_card(v: dict):
    """Render a single content variant as a styled card."""
    style_colors = {"analytical": "blue", "meme": "orange", "contrarian": "red"}
    style = v.get("style", "unknown")
    color = style_colors.get(style, "gray")
    score = v.get("score")
    score_str = f"{score:.1f}" if score is not None else "N/A"

    st.markdown(f":{color}[**{style.upper()}**] &nbsp; Score: **{score_str}**/10")
    st.code(v["text"], language=None)

    # Score breakdown
    breakdown = v.get("score_breakdown")
    if breakdown:
        cols = st.columns(len(breakdown))
        for col, (criterion, val) in zip(cols, breakdown.items()):
            col.metric(criterion.replace("_", " ").title(), f"{val:.0f}/10")

    st.divider()


# --- Main App ---


def main():
    st.set_page_config(page_title="AI Newsjacking Agent", page_icon="📰", layout="wide")
    st.title("📰 AI Newsjacking Agent")

    # Sidebar: navigation + pipeline trigger
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Go to",
            ["Dashboard", "Runs", "News", "Variants", "Post"],
            label_visibility="collapsed",
        )

        st.divider()
        st.header("Actions")
        article_count = st.selectbox("Articles to process", [1, 3, 5, 10], index=1)
        char_limit = st.selectbox(
            "Max chars per tweet",
            [280, 500, 1000, 2500, 5000, 10000, 25000],
            index=0,
        )
        if st.button("🚀 Run Pipeline", use_container_width=True):
            with st.spinner("Triggering pipeline..."):
                result = api_post("/run", json={"max_articles": article_count, "max_chars": char_limit})
                if result:
                    st.success(f"Pipeline started: {result['run']['id'][:8]}")
                    st.rerun()

        # --- Scheduler Controls ---
        st.divider()
        st.header("Scheduler")

        sched_status = api_get("/scheduler/status")
        if sched_status:
            article_options = [1, 3, 5, 10]
            current_articles = sched_status.get("max_articles", 3)
            articles_idx = article_options.index(current_articles) if current_articles in article_options else 1

            sched_articles = st.selectbox(
                "Articles to process",
                article_options,
                index=articles_idx,
                key="sched_articles",
            )

            if sched_articles != current_articles:
                api_post("/scheduler/max-articles", json={"max_articles": sched_articles})
                st.rerun()

            char_options = [280, 500, 1000, 2500, 5000, 10000, 25000]
            current_chars = sched_status.get("max_chars", 280)
            chars_idx = char_options.index(current_chars) if current_chars in char_options else 0

            sched_chars = st.selectbox(
                "Max chars per tweet",
                char_options,
                index=chars_idx,
                key="sched_chars",
            )

            if sched_chars != current_chars:
                api_post("/scheduler/max-chars", json={"max_chars": sched_chars})
                st.rerun()

            interval_options = [1, 3, 8, 12, 24]
            current_interval = sched_status.get("interval_hours", 12)
            current_idx = interval_options.index(current_interval) if current_interval in interval_options else 3

            interval = st.selectbox(
                "Run every (hours)",
                interval_options,
                index=current_idx,
                format_func=lambda h: f"{h}h",
            )

            if interval != current_interval:
                api_post("/scheduler/interval", json={"interval_hours": interval})
                st.rerun()

            if sched_status["running"]:
                if st.button("⏹ Stop Scheduler", use_container_width=True):
                    api_post("/scheduler/stop")
                    st.rerun()
                next_run = sched_status.get("next_run_time", "")
                if next_run:
                    st.caption(f"Next run: {next_run[:19]}")
            else:
                if st.button("▶ Start Scheduler", use_container_width=True):
                    api_post("/scheduler/start")
                    st.rerun()
                st.caption("Scheduler stopped")

    # Route to selected page
    pages = {
        "Dashboard": page_dashboard,
        "Runs": page_runs,
        "News": page_news,
        "Variants": page_variants,
        "Post": page_post,
    }
    pages[page]()


if __name__ == "__main__":
    main()
