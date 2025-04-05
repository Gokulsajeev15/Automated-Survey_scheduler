import os
import time
import threading
import schedule
import base64
from datetime import datetime, timedelta
from email.message import EmailMessage
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from database import User, Session, engine
from models import Org, Schedule
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

# Initialize OpenAI Client (optional, can be skipped for now)
client = OpenAI(api_key=st.secrets.get("openai", {}).get("api_key", ""))

# Gmail Service Setup
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

def test_gmail_connection(service):
    """Test connection to Gmail API."""
    try:
        profile = service.users().getProfile(userId='me').execute()
        st.success(f"✅ Connected to Gmail as: {profile['emailAddress']}")
        return True
    except Exception as e:
        st.error(f"❌ Gmail Connection Error: {str(e)}")
        return False

def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(
                {
                    "web": {
                        "client_id": st.secrets["gmail"]["client_id"],
                        "client_secret": st.secrets["gmail"]["client_secret"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": st.secrets["gmail"]["redirect_uris"]
                    }
                },
                scopes=SCOPES
            )
            creds = flow.run_local_server(port=8080, prompt='consent')  # Correct placement
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
    
    # Verify refresh_token exists
    if not creds.refresh_token:
        st.error("❌ Refresh token missing. Please re-authenticate.")
        return None
    
    return build('gmail', 'v1', credentials=creds)

def generate_email_content(name):
    """Generate email content using OpenAI or fallback to a template."""
    if client.api_key:
        prompt = f"""
        Create a professional survey invitation email for {name} regarding {Org.survey_name}.
        Organization: {Org.org_name}
        Contact Person: {Org.per_name}
        Survey Link: {Org.survey_link}
        
        Requirements:
        - Personalized greeting
        - Clear purpose statement
        - Time commitment estimate
        - Deadline if applicable
        - Professional closing
        - Mobile-friendly formatting
        """
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    else:
        # Fallback template
        return f"""
        Dear {name},
        
        We would appreciate your feedback on our recent {Org.survey_name}.
        Please complete the survey: {Org.survey_link}
        
        Thank you,
        {Org.per_name}
        {Org.org_name}
        """

def send_email(service, receiver, subject, body):
    """Send an email using Gmail API."""
    try:
        message = EmailMessage()
        message.set_content(body)
        message['To'] = receiver
        message['From'] = ""  # Replace with your email
        message['Subject'] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Debug: Print email details
        print(f"Sending email to: {receiver}")
        print(f"Subject: {subject}")
        print(f"Body: {body[:100]}...")  # Print first 100 chars of body
        
        # Send email
        result = service.users().messages().send(
            userId="me",
            body={'raw': encoded_message}
        ).execute()
        
        print(f"✅ Email sent successfully! Message ID: {result['id']}")
        return True
    except Exception as e:
        print(f"❌ Email Error Details: {str(e)}")
        st.error(f"❌ Email Error: {str(e)}")
        return False

def schedule_emails(emails_data):
    """Schedule emails based on user preferences."""
    service = get_gmail_service()
    if not service:
        return
    
    session = Session()
    try:
        for receiver, subject, body in emails_data:
            if Schedule.date and Schedule.time:
                scheduled_time = datetime.combine(Schedule.date, Schedule.time)
                delay = (scheduled_time - datetime.now()).total_seconds()
                if delay > 0:
                    schedule.every(delay).seconds.do(
                        send_email, service, receiver, subject, body
                    ).tag('single')
            
            if Schedule.days:
                for day in Schedule.days:
                    schedule.every().weekday.at("09:00").do(
                        send_email, service, receiver, subject, body
                    ).tag('recurring')
            
            user = session.query(User).filter_by(email=receiver).first()
            if user:
                user.status = "scheduled"
                user.scheduled_at = datetime.now()
        
        session.commit()
        
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(1)
        
        threading.Thread(target=run_scheduler, daemon=True).start()
        
    except Exception as e:
        session.rollback()
        st.error(f"❌ Scheduling Error: {str(e)}")
    finally:
        session.close()

def reset_user_status(email):
    """Reset the status of a specific user to 'pending'."""
    session = Session()
    try:
        user = session.query(User).filter_by(email=email).first()
        if user:
            user.status = 'pending'
            session.commit()
            st.success(f"✅ Status reset to 'pending' for {email}")
        else:
            st.warning(f"⚠️ User with email {email} not found")
    except Exception as e:
        st.error(f"❌ Error resetting status: {str(e)}")
    finally:
        session.close()

def launch_campaign():
    """Launch the email campaign."""
    session = Session()
    try:
        # Get all users regardless of status
        users = session.query(User).all()
        if not users:
            st.warning("⚠️ No participants found!")
            return
        
        emails_data = []
        progress_bar = st.progress(0)
        total_users = len(users)
        
        service = get_gmail_service()
        if not service:
            return
        
        for i, user in enumerate(users):
            try:
                body = generate_email_content(user.name)
                success = send_email(service, user.email, Org.subject, body)
                
                if success:
                    # Update status and timestamp
                    user.status = 'sent'
                    user.scheduled_at = datetime.now()
                    emails_data.append((user.email, Org.subject, body))
                    st.success(f"✅ Email sent to {user.email}")
                else:
                    user.status = 'failed'
                
                session.commit()
                progress_bar.progress((i + 1) / total_users)
                
            except Exception as e:
                st.error(f"❌ Failed for {user.email}: {str(e)}")
                session.rollback()
        
        st.success(f"🎉 Campaign completed! {len(emails_data)}/{len(users)} emails sent")
        
    except Exception as e:
        st.error(f"❌ Campaign Error: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    from __init__ import main
    main()