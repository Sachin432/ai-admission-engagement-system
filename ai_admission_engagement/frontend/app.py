import streamlit as st
import requests
import time
import os
from twilio.rest import Client
from langchain_groq import ChatGroq
# from langchain.prompts import PromptTemplate
from langchain_core.prompts import PromptTemplate



from langchain.chains import LLMChain

# ----------------------------
# Load secrets
# ----------------------------
TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = st.secrets["TWILIO_FROM_NUMBER"]
TWILIO_TWIML_URL = st.secrets["TWILIO_TWIML_URL"]

DB_URL = st.secrets["DB_URL"]
DB_KEY = st.secrets["DB_KEY"]

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# ----------------------------
# Clients
# ----------------------------
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama-3.1-70b-versatile"
)

# ----------------------------
# Supabase helpers
# ----------------------------
def sb_headers():
    return {
        "apikey": DB_KEY,
        "Authorization": f"Bearer {DB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def save_lead(name, phone, query):
    payload = {
        "name": name,
        "phone": phone,
        "query": query,
        "status": "created"
    }
    r = requests.post(f"{DB_URL}/rest/v1/leads", json=payload, headers=sb_headers())
    if r.status_code != 201:
        raise Exception(f"Insert failed: {r.status_code} {r.text}")
    data = r.json()
    return data[0]["id"]

def update_lead(lead_id, fields: dict):
    r = requests.patch(
        f"{DB_URL}/rest/v1/leads?id=eq.{lead_id}",
        json=fields,
        headers=sb_headers(),
    )
    if r.status_code not in (200, 204):
        raise Exception(f"Update failed: {r.status_code} {r.text}")

def get_lead(lead_id):
    r = requests.get(
        f"{DB_URL}/rest/v1/leads?id=eq.{lead_id}",
        headers={"apikey": DB_KEY, "Authorization": f"Bearer {DB_KEY}"},
    )
    if r.status_code != 200:
        raise Exception(f"Fetch failed: {r.status_code} {r.text}")
    data = r.json()
    return data[0] if data else None

# ----------------------------
# Twilio helpers
# ----------------------------
def start_call(phone, lead_id):
    call = twilio_client.calls.create(
        to=phone,
        from_=TWILIO_FROM_NUMBER,
        url=TWILIO_TWIML_URL,
    )
    update_lead(lead_id, {"call_sid": call.sid, "status": "calling"})
    return call.sid

def poll_call_and_get_recording(call_sid, timeout_sec=300, poll_every=10):
    start = time.time()
    while time.time() - start < timeout_sec:
        call = twilio_client.calls(call_sid).fetch()
        if call.status == "completed":
            recs = twilio_client.recordings.list(call_sid=call_sid, limit=1)
            if recs:
                return recs[0].uri  # relative URI
        time.sleep(poll_every)
    return None

def download_recording(uri):
    # Twilio gives relative URI; build absolute
    url = f"https://api.twilio.com{uri.replace('.json', '.wav')}"
    r = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    if r.status_code != 200:
        raise Exception("Failed to download recording")
    return r.content

# ----------------------------
# STT (placeholder)
# Replace with Whisper or HF pipeline if you want real STT
# ----------------------------
def speech_to_text(audio_bytes):
    # TODO: integrate Whisper/HF. For MVP, return placeholder.
    return "User discussed interest, budget, and timeline."

# ----------------------------
# LangChain analysis
# ----------------------------
def analyze_transcript(transcript: str):
    prompt = PromptTemplate(
        input_variables=["t"],
        template="""
From this conversation transcript:
{t}

1) Extract fields:
- interest_level (low/medium/high)
- budget (low/medium/high/unknown)
- timeline (immediate/1-3 months/3+ months/unknown)
- program_interest (text)

2) Provide:
- score (0 to 100)
- category (Hot/Warm/Cold)
- short summary

Return JSON with keys:
interest_level, budget, timeline, program_interest, score, category, summary
"""
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    out = chain.run(t=transcript)
    return out

# ----------------------------
# UI
# ----------------------------
st.set_page_config(page_title="AI Admission Engagement", layout="wide")
st.title("AI Admission Engagement (Streamlit-only)")

with st.sidebar:
    st.subheader("Add Lead")
    name = st.text_input("Name")
    phone = st.text_input("Phone (E.164, e.g., +91...)")
    query = st.text_area("Initial Query")
    if st.button("Create Lead & Start Call"):
        if not name or not phone:
            st.error("Name and phone required")
        else:
            lead_id = save_lead(name, phone, query)
            call_sid = start_call(phone, lead_id)
            st.success(f"Call started. Lead ID: {lead_id}, Call SID: {call_sid}")

st.subheader("Analyze a Lead")

lead_id = st.text_input("Enter Lead ID")

if st.button("Poll Call, Analyze, Save"):
    if not lead_id:
        st.error("Enter Lead ID")
    else:
        lead = get_lead(lead_id)
        if not lead or not lead.get("call_sid"):
            st.error("Lead not found or call not started")
        else:
            st.info("Polling Twilio for recording...")
            rec_uri = poll_call_and_get_recording(lead["call_sid"])
            if not rec_uri:
                st.error("Recording not ready yet. Try again later.")
            else:
                audio = download_recording(rec_uri)
                st.info("Running speech-to-text...")
                transcript = speech_to_text(audio)
                st.write("Transcript:", transcript)

                st.info("Running AI analysis (LangChain + Groq)...")
                result_json_text = analyze_transcript(transcript)
                st.write("AI Output (raw):", result_json_text)

                # Save raw + mark analyzed (you can parse JSON if you enforce strict JSON)
                update_lead(lead_id, {
                    "transcript": transcript,
                    "summary": result_json_text,
                    "status": "analyzed"
                })
                st.success("Saved analysis to DB.")

st.divider()
st.subheader("View Lead")

if st.button("Refresh Lead"):
    if not lead_id:
        st.error("Enter Lead ID")
    else:
        lead = get_lead(lead_id)
        if not lead:
            st.error("Not found")
        else:
            st.json(lead)
