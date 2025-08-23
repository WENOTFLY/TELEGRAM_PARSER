from __future__ import annotations

"""Routes implementing the AI content pipeline."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openai import OpenAI

from ..models import (
    ContentPackage,
    ContentPackageItem,
    EditorResult,
    ImageBrief,
    MediaAsset,
    User,
)
from .auth import get_current_user, get_db

router = APIRouter(prefix="/v1")


# ----- Pydantic schemas -----


class TransformRequest(BaseModel):
    headline: str
    body_variants: dict
    source_links: List[str] = Field(default_factory=list)
    topic_id: int | None = None
    message_ids: List[int] | None = None
    language: str | None = None
    dek: str | None = None
    key_points: dict | None = None


class TransformResponse(BaseModel):
    id: int
    headline: str
    body_variants: dict
    source_links: List[str]


class ImageBriefRequest(BaseModel):
    editor_result_id: int
    title: str | None = None
    prompt: str
    negative: str | None = None
    size: str | None = None
    variants: int | None = None
    caption: str | None = None
    style_tags: List[str] | None = None


class ImageBriefResponse(BaseModel):
    id: int
    prompt: str


class ImagesRequest(BaseModel):
    image_brief_id: int


class ImagesResponse(BaseModel):
    urls: List[str]


class PackageItemSchema(BaseModel):
    platform: str
    post_time: datetime | None = None
    post_text: dict
    hashtags: List[str] = Field(default_factory=list)
    cta: str | None = None
    image_url: str | None = None


class PackageRequest(BaseModel):
    editor_result_id: int
    items: List[PackageItemSchema]


class PackageResponse(BaseModel):
    id: int


# ----- Routes -----


@router.post("/transform", response_model=TransformResponse)
async def create_transform(
    payload: TransformRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store an editor result produced by the transform step."""
    result = EditorResult(
        user_id=user.id,
        topic_id=payload.topic_id,
        message_ids=payload.message_ids,
        language=payload.language,
        headline=payload.headline,
        dek=payload.dek,
        body_variants=payload.body_variants,
        key_points=payload.key_points,
        source_links=payload.source_links,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return TransformResponse(
        id=result.id,
        headline=result.headline or "",
        body_variants=result.body_variants or {},
        source_links=result.source_links or [],
    )


@router.post("/image-brief", response_model=ImageBriefResponse)
async def create_image_brief(
    payload: ImageBriefRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store an image brief linked to an editor result."""
    result = db.get(EditorResult, payload.editor_result_id)
    if result is None or result.user_id != user.id:
        raise HTTPException(status_code=404, detail="editor result not found")
    brief = ImageBrief(
        editor_result_id=payload.editor_result_id,
        title=payload.title,
        prompt=payload.prompt,
        negative=payload.negative,
        size=payload.size,
        variants=payload.variants,
        caption=payload.caption,
        style_tags=payload.style_tags,
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return ImageBriefResponse(id=brief.id, prompt=brief.prompt or "")


@router.post("/images", response_model=ImagesResponse)
async def generate_images(
    payload: ImagesRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate images using OpenAI and store them as media assets."""
    brief = db.get(ImageBrief, payload.image_brief_id)
    if brief is None or brief.editor_result.user_id != user.id:
        raise HTTPException(status_code=404, detail="image brief not found")

    client = OpenAI()
    # Simple moderation step; in case of flagged content, raise error
    mod = client.moderations.create(
        model="omni-moderation-latest", input=brief.prompt or ""
    )
    if getattr(mod.results[0], "flagged", False):
        raise HTTPException(status_code=400, detail="prompt flagged")

    n = brief.variants or 1
    size = brief.size or "1024x1024"
    resp = client.images.generate(
        model="gpt-image-1", prompt=brief.prompt or "", size=size, n=n
    )
    urls: List[str] = [d.url for d in resp.data]

    for url in urls:
        asset = MediaAsset(
            image_brief_id=brief.id,
            kind="generated",
            url=url,
        )
        db.add(asset)
    db.commit()

    return ImagesResponse(urls=urls)


@router.post("/package", response_model=PackageResponse)
async def create_package(
    payload: PackageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a content package with platform-specific items."""
    result = db.get(EditorResult, payload.editor_result_id)
    if result is None or result.user_id != user.id:
        raise HTTPException(status_code=404, detail="editor result not found")

    package = ContentPackage(user_id=user.id, editor_result_id=result.id)
    db.add(package)
    db.flush()

    for item in payload.items:
        pkg_item = ContentPackageItem(
            package_id=package.id,
            platform=item.platform,
            post_time=item.post_time,
            post_text=item.post_text,
            hashtags=item.hashtags,
            cta=item.cta,
            image_url=item.image_url,
        )
        db.add(pkg_item)

    db.commit()
    db.refresh(package)
    return PackageResponse(id=package.id)


@router.get("/packages")
async def list_packages(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List content packages created by the user with their items."""
    packages = (
        db.query(ContentPackage)
        .filter(ContentPackage.user_id == user.id)
        .all()
    )
    result = []
    for pkg in packages:
        items = [
            {
                "platform": i.platform,
                "post_time": i.post_time.isoformat() if i.post_time else None,
                "post_text": i.post_text,
                "hashtags": i.hashtags,
                "cta": i.cta,
                "image_url": i.image_url,
            }
            for i in pkg.items
        ]
        result.append({"id": pkg.id, "items": items})
    return result


__all__ = ["router"]
