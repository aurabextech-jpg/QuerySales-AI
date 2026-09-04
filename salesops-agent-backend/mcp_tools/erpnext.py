import json
import httpx
from typing import Dict, Any, List, Optional
from core.config import settings
from pydantic import BaseModel

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

async def create_erpnext_lead(input_data: CreateLeadInput) -> Dict[str, Any]:
    """
    Creates a lead in ERPNext.
    """
    payload = input_data.model_dump()
        
    headers = {
        "Authorization": f"token {settings.ERPNEXT_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.ERPNEXT_BASE_URL}/api/resource/Lead",
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


async def get_chatbot_link(lead_id: str) -> Dict[str, Any]:
    """Fetches the chatbot link/quotation link for a given Lead ID."""
    headers = {
        "Authorization": f"token {settings.ERPNEXT_API_TOKEN}",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.ERPNEXT_BASE_URL}/api/method/education.education.chatbot_api.get_chatbot_link",
                params={"lead_id": lead_id},
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return {"status": "success", "data": response.json().get("message", {})}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"HTTP error occurred: {e}", "details": e.response.text}
        except Exception as e:
            return {"status": "error", "message": f"An error occurred: {str(e)}"}


async def read_erpnext_lead(input_data: ReadLeadInput) -> Dict[str, Any]:
    """Reads a single lead from ERPNext by its Lead ID."""
    headers = {"Authorization": f"token {settings.ERPNEXT_API_TOKEN}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.ERPNEXT_BASE_URL}/api/resource/Lead/{input_data.lead_id}",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return {"status": "success", "data": response.json().get("data", {})}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"HTTP error: {e}", "details": e.response.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def update_erpnext_lead(input_data: UpdateLeadInput) -> Dict[str, Any]:
    """Updates an existing lead in ERPNext."""
    update_fields = input_data.model_dump(
        exclude={"lead_id"},
        exclude_none=True,
    )

    headers = {
        "Authorization": f"token {settings.ERPNEXT_API_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{settings.ERPNEXT_BASE_URL}/api/resource/Lead/{input_data.lead_id}",
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


async def analyze_crm_data(input_data: AnalyzeCrmInput) -> Dict[str, Any]:
    """Fetches and summarises CRM records (Leads, Opportunities, etc.)."""
    headers = {"Authorization": f"token {settings.ERPNEXT_API_TOKEN}"}
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
                f"{settings.ERPNEXT_BASE_URL}/api/resource/{input_data.doctype}",
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
