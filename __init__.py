import streamlit as st
import pandas as pd
from datetime import datetime
from database import engine, User, Session
from models import Org, Schedule

def main():
    st.set_page_config(page_title="Survey Scheduler Pro", layout="wide")
    
    # Organization Configuration
    with st.sidebar.expander("🏢 Organization Setup"):
        with st.form("org_config"):
            Org.org_name = st.text_input("Organization Name", value=Org.org_name or "")
            Org.per_name = st.text_input("Contact Person", value=Org.per_name or "")
            Org.survey_name = st.text_input("Survey Type", value=Org.survey_name or "")
            Org.survey_link = st.text_input("Survey Link", value=Org.survey_link or "")
            Org.subject = st.text_input("Email Subject", value=Org.subject or "Your Survey Invitation")
            st.form_submit_button("💾 Save Configuration")

    # Participant Management
    with st.sidebar.expander("👥 Participant Management"):
        with st.form("user_form", clear_on_submit=True):
            name = st.text_input("Name")
            email = st.text_input("Email")
            age = st.number_input("Age", 18, 100)
            if st.form_submit_button("➕ Add Participant"):
                add_user(name, email, age)
        
        uploaded_file = st.file_uploader("📁 Bulk Upload CSV", type=["csv"])
        if uploaded_file:
            process_csv(uploaded_file)

    # Main Interface
    st.title("📅 Automated Survey Scheduling Pro")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.expander("⏰ Scheduling Configuration"):
            scheduling_time = st.radio("Schedule Type:", 
                                      ["Immediate", "Date", "Weekly", "Recurrent"],
                                      horizontal=True)
            handle_scheduling(scheduling_time)
        
        if st.button("🚀 Launch Survey Campaign", use_container_width=True):
            from main import launch_campaign
            launch_campaign()

    with col2:
        with st.expander("📊 Participant Overview"):
            display_user_table()

def add_user(name, email, age):
    try:
        session = Session()
        user = User(name=name, email=email, age=age)
        session.add(user)
        session.commit()
        st.success("✅ Participant added successfully!")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
    finally:
        session.close()

def process_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        required_cols = ['name', 'email', 'age']
        if all(col in df.columns for col in required_cols):
            df.to_sql('users', engine, if_exists='append', index=False)
            st.success(f"✅ Added {len(df)} participants successfully!")
        else:
            st.error("❌ CSV must contain columns: name, email, age")
    except Exception as e:
        st.error(f"❌ CSV Error: {str(e)}")

def handle_scheduling(schedule_type):
    if schedule_type == "Date":
        Schedule.date = st.date_input("Select Date")
        Schedule.time = st.time_input("Select Time")
    elif schedule_type == "Weekly":
        Schedule.days = st.multiselect("Select Days", 
                                     ["Monday", "Tuesday", "Wednesday", 
                                      "Thursday", "Friday", "Saturday", "Sunday"])
    elif schedule_type == "Recurrent":
        Schedule.frequency = st.selectbox("Frequency", 
                                       ["Daily", "Weekly", "Monthly"])
    else:
        Schedule.time = datetime.now()

def display_user_table():
    session = Session()
    try:
        users = session.query(User).all()
        if users:
            df = pd.DataFrame([(u.name, u.email, u.age, u.status, u.created_at) for u in users],
                            columns=["Name", "Email", "Age", "Status", "Added On"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("ℹ️ No participants added yet")
    finally:
        session.close()