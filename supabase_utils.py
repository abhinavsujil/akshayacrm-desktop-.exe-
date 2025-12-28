# supabase_utils.py
from __future__ import annotations

import os
import re
import requests
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

# ---------------- Configuration ----------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://exjmniefzgytfvbnbqct.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV4am1uaWVmemd5dGZ2Ym5icWN0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIyMjM5MjAsImV4cCI6MjA2Nzc5OTkyMH0.U0m52fIJvtiwfrz11VHtow2sHHK3cNxiLu6nXEFcQzU",
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    # We commonly want returned rows for PATCH/POST
    "Prefer": "return=representation",
}

DEFAULT_TIMEOUT = 12
_DEBUG = os.environ.get("DEBUG_SUPABASE", "0").lower() in ("1", "true", "yes")


def _debug(*args, **kwargs):
    if _DEBUG:
        print("[supabase_utils DEBUG]", *args, **kwargs)


# ---------------- HTTP helpers ----------------
def _safe_get(url: str, params: Optional[dict] = None) -> requests.Response:
    return requests.get(url, headers=HEADERS, params=params, timeout=DEFAULT_TIMEOUT)


def supabase_get(table: str, filter_query: Optional[str] = None, select: str = "*") -> requests.Response:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params: Dict[str, Any] = {"select": select}
    if filter_query:
        # filter_query is expected like "status=eq.pending&other=..."
        for part in str(filter_query).split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k in params:
                    if isinstance(params[k], list):
                        params[k].append(v)
                    else:
                        params[k] = [params[k], v]
                else:
                    params[k] = v
    _debug("GET", url, "params=", params)
    try:
        resp = _safe_get(url, params=params)
    except Exception as e:
        raise RuntimeError(f"GET failed {url}: {e}") from e
    _debug("GET status", getattr(resp, "status_code", None))
    return resp


def supabase_post(table: str, data: dict) -> requests.Response:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    _debug("POST", url, "data=", data)
    try:
        resp = requests.post(url, headers=HEADERS, json=data, timeout=DEFAULT_TIMEOUT)
    except Exception as e:
        raise RuntimeError(f"POST failed {url}: {e}") from e
    _debug("POST status", getattr(resp, "status_code", None))
    return resp


def supabase_patch(table: str, filter_query: str, data: dict) -> requests.Response:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params: Dict[str, Any] = {}
    for part in str(filter_query).split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    _debug("PATCH", url, "params=", params, "data=", data)
    try:
        resp = requests.patch(url, headers=HEADERS, params=params, json=data, timeout=DEFAULT_TIMEOUT)
    except Exception as e:
        raise RuntimeError(f"PATCH failed {url}: {e}") from e
    _debug("PATCH status", getattr(resp, "status_code", None))
    return resp


def supabase_delete(table: str, filter_query: Optional[str]) -> requests.Response:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params: Dict[str, Any] = {}
    if filter_query:
        for part in str(filter_query).split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
    _debug("DELETE", url, "params=", params)
    try:
        resp = requests.delete(url, headers=HEADERS, params=params, timeout=DEFAULT_TIMEOUT)
    except Exception as e:
        raise RuntimeError(f"DELETE failed {url}: {e}") from e
    _debug("DELETE status", getattr(resp, "status_code", None))
    return resp


# ---------------- Timestamp / normalization helpers ----------------
def _parse_dt(raw_ts: Any) -> datetime:
    if raw_ts is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(raw_ts, datetime):
        dt = raw_ts
    else:
        s = str(raw_ts).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            try:
                dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            except Exception:
                if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
                    return datetime.fromisoformat(s + "T00:00:00+00:00")
                return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return dt.astimezone(timezone.utc)
    except Exception:
        return dt.replace(tzinfo=timezone.utc)


def _to_iso(raw_ts: Any) -> str:
    if not raw_ts:
        return ""
    try:
        dt = _parse_dt(raw_ts)
        return dt.isoformat()
    except Exception:
        return str(raw_ts)


