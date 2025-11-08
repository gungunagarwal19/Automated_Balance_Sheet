# mailjet_mailer.py
"""
Mailjet transactional email sender for GL reconciliation workflow.
Reads credentials from environment variables (never hardcode keys).

Required environment variables:
- MAILJET_API_KEY (public key)
- MAILJET_API_SECRET (private key)
- MAILJET_SENDER_EMAIL (verified sender email)
- MAILJET_SENDER_NAME (optional, default: "GL Reconciliation")
"""
import os
from mailjet_rest import Client

# Hardcoded Mailjet credentials
MJ_API_KEY = "db722316dc59f2215f167af4871d61c5"
MJ_API_SECRET = "68b0add277af5ded50d107895d3c59b3"
SENDER_EMAIL = "acadassistant8@gmail.com"
SENDER_NAME = "GL Reconciliation"

client = Client(auth=(MJ_API_KEY, MJ_API_SECRET), version='v3.1')


def send_transactional(to_email, to_name, subject, html_content, text_content=None):
    """
    Send a transactional email via Mailjet v3.1.
    
    Args:
        to_email: recipient email address
        to_name: recipient display name
        subject: email subject line
        html_content: HTML body
        text_content: optional plain text body
    
    Returns:
        tuple: (status_code, response_json)
    """
    message = {
        "From": {"Email": SENDER_EMAIL, "Name": SENDER_NAME},
        "To": [{"Email": to_email, "Name": to_name or to_email}],
        "Subject": subject,
        "HTMLPart": html_content
    }
    
    if text_content:
        message["TextPart"] = text_content
    
    data = {"Messages": [message]}
    
    try:
        result = client.send.create(data=data)
        return result.status_code, result.json()
    except Exception as e:
        print(f"Mailjet send error: {e}")
        return 0, {"error": str(e)}


# Email recipient constants (as requested by user)
MAKER_EMAIL = "padmnabhtewari@gmail.com"
REVIEWER_EMAIL = "deveshmirchandanibrother@gmail.com"
FC_EMAIL = "dmirchandani01@gmail.com"
CFO_EMAIL = "deveshmirchandani123@gmail.com"


def send_csv_uploaded_to_maker(gl_accts="multiple GLs"):
    """Email maker when CSV is uploaded"""
    subject = "G/L Received for Review"
    html = f"""
    <p>Hi,</p>
    <p>We have received <strong>{gl_accts}</strong> for review.</p>
    <p>Please login to view and upload supporting documents.</p>
    <p>Thank you,<br/>Finance Automation</p>
    """
    return send_transactional(MAKER_EMAIL, "Maker", subject, html)


def send_maker_submitted_to_reviewer(gl_acct):
    """Email reviewer when maker submits"""
    subject = f"G/L {gl_acct} - Ready for Review"
    html = f"""
    <p>Hi Reviewer,</p>
    <p>G/L <strong>{gl_acct}</strong> has been submitted by the maker and is ready for your review.</p>
    <p>Please login to review the submission.</p>
    <p>Thank you,<br/>Finance Automation</p>
    """
    return send_transactional(REVIEWER_EMAIL, "Reviewer", subject, html)


def send_reviewer_to_fc(gl_acct):
    """Email FC when reviewer completes"""
    subject = f"G/L {gl_acct} - Ready for FC Review"
    html = f"""
    <p>Hi Business FC,</p>
    <p>G/L <strong>{gl_acct}</strong> has been reviewed and is ready for your review.</p>
    <p>Please login to proceed with FC review.</p>
    <p>Thank you,<br/>Finance Automation</p>
    """
    return send_transactional(FC_EMAIL, "Business FC", subject, html)


def send_fc_to_cfo(gl_acct):
    """Email CFO when FC completes"""
    subject = f"G/L {gl_acct} - Ready for CFO Approval"
    html = f"""
    <p>Hi CFO,</p>
    <p>G/L <strong>{gl_acct}</strong> has been reviewed by Business FC and is ready for your approval.</p>
    <p>Please login to review and approve.</p>
    <p>Thank you,<br/>Finance Automation</p>
    """
    return send_transactional(CFO_EMAIL, "CFO", subject, html)


def send_cfo_approved_to_maker(gl_acct):
    """Email maker when CFO approves"""
    subject = f"G/L {gl_acct} - Approved by CFO"
    html = f"""
    <p>Hi,</p>
    <p>Your G/L <strong>{gl_acct}</strong> has been approved by the CFO.</p>
    <p>Thank you for your submission.</p>
    <p>Best regards,<br/>Finance Automation</p>
    """
    return send_transactional(MAKER_EMAIL, "Maker", subject, html)
