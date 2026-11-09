"""Knowledge Base endpoints — categories + articles."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id, get_current_user, require_role
from ...models import KBArticle, KBCategory, User, Workspace
from ...schemas import (
    KBArticleCreate,
    KBArticleOut,
    KBArticleUpdate,
    KBCategoryCreate,
    KBCategoryOut,
    PaginatedResponse,
)
from ...services.audit import write_audit
from ...slugs import slugify

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=PaginatedResponse[KBCategoryOut])
def list_kb_categories(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(KBCategory).where(KBCategory.agency_id == agency_id)
    count_stmt = select(func.count()).select_from(KBCategory).where(KBCategory.agency_id == agency_id)
    if workspace_id is not None:
        stmt = stmt.where(KBCategory.workspace_id == workspace_id)
        count_stmt = count_stmt.where(KBCategory.workspace_id == workspace_id)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(KBCategory.position.asc(), KBCategory.created_at.desc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[KBCategoryOut](items=items, total=total, limit=limit, offset=offset)


@router.post("/categories", response_model=KBCategoryOut, status_code=status.HTTP_201_CREATED)
def create_kb_category(
    payload: KBCategoryCreate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws = db.scalar(
        select(Workspace).where(
            Workspace.id == payload.workspace_id,
            Workspace.agency_id == agency_id,
        )
    )
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    slug = slugify(payload.name)
    existing = db.scalar(
        select(KBCategory).where(
            KBCategory.workspace_id == payload.workspace_id,
            KBCategory.slug == slug,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Category slug already exists in this workspace")
    if payload.parent_id is not None:
        parent = db.scalar(
            select(KBCategory).where(
                KBCategory.id == payload.parent_id,
                KBCategory.workspace_id == payload.workspace_id,
                KBCategory.agency_id == agency_id,
            )
        )
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent category not found")
    cat = KBCategory(
        workspace_id=payload.workspace_id,
        agency_id=agency_id,
        name=payload.name,
        slug=slug,
        parent_id=payload.parent_id,
        position=payload.position,
    )
    db.add(cat)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="kb_category.create",
        target_type="kb_category",
        target_id=cat.id,
        metadata={"workspace_id": str(payload.workspace_id), "slug": slug},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------


@router.get("/articles", response_model=PaginatedResponse[KBArticleOut])
def list_kb_articles(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    is_published: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(KBArticle).where(KBArticle.agency_id == agency_id)
    count_stmt = select(func.count()).select_from(KBArticle).where(KBArticle.agency_id == agency_id)
    if workspace_id is not None:
        stmt = stmt.where(KBArticle.workspace_id == workspace_id)
        count_stmt = count_stmt.where(KBArticle.workspace_id == workspace_id)
    if category_id is not None:
        stmt = stmt.where(KBArticle.category_id == category_id)
        count_stmt = count_stmt.where(KBArticle.category_id == category_id)
    if is_published is not None:
        stmt = stmt.where(KBArticle.is_published == is_published)
        count_stmt = count_stmt.where(KBArticle.is_published == is_published)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(KBArticle.created_at.desc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[KBArticleOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/articles/{article_id}", response_model=KBArticleOut)
def get_kb_article(
    article_id: uuid.UUID,
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
):
    a = db.scalar(
        select(KBArticle).where(KBArticle.id == article_id, KBArticle.agency_id == agency_id)
    )
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return a


@router.post("/articles", response_model=KBArticleOut, status_code=status.HTTP_201_CREATED)
def create_kb_article(
    payload: KBArticleCreate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager", "agent")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws = db.scalar(
        select(Workspace).where(
            Workspace.id == payload.workspace_id,
            Workspace.agency_id == agency_id,
        )
    )
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if payload.category_id is not None:
        cat = db.scalar(
            select(KBCategory).where(
                KBCategory.id == payload.category_id,
                KBCategory.workspace_id == payload.workspace_id,
                KBCategory.agency_id == agency_id,
            )
        )
        if cat is None:
            raise HTTPException(status_code=404, detail="Category not found in this workspace")
    slug = slugify(payload.title)
    # ensure slug uniqueness within workspace
    existing = db.scalar(
        select(KBArticle).where(
            KBArticle.workspace_id == payload.workspace_id,
            KBArticle.slug == slug,
        )
    )
    if existing is not None:
        # Append a short suffix to disambiguate
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    article = KBArticle(
        workspace_id=payload.workspace_id,
        agency_id=agency_id,
        category_id=payload.category_id,
        title=payload.title,
        slug=slug,
        content_md=payload.content_md,
        content_html="",  # Phase 1: no markdown rendering server-side
        is_published=payload.is_published,
        author_id=user.id,
    )
    db.add(article)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="kb_article.create",
        target_type="kb_article",
        target_id=article.id,
        metadata={"workspace_id": str(payload.workspace_id), "slug": slug, "is_published": payload.is_published},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(article)
    return article


@router.patch("/articles/{article_id}", response_model=KBArticleOut)
def update_kb_article(
    article_id: uuid.UUID,
    payload: KBArticleUpdate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager", "agent")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = db.scalar(
        select(KBArticle).where(KBArticle.id == article_id, KBArticle.agency_id == agency_id)
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    changes: dict = {}
    if payload.title is not None and payload.title != article.title:
        article.title = payload.title
        changes["title"] = payload.title
    if payload.content_md is not None and payload.content_md != article.content_md:
        article.content_md = payload.content_md
        changes["content_md"] = True
    if payload.is_published is not None and payload.is_published != article.is_published:
        article.is_published = payload.is_published
        changes["is_published"] = payload.is_published
    if payload.category_id is not None and payload.category_id != article.category_id:
        article.category_id = payload.category_id
        changes["category_id"] = str(payload.category_id)
    if changes:
        write_audit(
            db,
            agency_id=agency_id,
            actor_user_id=user.id,
            action="kb_article.update",
            target_type="kb_article",
            target_id=article.id,
            metadata=changes,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    db.commit()
    db.refresh(article)
    return article
