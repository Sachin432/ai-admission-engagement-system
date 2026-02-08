import streamlit as st
import os
import time
from dotenv import load_dotenv
from twilio.rest import Client
import requests

# Load env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
TWILIO_VOICE_START_URL = os.getenv("TWILIO_VOICE_START_URL")

DB_URL = os.getenv("DB_URL")
DB_KEY = os.getenv("DB_KEY")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

st.set_page_config(page_title="AI Admission Engagement")

st.title("AI Admission Engagement Dashboard")

st.subheader("Add New Lead")

name = st.text_input("Name")
phone = st.text_input("Phone (E.164 format, e.g. +91...)")
query = st.text_area("Initial Query")

def save_lead_to_db(name, phone, query):
    payload = {"name": name, "phone": phone, "query": query}
    r = requests.post(f"{DB_URL}/leads", json=payload, headers={"apikey": DB_KEY})
    return r.json()["id"]

def start_call(phone, lead_id):
    call = client.calls.create(
        to=phone,
        from_=TWILIO_FROM_NUMBER,
        url=f"{TWILIO_VOICE_START_URL}?lead_id={lead_id}"
    )
    return call.sid

if st.button("Start AI Call"):
    if not name or not phone or not query:
        st.error("Fill all fields")
    else:
        lead_id = save_lead_to_db(name, phone, query)
        call_sid = start_call(phone, lead_id)
        st.success(f"Call started. Call SID: {call_sid}")

st.divider()

st.subheader("Check Lead Result")

lead_id_check = st.text_input("Enter Lead ID")

def get_lead_result(lead_id):
    r = requests.get(f"{DB_URL}/leads/{lead_id}", headers={"apikey": DB_KEY})
    return r.json()

if st.button("Refresh Result"):
    if not lead_id_check:
        st.error("Enter Lead ID")
    else:
        data = get_lead_result(lead_id_check)
        st.write("Status:", data.get("status"))
        st.write("Transcript:", data.get("transcript"))
        st.write("Extracted Info:", data.get("extracted_fields"))
        st.write("Score:", data.get("score"))
        st.write("Category:", data.get("category"))
        st.write("Summary:", data.get("summary"))
