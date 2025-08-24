import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from pathlib import Path
from celery.result import AsyncResult
from backend.tasks import factor_analysis
import pandas as pd, altair as alt

UPLOAD_DIR = Path("/shared/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="StratLab", layout="wide")
st.sidebar.title("StratLab ⛵")

page = st.sidebar.radio("Navigate", ["Upload", "Factor Model", "Results"])


def _render_task_failure(res: AsyncResult, err: Exception) -> None:
    """Show a concise error plus the worker traceback if available."""
    st.error(f"Task failed: {type(err).__name__}: {err}")
    tb = getattr(res, "traceback", None)
    if tb:
        st.caption("Worker traceback")
        st.code(tb, language="text")


def _render_results(out: dict) -> None:
    """Render task output defensively (keys may be missing on partial failures)."""
    if not isinstance(out, dict):
        st.error("Unexpected task output format.")
        return

def _render_results(out: dict) -> None:
    """Render task output defensively (keys may be missing on partial failures)."""
    if not isinstance(out, dict):
        st.error("Unexpected task output format.")
        return

    # Summary table - FIXED: Handle the new data format
    summary_info = out.get("summary", {})
    if summary_info and "data" in summary_info:
        try:
            # The data is already in list of dicts format, convert to DataFrame directly
            df = pd.DataFrame(summary_info["data"])
            st.subheader("Summary")
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not parse summary table: {e}")
            # Debug info
            st.write("Debug - Summary structure:")
            st.json(summary_info)

    # Check if there was an error in the task
    if "error" in out:
        st.error(f"Analysis failed: {out['error']}")
        return

    # VaR chart
    var_chart = out.get("var_chart")
    if isinstance(var_chart, dict) and var_chart.get("x") and var_chart.get("y"):
        try:
            chart_data = pd.DataFrame(var_chart)
            st.altair_chart(
                alt.Chart(chart_data)
                .mark_bar()
                .encode(x="x:N", y="y:Q")
                .properties(title="99% VaR by Symbol"),
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"Could not render VaR chart: {e}")

    # Beta chart
    beta_chart = out.get("beta_chart")
    if isinstance(beta_chart, dict) and beta_chart.get("x") and beta_chart.get("y"):
        try:
            chart_data = pd.DataFrame(beta_chart)
            st.altair_chart(
                alt.Chart(chart_data)
                .mark_line(point=True)
                .encode(x="x:N", y="y:Q")
                .properties(title="CAMP Beta vs SPY"),
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"Could not render Beta chart: {e}")

    if not (summary_info.get("data") or var_chart or beta_chart):
        st.info("Task completed but no renderable outputs were returned.")


def safe_get_result(res: AsyncResult, timeout: int = 10):
    """Safely get result from Celery task, handling conversion errors."""
    try:
        return res.get(timeout=timeout, propagate=True)
    except Exception as e:
        error_msg = str(e)
        # Check if it's the specific float conversion error we're dealing with
        if "could not convert string to float" in error_msg and "2025-01-01" in error_msg:
            st.error("Data processing error: Found date strings where numeric values were expected.")
            st.info("This usually means your data has dates in the wrong columns. Please check that:")
            st.markdown("""
            - Date column contains only dates
            - Price (Px) column contains only numbers  
            - Return (Ret) column contains only numbers
            - No date strings are mixed in with numeric data
            """)
            return None
        else:
            # Re-raise other exceptions
            raise e


if page == "Upload":
    uploaded = st.file_uploader("Upload price data", type=["csv", "parquet"])
    if uploaded:
        dest = UPLOAD_DIR / uploaded.name
        dest.write_bytes(uploaded.getbuffer())
        st.session_state["data_path"] = str(dest)
        st.success(f"Saved to {dest}")

elif page == "Factor Model":
    if "data_path" not in st.session_state:
        st.warning("Please upload data first.")
    else:
        st.header("Factor Model Settings")
        
        # Add data validation button
        if st.button("🔍 Test Data Loading"):
            from backend.tasks import test_data_loading
            try:
                result = test_data_loading.delay(st.session_state["data_path"]).get(timeout=30)
                if result["success"]:
                    st.success("✅ Data loaded successfully!")
                    st.write("**Data Info:**")
                    st.write(f"Shape: {result['shape']}")
                    st.write(f"Columns: {result['columns']}")
                    st.write("**Data Types:**")
                    st.json(result['dtypes'])
                    st.write("**Date Range:**")
                    st.write(f"From {result['date_range']['min']} to {result['date_range']['max']}")
                else:
                    st.error("❌ Data loading failed!")
                    st.code(result['error'])
            except Exception as e:
                st.error(f"Test failed: {e}")
        
        st.markdown("---")
        
        # Keep priors strictly numeric; slider returns float already
        priors = {"lambda": float(st.slider("Shrinkage λ", 0.0, 1.0, 0.1))}
        run = st.button("Run Analysis")
        if run:
            try:
                # Debug: Show what we're sending to the task
                st.write("Debug info:")
                st.write(f"File path: {st.session_state['data_path']}")
                st.write(f"Priors: {priors}")
                
                # Dispatch Celery task with clear args
                task = factor_analysis.delay(st.session_state["data_path"], priors)
                st.session_state["task_id"] = task.id
                st.info("Task dispatched – check Results tab.")
                
            except Exception as e:
                st.error(f"Failed to start task: {e}")
                st.code(str(e))

elif page == "Results":
    tid = st.session_state.get("task_id")
    if not tid:
        st.info("No analysis run yet.")
    else:
        res = AsyncResult(tid)
        st.caption(f"Task status: {res.status}")

        if res.failed():
            # Safely handle failed tasks
            try:
                safe_get_result(res, timeout=1)
            except Exception as e:
                _render_task_failure(res, e)

        elif res.successful():
            # FIXED: Use safe_get_result instead of direct res.get()
            try:
                out = safe_get_result(res, timeout=10)
                if out is not None:
                    _render_results(out)
            except Exception as e:
                _render_task_failure(res, e)

        else:
            with st.spinner("Running…"):
                # No busy-loop; on user interaction or tab revisit it will update.
                pass