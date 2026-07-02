import streamlit as st
import requests

st.set_page_config(page_title="Oncology Research Assistant", page_icon="🧬", layout="wide")
st.title("🧬 Advanced Agentic Oncology Assistant")

BACKEND_URL = "http://localhost:8000"

with st.sidebar:
    st.header("Pipeline Infrastructure Status")
    try:
        health_res = requests.get(f"{BACKEND_URL}/health", timeout=3)
        if health_res.status_code == 200:
            st.success("🟢 FastAPI Backend Engine: ONLINE")
            st.caption(f"Connected to: {BACKEND_URL}")
    except Exception:
        st.error("🔴 FastAPI Backend Engine: OFFLINE")
        st.caption("Ensure your backend is running: `uv run app_api.py`")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_input := st.chat_input("Enter clinical inquiry (e.g., 'Latest trials for NCT02296125 or NCCN guidelines for HER2-low'):"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.status("Agent executing pipeline trace nodes...", expanded=True) as status:
            try:
                st.write("Routing and querying backend execution cluster...")
                
                # Fix applied: force UI to catch backend HTTP 500 errors
                raw_response = requests.post(f"{BACKEND_URL}/search", json={"query": user_input}, timeout=120)
                raw_response.raise_for_status()
                
                response = raw_response.json()

                status.write(f"**Execution Path Taken:** `{response.get('execution_path', 'N/A')}`")
                status.update(label="Response Generation Verified!", state="complete")

                generation = response.get("generation", "No response generated.")
                st.markdown(generation)

                metrics = response.get("validation_metrics", {})
                if metrics:
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        score = metrics.get("final_score", 0)
                        st.metric(label="System Confidence Score", value=f"{score}%")
                    with col2:
                        safe = "PASSED" if metrics.get("is_safe_to_display") else "FAILED GUARDRAILS"
                        st.metric(label="Clinical Safety Status", value=safe)

                    with st.expander("View Retrieved Sources"):
                        for doc in response.get("retrieved_sources", []):
                            st.markdown(f"**[{doc.get('source')} {doc.get('id')}]** {doc.get('text')}")

                st.session_state.messages.append({"role": "assistant", "content": generation})

            except Exception as e:
                status.update(label="Execution Framework Failure", state="error")
                st.error(f"Failed connection trace parameters: {str(e)}")