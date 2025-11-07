# sap_connectors.py
from typing import List, Dict

def fetch_company_trial_from_sap(server_cfg: dict, company_code: str) -> List[Dict]:
    """
    Return a list of dicts with keys:
    company_code, gl_account, gl_description, doc_no, posting_date,
    amount, currency, cost_center, profit_center, text, reference
    """
    # TODO: Replace with pyrfc/odata/pyhana etc.
    # Here we return sample rows.
    return [
        {
            "company_code": company_code, "gl_account": "400100",
            "gl_description": "Revenue - Domestic", "doc_no": "900001",
            "posting_date": "2025-11-05", "amount": 125000.0, "currency": "INR",
            "cost_center": "CC100", "profit_center": "PC10",
            "text": "Nov domestic", "reference": "SAP-EX"
        }
    ]