def _normalize_log(raw_log: Any) -> dict:
    """
    Ensure log dict has fields used by UI:
      id, staff_id, name, phone, timestamp (ISO), remarks, _raw
    """
    if not isinstance(raw_log, dict):
        return {"id": "", "staff_id": "", "name": "", "phone": "", "timestamp": "", "remarks": "", "_raw": raw_log or {}}

    id_val = raw_log.get("id") or raw_log.get("log_id") or ""
    staff_id = raw_log.get("staff_id") or raw_log.get("staff") or raw_log.get("created_by") or ""
    name = raw_log.get("name") or raw_log.get("customer_name") or raw_log.get("customer") or ""
    phone = raw_log.get("phone") or raw_log.get("mobile") or raw_log.get("contact") or ""
    ts_raw = raw_log.get("timestamp") or raw_log.get("created_at") or ""
    remarks = raw_log.get("remarks") or raw_log.get("notes") or raw_log.get("note") or ""
    return {
        "id": id_val,
        "staff_id": staff_id,
        "name": name,
        "phone": phone,
        "timestamp": _to_iso(ts_raw) if ts_raw else "",
        "remarks": remarks,
        "_raw": raw_log,
    }


def _normalize_service(raw_s: Any) -> dict:
    """
    Ensure service dict has: id, log_id, service, amount, status, payments, _raw
    """
    if not isinstance(raw_s, dict):
        return {"id": "", "log_id": "", "service": "", "amount": None, "status": "", "payments": [], "_raw": raw_s or {}}
    amt = raw_s.get("amount")
    if amt in (None, ""):
        amt = None
    payments = raw_s.get("payments") or raw_s.get("payment") or []
    return {
        "id": raw_s.get("id"),
        "log_id": raw_s.get("log_id"),
        "service": raw_s.get("service"),
        "amount": amt,
        "status": raw_s.get("status"),
        "variant_id": raw_s.get("variant_id"),
        "payments": payments,
        "_raw": raw_s,
    }


# ---------------- logs + services + payments ----------------
def get_all_logs_with_services() -> List[dict]:
    """
    Return: [ { "log": normalized_log, "services": [ normalized_service, ... ] }, ... ]
    Same behaviour as your old helper, but with normalized shapes.
    """
    try:
        resp = supabase_get("logs", select="*,services(*,payments(*))")
    except Exception as e:
        _debug("joined logs get failed:", e)
        resp = None

    rows: List[dict] = []
    if resp is not None and getattr(resp, "status_code", None) == 200:
        try:
            rows = resp.json() or []
        except Exception as e:
            _debug("json parse joined logs failed:", e)
            rows = []
    else:
        try:
            resp2 = supabase_get("logs", select="*,services(*)")
            if getattr(resp2, "status_code", None) == 200:
                rows = resp2.json() or []
            else:
                r_logs = supabase_get("logs", select="*")
                r_services = supabase_get("services", select="*")
                logs_list = r_logs.json() or [] if getattr(r_logs, "status_code", None) == 200 else []
                services_list = r_services.json() or [] if getattr(r_services, "status_code", None) == 200 else []
                services_by_log: Dict[str, List[dict]] = {}
                for s in services_list:
                    lid = s.get("log_id")
                    services_by_log.setdefault(str(lid), []).append(s)
                rows = []
                for lg in logs_list:
                    rows.append({**lg, "services": services_by_log.get(str(lg.get("id")), [])})
        except Exception as e:
            _debug("fallback join failed:", e)
            rows = []

    results: List[dict] = []
    for r in rows:
        raw_services = r.get("services") or []
        log_raw = {k: v for k, v in r.items() if k != "services"}
        normalized_log = _normalize_log(log_raw)
        normalized_services = [_normalize_service(s) for s in raw_services]
        results.append({"log": normalized_log, "services": normalized_services})
    return results


