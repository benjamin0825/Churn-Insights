"""Retention campaigns: live preview, saved campaigns and CSV export."""

from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..campaigns import CampaignParams, customer_table, export_frame, plan
from ..db import get_db
from ..models import Campaign, User
from ..security import current_user
from ..workspace import Workspace
from .common import clean, records, require_scores

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _named(ws: Workspace, rows: list[dict]) -> list[dict]:
    return [{**row, "name": ws.customer_name(row["customer_id"])} for row in rows]
Tier = Literal["high", "medium", "low"]


class PlanIn(BaseModel):
    offer_cost: float = Field(ge=0, le=100000)
    retention_success_rate: float = Field(ge=0, le=1)
    months_of_value: float = Field(gt=0, le=120)
    budget: float | None = Field(default=None, ge=0)
    max_customers: int | None = Field(default=None, ge=1)
    risk_tiers: list[Tier] = Field(default_factory=lambda: ["high", "medium", "low"], min_length=1)
    min_probability: float = Field(default=0.0, ge=0, le=1)

    def params(self) -> CampaignParams:
        return CampaignParams(self.offer_cost, self.retention_success_rate, self.months_of_value, self.budget,
                              self.max_customers, tuple(self.risk_tiers), self.min_probability)


class CampaignIn(PlanIn):
    name: str = Field(min_length=1, max_length=200)


def _campaign_dir(ws: Workspace):
    path = ws.root / "campaigns"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _out(c: Campaign) -> dict:
    return clean({"id": c.id, "name": c.name, "created_at": c.created_at.isoformat(), "model_version": c.model_version,
                  "as_of_week": c.as_of_week, "params": c.params, "summary": c.summary})


@router.post("/preview")
def preview(body: PlanIn, user: User = Depends(current_user)) -> dict:
    ws = Workspace(user.organization_id)
    scores, features, meta = require_scores(ws)
    targets, summary, curve = plan(customer_table(scores, features), body.params())
    return clean({"summary": summary, "curve": curve, "as_of_week": meta["week"],
                  "top_targets": _named(ws, records(export_frame(targets.head(25))))})


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: CampaignIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    ws = Workspace(user.organization_id)
    scores, features, meta = require_scores(ws)
    targets, summary, _ = plan(customer_table(scores, features), body.params())
    campaign = Campaign(organization_id=user.organization_id, name=body.name.strip(), created_by=user.id,
                        model_version=meta["model_version"], as_of_week=meta["week"],
                        params=body.model_dump(exclude={"name"}), summary=summary)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    export_frame(targets).to_csv(_campaign_dir(ws) / f"campaign_{campaign.id:06d}.csv", index=False)
    return _out(campaign)


@router.get("")
def list_campaigns(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = (db.query(Campaign).filter(Campaign.organization_id == user.organization_id)
            .order_by(Campaign.id.desc()).limit(100).all())
    return [_out(c) for c in rows]


def _owned(db: Session, user: User, campaign_id: int) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.organization_id != user.organization_id:
        raise HTTPException(404, "Campaign not found")
    return campaign


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    campaign = _owned(db, user, campaign_id)
    ws = Workspace(user.organization_id)
    path = _campaign_dir(ws) / f"campaign_{campaign.id:06d}.csv"
    preview_rows = _named(ws, records(pd.read_csv(path).head(50))) if path.exists() else []
    return {**_out(campaign), "targets_preview": preview_rows}


@router.get("/{campaign_id}/export")
def export(campaign_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    campaign = _owned(db, user, campaign_id)
    path = _campaign_dir(Workspace(user.organization_id)) / f"campaign_{campaign.id:06d}.csv"
    if not path.exists():
        raise HTTPException(404, "Target list file is missing")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in campaign.name)[:60] or "campaign"
    return Response(path.read_bytes(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{safe}_{campaign.id}.csv"'})


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(campaign_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    campaign = _owned(db, user, campaign_id)
    (_campaign_dir(Workspace(user.organization_id)) / f"campaign_{campaign.id:06d}.csv").unlink(missing_ok=True)
    db.delete(campaign)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
