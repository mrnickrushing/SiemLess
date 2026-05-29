"""Compliance report router."""
import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.compliance import ComplianceReport
from app.services.compliance import compliance_service

router = APIRouter(prefix="/compliance", tags=["compliance"])
logger = logging.getLogger(__name__)

SUPPORTED_FRAMEWORKS = ["pci_dss", "hipaa", "gdpr", "soc2", "nist"]


@router.post("/reports", status_code=status.HTTP_202_ACCEPTED, summary="Generate compliance report")
async def generate_report(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> dict:
    framework = payload.get("framework", "").lower()
    if framework not in SUPPORTED_FRAMEWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported framework. Supported: {SUPPORTED_FRAMEWORKS}",
        )
    params = payload.get("parameters", {})
    report_id = await compliance_service.generate_report(db, framework, params, username)
    return {"report_id": report_id, "status": "pending"}


@router.get("/reports", summary="List compliance reports")
async def list_reports(
    framework: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    from sqlalchemy import func

    query = select(ComplianceReport)
    count_query = select(func.count()).select_from(ComplianceReport)
    if framework:
        query = query.where(ComplianceReport.framework == framework)
        count_query = count_query.where(ComplianceReport.framework == framework)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(ComplianceReport.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    reports = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "framework": r.framework,
                "title": r.title,
                "status": r.status,
                "generated_by": r.generated_by,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ],
    }


@router.get("/reports/{report_id}", summary="Get compliance report")
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(ComplianceReport).where(ComplianceReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": report.id,
        "framework": report.framework,
        "title": report.title,
        "status": report.status,
        "generated_by": report.generated_by,
        "created_at": report.created_at.isoformat(),
        "result_data": report.result_data,
        "error_message": report.error_message,
        "parameters": report.parameters,
    }


@router.get("/reports/{report_id}/download", summary="Download report as CSV")
async def download_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> StreamingResponse:
    result = await db.execute(
        select(ComplianceReport).where(ComplianceReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "completed" or not report.result_data:
        raise HTTPException(status_code=400, detail="Report not yet completed")

    output = io.StringIO()
    writer = csv.writer(output)

    # Flatten the result_data dict into key/value rows
    writer.writerow(["metric", "value"])
    for key, value in report.result_data.items():
        if isinstance(value, dict):
            for subkey, subval in value.items():
                writer.writerow([f"{key}.{subkey}", str(subval)])
        else:
            writer.writerow([key, str(value)])

    output.seek(0)
    filename = f"{report.framework}_{report.id[:8]}.csv"
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
