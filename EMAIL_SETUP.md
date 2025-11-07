# Email Automation Setup Guide

## Overview
The GL Reconciliation system sends automated emails at 5 key workflow stages using Mailjet transactional API.

## Email Flow

1. **CSV Upload → Maker**  
   When a CSV is uploaded, the maker receives a notification email.

2. **Maker Submit → Reviewer**  
   When maker submits GLs for review, the reviewer receives an email.

3. **Reviewer Approve → Business FC**  
   When reviewer completes review, Business FC receives an email.

4. **FC Approve → CFO**  
   When Business FC approves, CFO receives an email.

5. **CFO Final Approval → Maker**  
   When CFO gives final approval, maker receives a confirmation email.

## Recipients (Configured)

- **Maker/User**: padmnabhtewari@gmail.com
- **Reviewer**: deveshmirchandanibrother@gmail.com
- **Business FC**: dmirchandani01@gmail.com
- **CFO**: deveshmirchandani123@gmail.com

## Required Environment Variables

Before running the application, set these environment variables in PowerShell:

```powershell
$env:MAILJET_API_KEY = "your_public_api_key"
$env:MAILJET_API_SECRET = "your_private_api_key"
$env:MAILJET_SENDER_EMAIL = "no-reply@yourdomain.com"
$env:MAILJET_SENDER_NAME = "GL Reconciliation"
```

### Getting Mailjet Credentials

1. Sign up at [https://www.mailjet.com](https://www.mailjet.com)
2. Navigate to Account Settings → API Keys
3. Create or copy your API Key (public) and Secret Key (private)
4. **Important**: Verify your sender email in Mailjet dashboard before sending

### Security Notes

- **Never commit API keys to source control**
- Rotate keys immediately if accidentally exposed
- Use environment variables or a secrets manager
- For production, use a verified domain sender

## Testing Email Setup

Test the email system without going through the full workflow:

```powershell
# Set env vars first (see above)
python -c "from mailjet_mailer import send_csv_uploaded_to_maker; print(send_csv_uploaded_to_maker('test'))"
```

Expected output: `(200, {...})` or `(201, {...})`

## Troubleshooting

### Error: "Mailjet credentials missing"
- Ensure all 4 environment variables are set in the same PowerShell session where you run Streamlit
- Check for typos in variable names

### Email not received
- Verify sender email is validated in Mailjet dashboard
- Check spam/junk folder
- Verify recipient email addresses in `mailjet_mailer.py`
- Check Mailjet dashboard for delivery logs

### Status code != 200/201
- Review the response JSON for error details
- Common issues: invalid sender, rate limits, invalid recipient format

## Email Content Customization

Email templates are defined in `mailjet_mailer.py`. To customize:

1. Open `mailjet_mailer.py`
2. Edit the HTML content in functions like `send_csv_uploaded_to_maker()`
3. Test changes with a single send before deploying

## Production Recommendations

- Use Mailjet templates (create in Mailjet dashboard, reference by template ID)
- Implement an email queue table for retry logic
- Monitor send rates and request higher quotas if needed
- Set up SPF/DKIM for your domain to improve deliverability
- Add email logging to database for audit trail

## Quick Start

1. Install dependency:
   ```powershell
   pip install mailjet-rest
   ```

2. Set environment variables (see above)

3. Run Streamlit:
   ```powershell
   streamlit run app.py
   ```

4. Upload a CSV → emails will be sent automatically at each workflow stage

## Contact

For issues or questions about email configuration, contact the system administrator.
