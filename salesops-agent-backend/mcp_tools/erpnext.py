import json
import httpx
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


# ── Per-user credentials ────────────────────────────────────────────────────
# Every function takes a ``creds`` (core.user_config.ResolvedIntegration) holding
# the caller's own ERPNext credentials. Without it the tool returns a
# "not configured" result — there is no shared instance to fall back to.


def _erp_creds(creds: Any = None) -> tuple[str, str]:
    """Return (base_url, api_token) from the caller's own configuration.

    There is no environment fallback — a caller without credentials gets
    ("", ""), and every tool turns that into a "not configured" result.
    """
    if creds is None:
        return "", ""
    return creds.get("base_url"), creds.get("api_token")


def _erp_headers(token: str, *, json_body: bool = False) -> Dict[str, str]:
    headers = {"Authorization": f"token {token}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _erp_unconfigured() -> Dict[str, Any]:
    """ERPNext is optional — never raise, return a reason the caller can show."""
    return {
        "status": "error",
        "reason": "not_configured",
        "message": "ERPNext is not configured. Add it in Settings -> Integrations.",
    }


async def ping_erpnext(creds: Any = None) -> Dict[str, Any]:
    """Verify credentials by requesting a single Lead. Used by the settings test."""
    base_url, token = _erp_creds(creds)
    if not base_url or not token:
        return {"success": False, "message": "ERPNext is not configured."}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/resource/Lead",
                params={"limit_page_length": 1},
                headers=_erp_headers(token),
                timeout=10.0,
            )
        if response.status_code == 401 or response.status_code == 403:
            return {"success": False, "message": "Authentication failed - check the API token."}
        response.raise_for_status()
        return {"success": True, "message": "Connected to ERPNext."}
    except httpx.HTTPStatusError as exc:
        return {"success": False, "message": f"ERPNext returned HTTP {exc.response.status_code}."}
    except Exception as exc:
        return {"success": False, "message": f"Connection failed: {type(exc).__name__}"}


class LeadQuotationItem(BaseModel):
    item: str
    qty: int
    rate: float
    business_purpose: str
    list_of_modules: str

class CreateLeadInput(BaseModel):
    first_name: str
    mobile_no: str
    email_id: str
    docstatus: int = 1
    lead_quot_ct: List[LeadQuotationItem] = []

async def create_erpnext_lead(
    input_data: CreateLeadInput, creds: Any = None
) -> Dict[str, Any]:
    """Creates a lead in ERPNext."""
    base_url, token = _erp_creds(creds)
    if not base_url or not token:
        return _erp_unconfigured()

    payload = input_data.model_dump()
    headers = _erp_headers(token, json_body=True)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/resource/Lead",
                json=payload,
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()
            return {"status": "success", "data": response.json().get("data", {})}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"HTTP error occurred: {e}", "details": e.response.text}
        except Exception as e:
            return {"status": "error", "message": f"An error occurred: {str(e)}"}

class ReadLeadInput(BaseModel):
    lead_id: str


class UpdateLeadInput(BaseModel):
    lead_id: str
    status: Optional[str] = None
    lead_name: Optional[str] = None
    notes: Optional[str] = None
    phone: Optional[str] = None
    email_id: Optional[str] = None


class AnalyzeCrmInput(BaseModel):
    doctype: str = "Lead"
    filters: Optional[Dict[str, Any]] = None
    fields: List[str] = ["name", "lead_name", "status", "source", "creation"]
    limit: int = 20
    limit_start: int = 0
    order_by: str = "creation desc"


async def read_erpnext_lead(
    input_data: ReadLeadInput, creds: Any = None
) -> Dict[str, Any]:
    """Reads a single lead from ERPNext by its Lead ID."""
    base_url, token = _erp_creds(creds)
    if not base_url or not token:
        return _erp_unconfigured()
    headers = _erp_headers(token)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{base_url}/api/resource/Lead/{input_data.lead_id}",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return {"status": "success", "data": response.json().get("data", {})}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"HTTP error: {e}", "details": e.response.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def update_erpnext_lead(
    input_data: UpdateLeadInput, creds: Any = None
) -> Dict[str, Any]:
    """Updates an existing lead in ERPNext."""
    base_url, token = _erp_creds(creds)
    if not base_url or not token:
        return _erp_unconfigured()

    update_fields = input_data.model_dump(
        exclude={"lead_id"},
        exclude_none=True,
    )
    headers = _erp_headers(token, json_body=True)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{base_url}/api/resource/Lead/{input_data.lead_id}",
                json=update_fields,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return {"status": "success", "data": response.json().get("data", {})}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"HTTP error: {e}", "details": e.response.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def analyze_crm_data(
    input_data: AnalyzeCrmInput, creds: Any = None
) -> Dict[str, Any]:
    """Fetches and summarises CRM records (Leads, Opportunities, etc.)."""
    base_url, token = _erp_creds(creds)
    if not base_url or not token:
        return _erp_unconfigured()
    headers = _erp_headers(token)
    params: Dict[str, Any] = {
        "fields": json.dumps(input_data.fields),
        "limit_page_length": input_data.limit,
        "limit_start": input_data.limit_start,
        "order_by": input_data.order_by,
    }
    if input_data.filters:
        params["filters"] = json.dumps(input_data.filters)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{base_url}/api/resource/{input_data.doctype}",
                params=params,
                headers=headers,
                timeout=15.0,
            )
            response.raise_for_status()
            records = response.json().get("data", [])
            return {
                "status": "success",
                "total_records": len(records),
                "data": records,
            }
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"HTTP error: {e}", "details": e.response.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}