# ---------------- Staff logs (for staff dashboard) ----------------
def get_logs_for_staff(staff_id: str, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[dict]:
    """
    Same contract as your original helper: returns
       [ { "log": {...}, "services": [...] }, ... ]
    filtered by staff_id and optional date range.
    """
    filters = [f"staff_id=eq.{staff_id}"]
    if date_from:
        filters.append(f"timestamp=gte.{date_from}")
    if date_to:
        filters.append(f"timestamp=lte.{date_to}")

    filter_query = "&".join(filters)

    try:
        resp = supabase_get("logs", filter_query=filter_query, select="*,services(*,payments(*))")
    except Exception as e:
        _debug("get_logs_for_staff error:", e)
        return []

    if getattr(resp, "status_code", None) != 200:
        _debug("get_logs_for_staff status", getattr(resp, "status_code", None), getattr(resp, "text", ""))
        return []

    try:
        rows = resp.json() or []
    except Exception as e:
        _debug("get_logs_for_staff json error:", e)
        return []

    result: List[dict] = []
    for r in rows:
        raw_services = r.get("services") or []
        log_raw = {k: v for k, v in r.items() if k != "services"}
        result.append({"log": _normalize_log(log_raw), "services": [_normalize_service(s) for s in raw_services]})
    return result


# ---------------- Pending services join (Verify Services) ----------------
def _pending_services_fallback() -> List[dict]:
    """
    Fallback: get *all* services joined with logs and filter for pending in Python.
    Case-insensitive comparison so 'Pending' / 'PENDING' also works.
    """
    out: List[dict] = []
    try:
        r_services = supabase_get("services", select="*,log:logs(*)")
    except Exception as e:
        _debug("pending services fallback fetch error", e)
        return out

    if getattr(r_services, "status_code", None) != 200:
        _debug("pending services fallback bad status", getattr(r_services, "status_code", None))
        return out

    try:
        svc_rows = r_services.json() or []
    except Exception as e:
        _debug("pending services fallback json error", e)
        return out

    def is_pending(s: dict) -> bool:
        return str(s.get("status") or "").strip().lower() == "pending"

    for s in svc_rows:
        if not is_pending(s):
            continue
        raw_log = s.get("log") or {}
        svc = _normalize_service({k: v for k, v in s.items() if k != "log"})
        log = _normalize_log(raw_log)
        out.append({"service": svc, "log": log})
    return out


def get_pending_services_with_logs(include_suggestions: bool = True) -> List[dict]:
    """
    Returns pending service rows joined with logs.

    Behaviour:
      - from services: rows whose status (case-insensitive) is 'pending'
      - from service_suggestions: rows whose status is 'pending' OR empty/NULL
        (staff just typed a new service, DB might not set status yet)
    """
    combined: List[dict] = []

    # 1) base services (no status filter in SQL; filter locally)
    try:
        resp = supabase_get("services", select="*,log:logs(*)")
    except Exception as e:
        _debug("pending services joined get failed:", e)
        return _pending_services_fallback()

    if getattr(resp, "status_code", None) != 200:
        _debug("pending services joined bad status", getattr(resp, "status_code", None))
        return _pending_services_fallback()

    try:
        svc_rows = resp.json() or []
    except Exception as e:
        _debug("pending services json error:", e)
        return _pending_services_fallback()

    def is_pending_status(val: Any) -> bool:
        return str(val or "").strip().lower() == "pending"

    # If some rows have no joined log, get all logs once and join in Python
    needs_lookup = any(s.get("log") is None for s in svc_rows)
    logs_by_id: Dict[str, dict] = {}
    if needs_lookup:
        try:
            r_logs = supabase_get("logs", select="*")
            if getattr(r_logs, "status_code", None) == 200:
                for lg in r_logs.json() or []:
                    logs_by_id[str(lg.get("id"))] = lg
        except Exception as e:
            _debug("pending services logs lookup failed:", e)

    # services table → only status == pending
    for s in svc_rows:
        if not is_pending_status(s.get("status")):
            continue
        raw_log = s.get("log") or {}
        if not raw_log:
            lid = s.get("log_id")
            if lid:
                raw_log = logs_by_id.get(str(lid)) or {}
        svc_norm = _normalize_service({k: v for k, v in s.items() if k != "log"})
        log_norm = _normalize_log(raw_log)
        combined.append({"service": svc_norm, "log": log_norm})

    # 2) include suggestions if requested
    if include_suggestions:
        try:
            r_sugg = supabase_get("service_suggestions", select="*")
        except Exception as e:
            _debug("service_suggestions fetch error", e)
            r_sugg = None

        sugg_rows: List[dict] = []
        if r_sugg is not None and getattr(r_sugg, "status_code", None) == 200:
            try:
                sugg_rows = r_sugg.json() or []
            except Exception as e:
                _debug("service_suggestions json error", e)
                sugg_rows = []

        for r in sugg_rows:
            status_val = r.get("status")
            # Treat NULL/"" as pending for suggestions (new staff entries)
            if status_val not in (None, "") and not is_pending_status(status_val):
                continue

            raw_id = r.get("id")
            sugg_id = f"sugg:{raw_id}" if raw_id else f"sugg:{r.get('service')}"
            svc = {
                "id": sugg_id,
                "log_id": None,
                "service": r.get("service"),
                "amount": None,
                "status": status_val or "pending",
                "payments": [],
                "_raw": r,
            }
            ts = r.get("suggested_at") or r.get("created_at") or datetime.utcnow().isoformat()
            log = {
                "id": None,
                "staff_id": r.get("suggested_by"),
                "name": f"Suggested by: {r.get('suggested_by')}",
                "phone": "",
                "timestamp": _to_iso(ts),
                "remarks": "",
                "_raw": r,
            }
            combined.append({"service": _normalize_service(svc), "log": _normalize_log(log)})

    # no dedupe: show every pending/suggested row
    return combined



# ---------------- Approved service names / count ----------------
def get_approved_service_names() -> List[str]:
    """
    Distinct approved service names.

    Same logic as old version, but status filter is done in Python,
    case-insensitive (so 'Approved' also works).
    """
    try:
        resp = supabase_get("services", select="service,status")
    except Exception as e:
        _debug("get_approved_service_names error:", e)
        return []

    if getattr(resp, "status_code", None) != 200:
        _debug("get_approved_service_names bad status", getattr(resp, "status_code", None))
        return []

    try:
        rows = resp.json() or []
    except Exception as e:
        _debug("get_approved_service_names json error", e)
        return []

    names = {
        r.get("service")
        for r in rows
        if r.get("service") and str(r.get("status") or "").strip().lower() == "approved"
    }
    return sorted(names)


def get_total_service_types() -> int:
    return len(get_approved_service_names())


# ---------------- Dashboard stats ----------------
def get_dashboard_stats() -> dict:
    stats = {"total_logs": 0, "pending_verifications": 0, "total_staff": 0, "total_revenue": 0, "total_base": 0, "total_charge": 0}
    try:
        r_logs = supabase_get("logs", select="id")
        if getattr(r_logs, "status_code", None) == 200:
            stats["total_logs"] = len(r_logs.json() or [])
    except Exception as e:
        _debug("get_dashboard_stats logs error:", e)

    try:
        r_pending = supabase_get("services", select="id,status")
        svc_rows = r_pending.json() or [] if getattr(r_pending, "status_code", None) == 200 else []
        stats["pending_verifications"] = sum(
            1 for r in svc_rows if str(r.get("status") or "").strip().lower() == "pending"
        )
    except Exception as e:
        _debug("get_dashboard_stats pending services error:", e)

    try:
        r_sugg = supabase_get("service_suggestions", select="id,status")
        sugg_rows = r_sugg.json() or [] if getattr(r_sugg, "status_code", None) == 200 else []
        stats["pending_verifications"] += sum(
            1 for r in sugg_rows if str(r.get("status") or "").strip().lower() == "pending"
        )
    except Exception:
        pass

    try:
        r_staff = supabase_get("staff", select="id")
        if getattr(r_staff, "status_code", None) == 200:
            stats["total_staff"] = len(r_staff.json() or [])
    except Exception as e:
        _debug("get_dashboard_stats staff error:", e)

    try:
        r_pay = supabase_get("payments", select="amount,base_amount,service_charge")
        rows = r_pay.json() or [] if getattr(r_pay, "status_code", None) == 200 else []
    except Exception as e:
        _debug("get_dashboard_stats payments error:", e)
        rows = []

    total_revenue = total_base = total_charge = 0.0
    for row in rows:
        try:
            amt = float(row.get("amount") or 0)
        except Exception:
            amt = 0.0
        try:
            base = float(row.get("base_amount") or 0)
        except Exception:
            base = 0.0
        try:
            charge = float(row.get("service_charge") or 0)
        except Exception:
            charge = 0.0
        if amt == 0 and (base or charge):
            amt = base + charge
        total_revenue += amt
        total_base += base
        total_charge += charge
    stats["total_revenue"] = int(total_revenue)
    stats["total_base"] = int(total_base)
    stats["total_charge"] = int(total_charge)
    return stats


# ---------------- Update / delete helpers ----------------
def _split_service_and_suggestion_ids(service_ids: List[str]) -> Tuple[List[str], List[str]]:
    s_ids: List[str] = []
    sug_ids: List[str] = []
    for s in service_ids:
        if not s:
            continue
        if isinstance(s, str) and s.startswith("sugg:"):
            raw = s[len("sugg:") :].strip()
            if raw:
                sug_ids.append(raw)
        else:
            s_ids.append(s)
    return s_ids, sug_ids


def update_service_status(service_ids: List[str] | str, new_status: str) -> bool:
    if not service_ids:
        return False
    if isinstance(service_ids, str):
        service_ids = [service_ids]
    ids = [s for s in service_ids if s]
    if not ids:
        return False
    services_ids, suggestion_ids = _split_service_and_suggestion_ids(ids)
    any_success = False
    ok_all = True

    if services_ids:
        try:
            in_list = ",".join(services_ids)
            filter_q = f"id=in.({in_list})"
            resp = supabase_patch("services", filter_q, {"status": new_status})
            if getattr(resp, "status_code", None) in (200, 204):
                any_success = True
            else:
                _debug("update_service_status services patch failed", getattr(resp, "status_code", None), getattr(resp, "text", ""))
                ok_all = False
        except Exception as e:
            _debug("update_service_status services exception:", e)
            ok_all = False

    if suggestion_ids:
        try:
            in_list = ",".join(suggestion_ids)
            filter_q = f"id=in.({in_list})"
            resp = supabase_patch("service_suggestions", filter_q, {"status": new_status})
            if getattr(resp, "status_code", None) in (200, 204):
                any_success = True
                if new_status.strip().lower() == "approved":
                    try:
                        resp_fetch = supabase_get("service_suggestions", filter_query=f"id=in.({in_list})")
                        if getattr(resp_fetch, "status_code", None) == 200:
                            rows = resp_fetch.json() or []
                            for r in rows:
                                svc_name = r.get("service")
                                if svc_name:
                                    payload = {"service": svc_name, "status": "approved", "amount": None, "log_id": None}
                                    post_resp = supabase_post("services", payload)
                                    if getattr(post_resp, "status_code", None) not in (200, 201):
                                        _debug("warning: failed to insert approved suggestion as service", getattr(post_resp, "status_code", None))
                        else:
                            _debug("warning: could not fetch suggestion rows after approve", getattr(resp_fetch, "status_code", None))
                    except Exception as e:
                        _debug("warning while creating service for approved suggestion:", e)
            else:
                _debug("update_service_status service_suggestions patch failed", getattr(resp, "status_code", None), getattr(resp, "text", ""))
                ok_all = False
        except Exception as e:
            _debug("update_service_status suggestions exception:", e)
            ok_all = False

    return ok_all and any_success


def delete_log(log_id: str) -> bool:
    if not log_id:
        return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/logs"
        params = {"id": f"eq.{log_id}"}
        headers = dict(HEADERS)
        resp = requests.delete(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
        _debug("delete_log status", getattr(resp, "status_code", None))
        return getattr(resp, "status_code", None) in (200, 204)
    except Exception as e:
        _debug("delete_log exception:", e)
        return False


def update_log(log_id: str, payload: dict) -> bool:
    if not log_id or not payload:
        return False
    try:
        resp = supabase_patch("logs", filter_query=f"id=eq.{log_id}", data=payload)
    except Exception as e:
        _debug("update_log patch exception:", e)
        resp = None
    if getattr(resp, "status_code", None) in (200, 204):
        try:
            j = resp.json() if getattr(resp, "text", None) else None
        except Exception:
            j = None
        if isinstance(j, (list, dict)) and j:
            row = j[0] if isinstance(j, list) else j
            for k, v in payload.items():
                if str(row.get(k) or "") != str(v):
                    return False
            return True
        return True
    try:
        url = f"{SUPABASE_URL}/rest/v1/logs"
        params = {"id": f"eq.{log_id}"}
        headers = dict(HEADERS)
        headers["Prefer"] = "return=representation"
        resp2 = requests.patch(url, headers=headers, params=params, json=payload, timeout=DEFAULT_TIMEOUT)
        _debug("update_log fallback status", getattr(resp2, "status_code", None))
        if getattr(resp2, "status_code", None) in (200, 204):
            try:
                j2 = resp2.json() if getattr(resp2, "text", None) else None
            except Exception:
                j2 = None
            if isinstance(j2, (list, dict)) and j2:
                row = j2[0] if isinstance(j2, list) else j2
                for k, v in payload.items():
                    if str(row.get(k) or "") != str(v):
                        return False
                return True
            return True
    except Exception as e:
        _debug("update_log fallback exception", e)
    return False


# ---------------- Documents helpers ----------------
def get_service_documents() -> List[dict]:
    try:
        resp = supabase_get("service_documents", select="*")
        if getattr(resp, "status_code", None) != 200:
            _debug("get_service_documents failed", getattr(resp, "status_code", None))
            return []
        rows = resp.json() or []
    except Exception as e:
        _debug("get_service_documents http error", e)
        return []
    normalized: List[dict] = []
    for r in rows:
        docs = r.get("documents")
        docs_list: List[str] = []
        if docs is None:
            docs_list = []
        elif isinstance(docs, list):
            docs_list = docs
        elif isinstance(docs, str):
            s = docs.strip()
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    docs_list = parsed
                else:
                    docs_list = [str(parsed)]
            except Exception:
                docs_list = [p.strip() for p in s.strip("[]").split(",") if p.strip()]
        else:
            docs_list = [str(docs)]
        normalized.append(
            {
                "id": r.get("id"),
                "service": r.get("service"),
                "documents": docs_list,
                "created_by": r.get("created_by"),
                "created_at": r.get("created_at"),
                "notes": r.get("notes"),
            }
        )
    return normalized


def save_service_documents(service: str, documents: List[str], created_by: Optional[str] = None, notes: Optional[str] = None) -> bool:
    payload = {
        "service": service,
        "documents": documents,
        "created_by": created_by,
        "notes": notes,
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        resp = supabase_post("service_documents", payload)
        return getattr(resp, "status_code", None) in (200, 201)
    except Exception as e:
        _debug("save_service_documents failed", e)
        return False


def save_service_documents_upsert(service: str, documents: List[str], created_by: Optional[str] = None, notes: Optional[str] = None) -> bool:
    if not service:
        return False
    try:
        resp = supabase_get("service_documents", filter_query=f"service=eq.{service}", select="id")
        if getattr(resp, "status_code", None) == 200 and resp.json():
            row = resp.json()[0]
            row_id = row.get("id")
            payload: Dict[str, Any] = {"documents": documents}
            if notes is not None:
                payload["notes"] = notes
            if created_by is not None:
                payload["created_by"] = created_by
            patch = supabase_patch("service_documents", filter_query=f"id=eq.{row_id}", data=payload)
            return getattr(patch, "status_code", None) in (200, 204)
        payload = {
            "service": service,
            "documents": documents,
            "created_by": created_by,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat(),
        }
        resp2 = supabase_post("service_documents", payload)
        return getattr(resp2, "status_code", None) in (200, 201)
    except Exception as e:
        _debug("save_service_documents_upsert exception", e)
        return False


# ---------------- Debug runner ----------------
def _debug_sample():
    _debug("debug sample: logs+services")
    try:
        a = get_all_logs_with_services()
        _debug("logs count:", len(a))
        if a:
            _debug(json.dumps(a[:2], default=str, indent=2)[:3000])
    except Exception as e:
        _debug("sample logs error:", e)
    _debug("debug sample: pending")
    try:
        p = get_pending_services_with_logs(include_suggestions=True)
        _debug("pending count:", len(p))
        if p:
            _debug(json.dumps(p[:3], default=str, indent=2)[:3000])
    except Exception as e:
        _debug("sample pending error:", e)


if __name__ == "__main__":
    _debug("module executed as script - running sample fetch")
    _debug_sample()
