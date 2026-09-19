import json
import requests
import streamlit as st
import streamlit.components.v1 as components
from utils.api_client import ai_status, get_chat_history, send_chat_message
from utils.state import (
    add_chat_message,
    get_facility_id,
    get_facility_name,
    init_state,
)

st.set_page_config(
    page_title="Voice Assistant | SFEID", layout="wide", page_icon="🎙️"
)
init_state()

facility_id = get_facility_id()
facility_name = get_facility_name()

st.markdown(f"## 🎙️ Voice & Chat Assistant for Administrators — {facility_name}")
st.caption(
    "Query facility operational metrics, active anomalies, priority alerts,"
    " forecasts, and recommendations. Features **browser Text-to-Speech (TTS)**"
    " output with natural AI voice."
)

status_info = ai_status()
llm_enabled = status_info.get("llm_enabled", False)

if llm_enabled:
  st.info("🟢 **Engine Mode:** LLM-Enhanced (Gemini 3.8 Flash)")
else:
  st.info("🔵 **Engine Mode:** Rule-Based Engine (Offline mode)")

st.divider()


# --- Text-to-Speech (TTS) JavaScript Injector Helper with Premium AI Voice ---
def speak_text(text: str):
  # Clean text to remove markdown asterisks or hashes for smooth reading
  cleaned = (
      text.replace('"', '\\"')
      .replace("\n", " ")
      .replace("*", "")
      .replace("#", "")
  )

  js_code = f"""
    <script>
    if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
        
        var msg = new SpeechSynthesisUtterance('{cleaned}');
        
        function setVoiceAndSpeak() {{
            var voices = window.speechSynthesis.getVoices();
            
            // Try to find a premium/natural Indian English female voice (Google, Microsoft Zira, Heera, etc.)
            var indianVoice = voices.find(v => (v.lang.includes('en-IN') || v.lang.includes('IN')) && (v.name.includes('Female') || v.name.includes('Google') || v.name.includes('Zira') || v.name.includes('Heera') || v.name.includes('Neerja')));
            
            if (!indianVoice) {{
                indianVoice = voices.find(v => v.lang.includes('en-IN') || v.lang.includes('IN'));
            }}
            if (!indianVoice) {{
                indianVoice = voices.find(v => v.name.includes('Female') || v.name.includes('Zira') || v.name.includes('Google'));
            }}
            
            if (indianVoice) {{
                msg.voice = indianVoice;
            }}
            
            // Optimized rate and pitch for a natural, pleasant AI conversational tone
            msg.rate = 1.0; 
            msg.pitch = 1.05; 
            msg.lang = 'en-IN';
            
            window.speechSynthesis.speak(msg);
        }}
        
        if (window.speechSynthesis.getVoices().length > 0) {{
            setVoiceAndSpeak();
        }} else {{
            window.speechSynthesis.onvoiceschanged = setVoiceAndSpeak;
        }}
    }}
    </script>
    """
  components.html(js_code, height=0, width=0)


st.divider()

# --- Voice Audio File Upload / Mic Input Section ---
with st.expander("🎙️ Voice Input (Upload WAV / Audio Recording)"):
  audio_file = st.file_uploader(
      "Upload voice command (WAV / MP3)", type=["wav", "mp3"]
  )
  if audio_file is not None:
    if st.button("▶️ Process Audio Command"):
      with st.spinner("Transcribing audio & analyzing intent..."):
        try:
          res = requests.post(
              f"http://localhost:8000/ai/voice?facility_id={facility_id}",
              files={"audio_file": (audio_file.name, audio_file.getvalue())},
              timeout=15,
          ).json()
          reply = res.get("reply", "Could not process audio.")
          st.success("Audio transcribed and processed successfully.")
          speak_text(reply)
        except Exception as exc:
          st.error(f"Voice processing failed: {exc}")

st.divider()

# --- Chat History & Message Interface ---
history = get_chat_history(facility_id, limit=30)

# Display existing messages
for msg in history:
  role = msg.get("role", "assistant")
  content = msg.get("message", "")
  src = msg.get("source", "rule_engine")

  with st.chat_message(role):
    st.markdown(content)
    if role == "assistant":
      st.caption(
          f"Source: {'🔵 Gemini LLM' if src == 'llm' else '⚙️ Rule Engine'}"
      )

# Chat Input Box (Ab yahan type karne par bhi sound aayega!)
user_prompt = st.chat_input("Ask about facility energy, water, air quality...")

if user_prompt:
  # Display user message immediately
  with st.chat_message("user"):
    st.markdown(user_prompt)

  # Fetch response from FastAPI
  with st.chat_message("assistant"):
    with st.spinner("Analyzing query..."):
      res = send_chat_message(facility_id, user_prompt)
      reply = res.get("reply", "No response.")
      src = res.get("source", "rule_engine")
      st.markdown(reply)
      st.caption(
          f"Source: {'🔵 Gemini LLM' if src == 'llm' else '⚙️ Rule Engine'}"
      )
      # Trigger speech output for typed chat messages as well
      speak_text(reply)

st.write("")
st.caption("💡 **Quick Questions:** Try clicking one:")
qcols = st.columns(4)

with qcols[0]:
  if st.button("⚡ Energy Status"):
    res = send_chat_message(
        facility_id, "What is current energy consumption?"
    )
    reply = res.get("reply", "No response.")
    st.markdown(reply)
    speak_text(reply)

with qcols[1]:
  if st.button("🚨 Open Anomalies"):
    res = send_chat_message(facility_id, "Are there any active anomalies?")
    reply = res.get("reply", "No response.")
    st.markdown(reply)
    speak_text(reply)

with qcols[2]:
  if st.button("🌱 Sustainability Score"):
    res = send_chat_message(facility_id, "What is the sustainability score?")
    reply = res.get("reply", "No response.")
    st.markdown(reply)
    speak_text(reply)

with qcols[3]:
  if st.button("💡 Top Recommendations"):
    res = send_chat_message(
        facility_id, "Give me recommendations to save energy."
    )
    reply = res.get("reply", "No response.")
    st.markdown(reply)
    speak_text(reply)
