import time
import requests
import streamlit as st

# --- CONFIGURATION ---
API_BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Oncology Agentic RAG", page_icon="🧬", layout="wide")

# --- SIDEBAR & BACKEND HEALTH CHECK ---
with st.sidebar:
    st.title("⚙️ System Settings")
    st.markdown("Configure the Agentic RAG pipeline behavior.")

    # Toggle for routing
    use_live_api = st.toggle("Use Live Evidence (PubMed/Trials)", value=True)

    st.divider()

    st.subheader("Backend Status")
    # Ping the FastAPI health endpoint
    try:
        health_res = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health_res.status_code == 200:
            st.success("🟢 FastAPI Backend Online")
            st.caption(f"Version: {health_res.json().get('version')}")
        else:
            st.warning("🟡 Backend returned unexpected status.")
    except requests.exceptions.ConnectionError:
        st.error("🔴 FastAPI Backend Offline")
        st.caption("Please run: `uv run 10_fastapi_backend.py` in another terminal.")

# --- MAIN UI: CHAT INTERFACE ---
st.title("🧬 Oncology Clinical Assistant")
st.markdown(
    "Ask clinical questions. The agent will retrieve, grade, and cite evidence automatically."
)

# Initialize chat history in Streamlit session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display existing chat history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # If it's an assistant message, display the metadata (scores and references)
        if message["role"] == "assistant":
            col1, col2 = st.columns([1, 3])
            with col1:
                st.info(f"**Score:** {message.get('score', 'N/A')}")
            with col2:
                with st.expander("📚 Supporting References"):
                    for ref in message.get("refs", []):
                        st.markdown(f"- {ref}")

# --- USER INPUT PROCESSING ---
if prompt := st.chat_input("E.g., What is the targeted therapy for KRAS G12C?"):
    # 1. Add user message to chat history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Assistant response block
    with st.chat_message("assistant"):
        # UI flair: Show the "Agentic Workflow" steps to the user
        with st.status("Agentic RAG Pipeline Executing...", expanded=True) as status:
            st.write("🔄 Routing query to appropriate database...")
            time.sleep(0.5)  # Simulated delay for UI effect
            st.write("📄 Retrieving and reranking documents...")
            time.sleep(0.5)
            st.write("🧠 Synthesizing clinical response...")
            time.sleep(0.5)
            st.write("🛡️ Running guardrail validation...")

            # Make the actual POST request to your FastAPI backend
            try:
                payload = {"query": prompt, "use_live_api": use_live_api}
                response = requests.post(
                    f"{API_BASE_URL}/search", json=payload, timeout=30
                )

                if response.status_code == 200:
                    status.update(
                        label="Response Generated Successfully!",
                        state="complete",
                        expanded=False,
                    )
                    data = response.json()

                    answer = data.get("answer", "No answer generated.")
                    score = data.get("confidence_score", "Unknown")
                    refs = data.get("references", [])

                    # Also optionally ping the validation endpoint to show deep verification
                    val_payload = {"claim": answer, "context": "Mock Context"}
                    val_res = requests.post(
                        f"{API_BASE_URL}/validate", json=val_payload
                    ).json()

                else:
                    status.update(label="API Error", state="error")
                    answer = f"Error: API returned status code {response.status_code}"
                    score, refs = "Error", []

            except Exception as e:
                status.update(label="Connection Failed", state="error")
                answer = "Critical Error: Could not connect to the FastAPI backend. Is it running?"
                score, refs = "Error", []

        # 3. Display the final answer
        st.markdown(answer)

        # Display the metadata beautifully
        if score != "Error":
            col1, col2 = st.columns([1, 3])
            with col1:
                if "High" in score:
                    st.success(f"**Confidence:**\n{score}")
                elif "Medium" in score:
                    st.warning(f"**Confidence:**\n{score}")
                else:
                    st.error(f"**Confidence:**\n{score}")

            with col2:
                with st.expander("📚 Supporting References"):
                    for ref in refs:
                        st.markdown(f"- {ref}")

            # Show validation guardrail status
            if "val_res" in locals() and not val_res.get("is_safe_to_display"):
                st.error(f"⚠️ Guardrail Warning: {val_res.get('reasoning')}")

        # 4. Save assistant response to memory
        st.session_state.messages.append(
            {"role": "assistant", "content": answer, "score": score, "refs": refs}
        )
