from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.exporter import export_filename, fetch_lead_rows, leads_to_xlsx_bytes

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/leads.xlsx")
def export_leads_xlsx(db: Session = Depends(get_db)) -> Response:
    rows = fetch_lead_rows(db)
    content = leads_to_xlsx_bytes(rows)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{export_filename("xlsx")}"'},
    )
