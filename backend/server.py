from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Depends, Header, Request
from fastapi.responses import Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt

from exporters import (
    docx_to_html,
    generate_pdf,
    generate_epub,
    KDP_TRIM_SIZES,
)
from ai_editor import (
    tighten_prose,
    improve_clarity,
    generate_blurb,
    suggest_chapter_titles,
    generate_synopsis,
)
from ai_copyeditor import run_copyedit_pass, STYLE_GUIDES
from writing_agent import (
    agent_chat,
    run_inline_command,
    VOICE_PRESETS,
    PROVIDER_LABELS,
    PROVIDER_DEFAULT_MODEL,
    resolve_provider_and_key,
)
from agent_quota import (
    FREE_DAILY_LIMIT,
    check_and_charge as agent_check_and_charge,
    refund_charge as agent_refund_charge,
    quota_snapshot as agent_quota_snapshot,
)
from audio_narrator import (
    list_voices as audio_list_voices,
    narrate_text,
    narrate_preview,
    narrate_audiobook,
)
from elevenlabs_narrator import (
    list_voices as eleven_list_voices,
    narrate_text as eleven_narrate_text,
    narrate_preview as eleven_narrate_preview,
    narrate_audiobook as eleven_narrate_audiobook,
    ElevenLabsAuthError,
    ElevenLabsServiceError,
    DEFAULT_MODEL as ELEVEN_DEFAULT_MODEL,
)
from audio_uploads import (
    save_upload as save_audio_upload,
    find_existing as find_audio_upload,
    delete_existing as delete_audio_upload,
    fetch_bytes as fetch_audio_bytes,
    media_type_for as audio_media_type,
    ALLOWED_EXTENSIONS as AUDIO_ALLOWED_EXTENSIONS,
)
from cover_uploads import (
    save_upload as save_cover_upload,
    find_existing as find_cover_upload,
    delete_existing as delete_cover_upload,
    fetch_bytes as fetch_cover_bytes,
    media_type_for as cover_media_type,
    ALLOWED_EXTENSIONS as COVER_ALLOWED_EXTENSIONS,
)
from voice_memos import (
    save_memo as save_voice_memo,
    find_memo_file,
    delete_memo_file,
    fetch_bytes as fetch_memo_bytes,
    media_type_for as memo_media_type,
    ALLOWED_EXTENSIONS as MEMO_ALLOWED_EXTENSIONS,
)
from object_storage import init_storage as init_object_storage
from transcription import transcribe_audio
from image_to_pdf import image_to_pdf
from chapter_audiobook import export_chapters_zip, split_into_chapters
from billing import (
    PLANS,
    get_plan,
    list_plans_public,
    new_transaction_record,
    new_subscription_record,
    extend_subscription,
    is_subscription_active,
    calculate_commission,
    new_commission_record,
)
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CheckoutStatusResponse,
)
import subscription_billing as subs_billing
import stripe  # for stripe.error.InvalidRequestError exception handling
from secrets_vault import decrypt_secret, encrypt_secret

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Initialize Stripe SDK AFTER loading .env so STRIPE_SECRET_KEY is available
subs_billing.init_stripe()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
SECRET_KEY = (os.environ.get('JWT_SECRET') or '').strip()
if len(SECRET_KEY) < 32:
    raise RuntimeError('JWT_SECRET must be configured with at least 32 characters.')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# --- MODELS ---

import secrets

def _generate_referral_code() -> str:
    """8-character URL-safe code, uppercase for memorability."""
    return secrets.token_urlsafe(6)[:8].upper().replace("-", "X").replace("_", "Y")


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    password_hash: str
    elevenlabs_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None       # BYO — routes chat + Cmd-K through user's own OpenAI key
    anthropic_api_key: Optional[str] = None    # BYO — routes chat + Cmd-K through user's own Anthropic key
    preferred_llm_provider: Optional[str] = None  # "openai" | "anthropic" (default anthropic)
    referral_code: Optional[str] = None
    referred_by: Optional[str] = None  # the referral_code of whoever referred this user
    is_super_admin: bool = False  # owner / platform admin
    stripe_customer_id: Optional[str] = None  # set after first Stripe checkout
    stripe_connect_account_id: Optional[str] = None  # affiliate's Connect (Express) account
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserRegister(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8, max_length=128)
    referral_code: Optional[str] = None  # optional invite code

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    has_elevenlabs_key: bool = False
    has_openai_key: bool = False
    has_anthropic_key: bool = False
    preferred_llm_provider: str = "anthropic"
    referral_code: Optional[str] = None
    is_super_admin: bool = False
    created_at: datetime

class TokenResponse(BaseModel):
    token: str
    user: UserResponse

class DocumentMetadata(BaseModel):
    isbn: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    language: Optional[str] = "English"
    page_count: Optional[int] = None
    genre: Optional[str] = None
    category: Optional[str] = None  # KDP category, e.g. "Self-Help > Leadership"
    keywords: List[str] = Field(default_factory=list)
    description: Optional[str] = None

class Comment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_name: str
    content: str
    position: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Version(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    version_number: int

class VoiceMemo(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: Optional[str] = None
    paragraph_index: Optional[int] = None  # 0-based block index in the manuscript, when set
    ext: str
    size_bytes: int
    transcript: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str = ""
    user_id: str
    format: str = "6x9"
    original_filename: Optional[str] = None
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    cover_image_ext: Optional[str] = None
    last_pdf_export_at: Optional[datetime] = None
    last_epub_export_at: Optional[datetime] = None
    last_audio_export_at: Optional[datetime] = None
    versions: List[Version] = Field(default_factory=list)
    comments: List[Comment] = Field(default_factory=list)
    memos: List[VoiceMemo] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineStatus(BaseModel):
    manuscript: bool = False
    metadata: bool = False
    cover: bool = False
    pdf: bool = False
    epub: bool = False
    audiobook: bool = False

    @property
    def completed(self) -> int:
        return sum([self.manuscript, self.metadata, self.cover, self.pdf, self.epub, self.audiobook])


def _strip_html_text(html: str) -> str:
    import re as _re
    return _re.sub(r"<[^>]+>", "", html or "").strip()


def _compute_pipeline_status(doc: dict, user_id: str) -> "PipelineStatus":
    metadata = doc.get("metadata") or {}
    has_audio_upload = bool(find_audio_upload(doc))
    return PipelineStatus(
        manuscript=len(_strip_html_text(doc.get("content") or "")) >= 50,
        metadata=bool((metadata.get("author") or "").strip())
                  and bool((metadata.get("description") or "").strip()),
        cover=bool(doc.get("cover_image_ext")) or bool(find_cover_upload(doc)),
        pdf=bool(doc.get("last_pdf_export_at")),
        epub=bool(doc.get("last_epub_export_at")),
        audiobook=has_audio_upload or bool(doc.get("last_audio_export_at")),
    )


def _build_document_response(doc: dict, user_id: str, include_pipeline: bool = True) -> "DocumentResponse":
    if isinstance(doc.get("created_at"), str):
        doc["created_at"] = datetime.fromisoformat(doc["created_at"])
    if isinstance(doc.get("updated_at"), str):
        doc["updated_at"] = datetime.fromisoformat(doc["updated_at"])
    for ts_field in ("last_pdf_export_at", "last_epub_export_at", "last_audio_export_at"):
        v = doc.get(ts_field)
        if isinstance(v, str):
            try:
                doc[ts_field] = datetime.fromisoformat(v)
            except ValueError:
                doc[ts_field] = None

    return DocumentResponse(
        id=doc["id"],
        title=doc["title"],
        content=doc.get("content", ""),
        user_id=doc["user_id"],
        format=doc.get("format", "6x9"),
        original_filename=doc.get("original_filename"),
        metadata=DocumentMetadata(**(doc.get("metadata") or {})),
        cover_image_ext=doc.get("cover_image_ext"),
        last_pdf_export_at=doc.get("last_pdf_export_at"),
        last_epub_export_at=doc.get("last_epub_export_at"),
        last_audio_export_at=doc.get("last_audio_export_at"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        version_count=len(doc.get("versions", [])),
        comment_count=len(doc.get("comments", [])),
        pipeline_status=_compute_pipeline_status(doc, user_id) if include_pipeline else None,
    )

class DocumentCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    format: Optional[str] = "6x9"

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    format: Optional[str] = None
    metadata: Optional[DocumentMetadata] = None

class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    user_id: str
    format: str
    original_filename: Optional[str]
    metadata: DocumentMetadata
    cover_image_ext: Optional[str] = None
    last_pdf_export_at: Optional[datetime] = None
    last_epub_export_at: Optional[datetime] = None
    last_audio_export_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    version_count: int
    comment_count: int
    pipeline_status: Optional[PipelineStatus] = None

class CommentCreate(BaseModel):
    content: str
    position: Optional[int] = None

# --- AUTH HELPERS ---

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    for field in ("elevenlabs_api_key", "openai_api_key", "anthropic_api_key"):
        user_doc[field] = decrypt_secret(user_doc.get(field))
    return User(**user_doc)

# --- AUTH ROUTES ---

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    existing = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Resolve referral code if provided — must be a real existing user's code
    referred_by = None
    if user_data.referral_code:
        code = user_data.referral_code.strip().upper()
        if code:
            referrer = await db.users.find_one({"referral_code": code}, {"_id": 0, "id": 1})
            if referrer:
                referred_by = code

    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=hash_password(user_data.password),
        referral_code=_generate_referral_code(),
        referred_by=referred_by,
    )

    doc = user.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.users.insert_one(doc)

    token = create_access_token({"sub": user.id})
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        has_elevenlabs_key=bool(user.elevenlabs_api_key),
        has_openai_key=bool(user.openai_api_key),
        has_anthropic_key=bool(user.anthropic_api_key),
        preferred_llm_provider=(user.preferred_llm_provider or "anthropic"),
        referral_code=user.referral_code,
        is_super_admin=user.is_super_admin,
        created_at=user.created_at
    )

    return TokenResponse(token=token, user=user_response)

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if isinstance(user_doc['created_at'], str):
        user_doc['created_at'] = datetime.fromisoformat(user_doc['created_at'])
    
    user = User(**user_doc)
    
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user.id})
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        has_elevenlabs_key=bool(user.elevenlabs_api_key),
        has_openai_key=bool(user.openai_api_key),
        has_anthropic_key=bool(user.anthropic_api_key),
        preferred_llm_provider=(user.preferred_llm_provider or "anthropic"),
        referral_code=user.referral_code,
        is_super_admin=user.is_super_admin,
        created_at=user.created_at
    )
    
    return TokenResponse(token=token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    # Backfill referral_code for legacy users who registered before the feature existed
    if not current_user.referral_code:
        current_user.referral_code = _generate_referral_code()
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"referral_code": current_user.referral_code}},
        )
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        has_elevenlabs_key=bool(current_user.elevenlabs_api_key),
        has_openai_key=bool(current_user.openai_api_key),
        has_anthropic_key=bool(current_user.anthropic_api_key),
        preferred_llm_provider=(current_user.preferred_llm_provider or "anthropic"),
        referral_code=current_user.referral_code,
        is_super_admin=current_user.is_super_admin,
        created_at=current_user.created_at
    )


@api_router.get("/auth/me/referrals")
async def my_referrals(current_user: User = Depends(get_current_user)):
    """Return the current user's referral code and a summary of people they have invited."""
    code = current_user.referral_code
    if not code:
        code = _generate_referral_code()
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"referral_code": code}},
        )

    referred_cursor = db.users.find(
        {"referred_by": code},
        {"_id": 0, "name": 1, "email": 1, "created_at": 1},
    )
    referred = await referred_cursor.to_list(500)
    # Strip emails to protect privacy — only show name + signup date
    public = []
    for r in referred:
        ts = r.get("created_at")
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        public.append({"name": r.get("name", "Anonymous Author"), "joined_at": ts})

    public.sort(key=lambda x: x["joined_at"] or "", reverse=True)
    return {
        "referral_code": code,
        "total_referred": len(public),
        "recent": public[:20],
    }


# --- AFFILIATE PROGRAM (settings + leaderboard) ---

DEFAULT_AFFILIATE_SETTINGS = {
    "enabled": True,
    "reward_type": "cash_and_perks",  # "credits" | "cash" | "perks" | "cash_and_perks" | "none"
    "signup_commission_percent": 30.0,  # one-time at qualifying event
    "mrr_commission_percent": 10.0,  # recurring monthly while invitee remains active
    "minimum_payout": 50.0,  # USD threshold before cash payout is issued
    "qualifying_event": "active_subscription_60d",  # signup | first_paid_subscription | first_book_published | active_subscription_60d
    "active_days_required": 60,
    "payout_method": "stripe_connect",  # stripe_connect | manual | none
    "currency": "USD",
    "stripe_connect_enabled": False,  # flipped on once Stripe onboarding is complete
    "perks_description": "Free book exports, audiobook minutes, and priority support.",
    "notes": "",
}


async def _load_affiliate_settings() -> dict:
    doc = await db.affiliate_settings.find_one({"_id": "global"}, {"_id": 0})
    if not doc:
        return dict(DEFAULT_AFFILIATE_SETTINGS)
    merged = dict(DEFAULT_AFFILIATE_SETTINGS)
    merged.update(doc)
    return merged


def _require_super_admin(current_user: User):
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Owner / super-admin only.")


@api_router.get("/affiliate/settings")
async def get_affiliate_settings_public():
    """Public read-only view of the program settings (so authors know how they're rewarded)."""
    settings = await _load_affiliate_settings()
    # Strip internal-only fields if any are ever added
    return settings


class AffiliateSettings(BaseModel):
    enabled: Optional[bool] = None
    reward_type: Optional[str] = None
    signup_commission_percent: Optional[float] = None
    mrr_commission_percent: Optional[float] = None
    minimum_payout: Optional[float] = None
    qualifying_event: Optional[str] = None
    active_days_required: Optional[int] = None
    payout_method: Optional[str] = None
    currency: Optional[str] = None
    stripe_connect_enabled: Optional[bool] = None
    perks_description: Optional[str] = None
    notes: Optional[str] = None


@api_router.put("/admin/affiliate/settings")
async def update_affiliate_settings(
    payload: AffiliateSettings,
    current_user: User = Depends(get_current_user),
):
    _require_super_admin(current_user)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    valid_reward = ("credits", "cash", "perks", "cash_and_perks", "none")
    if "reward_type" in updates and updates["reward_type"] not in valid_reward:
        raise HTTPException(status_code=400, detail=f"reward_type must be one of: {', '.join(valid_reward)}")
    valid_event = ("signup", "first_paid_subscription", "first_book_published", "active_subscription_60d")
    if "qualifying_event" in updates and updates["qualifying_event"] not in valid_event:
        raise HTTPException(status_code=400, detail=f"qualifying_event must be one of: {', '.join(valid_event)}")
    valid_payout = ("stripe_connect", "manual", "none")
    if "payout_method" in updates and updates["payout_method"] not in valid_payout:
        raise HTTPException(status_code=400, detail=f"payout_method must be one of: {', '.join(valid_payout)}")
    for pct_field in ("signup_commission_percent", "mrr_commission_percent"):
        if pct_field in updates and not (0.0 <= updates[pct_field] <= 100.0):
            raise HTTPException(status_code=400, detail=f"{pct_field} must be between 0 and 100")
    if "active_days_required" in updates and updates["active_days_required"] < 0:
        raise HTTPException(status_code=400, detail="active_days_required must be non-negative")
    await db.affiliate_settings.update_one(
        {"_id": "global"},
        {"$set": updates},
        upsert=True,
    )
    return await _load_affiliate_settings()


@api_router.get("/referrals/leaderboard")
async def referrals_leaderboard(limit: int = 10):
    """Top N users by referral count. Public — authors want to see who's leading."""
    limit = max(1, min(50, limit))
    pipeline = [
        {"$match": {"referred_by": {"$ne": None}}},
        {"$group": {"_id": "$referred_by", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    grouped = await db.users.aggregate(pipeline).to_list(limit)
    out = []
    for entry in grouped:
        code = entry["_id"]
        referrer = await db.users.find_one(
            {"referral_code": code}, {"_id": 0, "name": 1}
        )
        if referrer:
            out.append({
                "name": referrer.get("name", "Anonymous Author"),
                "count": entry["count"],
            })
    return {"leaderboard": out}


def _badge_tier(count: int) -> Optional[dict]:
    if count >= 25:
        return {"key": "founding_editor", "label": "Founding Editor", "min": 25}
    if count >= 10:
        return {"key": "patron", "label": "Patron of Letters", "min": 10}
    if count >= 5:
        return {"key": "advocate", "label": "Author Advocate", "min": 5}
    if count >= 1:
        return {"key": "ambassador", "label": "Ambassador", "min": 1}
    return None


@api_router.get("/auth/me/badge")
async def my_affiliate_badge(current_user: User = Depends(get_current_user)):
    """Return the badge tier earned by this user's referral activity."""
    code = current_user.referral_code
    if not code:
        return {"badge": None, "count": 0}
    count = await db.users.count_documents({"referred_by": code})
    return {"badge": _badge_tier(count), "count": count}


# --- BILLING & STRIPE CHECKOUT ---

class BillingCheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str  # frontend's window.location.origin


def _stripe_client(http_request) -> StripeCheckout:
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured on the server.")
    host_url = str(http_request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


@api_router.get("/billing/plans")
async def billing_plans():
    """Public plan catalogue. Prices/IDs are server-defined; never trust the client."""
    return {"plans": list_plans_public()}


@api_router.get("/billing/me")
async def billing_me(current_user: User = Depends(get_current_user)):
    """Current subscription status for the logged-in user."""
    sub = await db.subscriptions.find_one({"user_id": current_user.id}, {"_id": 0})
    plan = get_plan(sub["plan_id"]) if sub and sub.get("plan_id") else None
    return {
        "active": is_subscription_active(sub),
        "plan_id": sub.get("plan_id") if sub else None,
        "plan_name": plan["name"] if plan else None,
        "pro_until": sub.get("pro_until") if sub else None,
        "payments_count": sub.get("payments_count", 0) if sub else 0,
    }


@api_router.post("/billing/checkout")
async def billing_checkout(
    payload: BillingCheckoutRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout session for a fixed plan.

    Uses TRUE recurring subscriptions (mode=subscription) against the owner's
    Stripe account when STRIPE_SECRET_KEY is configured. Falls back to one-time
    payments via the platform test key when not.
    """
    plan = get_plan(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan.")
    origin = (payload.origin_url or "").strip().rstrip("/")
    if not origin.startswith("http"):
        raise HTTPException(status_code=400, detail="origin_url must be an absolute URL.")

    success_url = f"{origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/billing"

    # Prefer real subscriptions when configured
    if subs_billing.is_configured():
        # Reuse customer if we've seen this user before
        user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
        stripe_customer_id = (user_doc or {}).get("stripe_customer_id")
        try:
            session = subs_billing.create_subscription_checkout(
                user_id=current_user.id,
                email=current_user.email,
                plan_id=plan["id"],
                success_url=success_url,
                cancel_url=cancel_url,
                stripe_customer_id=stripe_customer_id,
                referred_by=(user_doc or {}).get("referred_by"),
            )
        except Exception as exc:
            logger.exception("Stripe subscription checkout creation failed")
            raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

        record = new_transaction_record(
            session_id=session.id,
            user_id=current_user.id,
            email=current_user.email,
            plan_id=plan["id"],
            amount=float(plan["amount"]),
            currency=plan["currency"],
            metadata={
                "source": "dlp_subscription",
                "mode": "subscription",
                "live": subs_billing.is_live_mode(),
            },
        )
        await db.payment_transactions.insert_one(record)
        return {"session_id": session.id, "url": session.url}

    # ---- Fallback: one-time payment via emergentintegrations test key ----
    client = _stripe_client(http_request)
    req = CheckoutSessionRequest(
        amount=float(plan["amount"]),
        currency=plan["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": current_user.id,
            "email": current_user.email,
            "plan_id": plan["id"],
            "source": "dlp_subscription",
        },
    )
    try:
        session = await client.create_checkout_session(req)
    except Exception as exc:
        logger.exception("Stripe checkout creation failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    record = new_transaction_record(
        session_id=session.session_id,
        user_id=current_user.id,
        email=current_user.email,
        plan_id=plan["id"],
        amount=float(plan["amount"]),
        currency=plan["currency"],
        metadata={"source": "dlp_subscription", "mode": "payment"},
    )
    await db.payment_transactions.insert_one(record)
    return {"session_id": session.session_id, "url": session.url}


async def _credit_successful_payment(
    *,
    session_id: str,
    payment_status: str,
    session_status: str,
    amount_total_cents: int,
    currency: str,
    metadata: dict,
    stripe_subscription_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
) -> dict:
    """Idempotently process a successful Stripe Checkout session:
    - Update the payment_transactions row.
    - Extend / create the user's subscription.
    - Accrue affiliate commission if applicable.
    Returns a small summary dict for clients/webhooks."""
    txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not txn:
        return {"processed": False, "reason": "transaction_not_found"}

    update_fields = {
        "payment_status": payment_status,
        "status": session_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if txn.get("processed"):
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": update_fields}
        )
        return {"processed": True, "duplicate": True, "plan_id": txn.get("plan_id")}

    if payment_status != "paid":
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": update_fields}
        )
        return {"processed": False, "payment_status": payment_status}

    plan_id = (metadata or {}).get("plan_id") or txn.get("plan_id")
    # Defense-in-depth: trust the txn we created server-side over Stripe metadata
    user_id = txn.get("user_id") or (metadata or {}).get("user_id")
    plan = get_plan(plan_id)
    if not plan or not user_id:
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": update_fields}
        )
        return {"processed": False, "reason": "missing_plan_or_user"}

    # Subscription credit
    existing_sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    is_first_payment = existing_sub is None
    if is_first_payment:
        sub_doc = new_subscription_record(
            user_id=user_id, plan_id=plan_id, period_days=int(plan["period_days"])
        )
        if stripe_subscription_id:
            sub_doc["stripe_subscription_id"] = stripe_subscription_id
        if stripe_customer_id:
            sub_doc["stripe_customer_id"] = stripe_customer_id
        await db.subscriptions.insert_one(sub_doc)
    else:
        ext = extend_subscription(
            existing_sub, plan_id=plan_id, period_days=int(plan["period_days"])
        )
        if stripe_subscription_id:
            ext["stripe_subscription_id"] = stripe_subscription_id
        if stripe_customer_id:
            ext["stripe_customer_id"] = stripe_customer_id
        await db.subscriptions.update_one({"user_id": user_id}, {"$set": ext})

    # Mark txn processed FIRST to lock idempotency
    update_fields["processed"] = True
    await db.payment_transactions.update_one(
        {"session_id": session_id}, {"$set": update_fields}
    )

    # Affiliate commission (best-effort; failures must not break the payment)
    commission_amount = None
    try:
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
        if user_doc and user_doc.get("referred_by"):
            referrer = await db.users.find_one(
                {"referral_code": user_doc["referred_by"]}, {"_id": 0}
            )
            if referrer:
                settings = await _load_affiliate_settings()
                signup_at = user_doc.get("created_at")
                if isinstance(signup_at, str):
                    try:
                        signup_at = datetime.fromisoformat(signup_at)
                    except ValueError:
                        signup_at = datetime.now(timezone.utc)
                elif not isinstance(signup_at, datetime):
                    signup_at = datetime.now(timezone.utc)
                if signup_at.tzinfo is None:
                    signup_at = signup_at.replace(tzinfo=timezone.utc)

                paid_amount = float(amount_total_cents) / 100.0 if amount_total_cents else float(plan["amount"])
                comm = calculate_commission(
                    amount=paid_amount,
                    is_first_payment=is_first_payment,
                    settings=settings,
                    referee_signup_at=signup_at,
                )
                if comm:
                    rec = new_commission_record(
                        referrer_user_id=referrer["id"],
                        referee_user_id=user_id,
                        referee_email=user_doc.get("email", ""),
                        transaction_id=txn["id"],
                        session_id=session_id,
                        plan_id=plan_id,
                        kind=comm["kind"],
                        percent=comm["percent"],
                        amount=comm["amount"],
                        currency=comm["currency"],
                    )
                    await db.commissions.insert_one(rec)
                    commission_amount = comm["amount"]
    except Exception:
        logger.exception("Commission accrual failed (non-fatal)")

    return {
        "processed": True,
        "plan_id": plan_id,
        "user_id": user_id,
        "commission_amount": commission_amount,
    }


@api_router.get("/billing/checkout/status/{session_id}")
async def billing_checkout_status(
    session_id: str,
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    """Poll Stripe for the session status and credit the user idempotently."""
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Checkout session not found.")

    # Real subscription mode (owner's account) — use raw stripe SDK
    if subs_billing.is_configured() and (txn.get("metadata") or {}).get("mode") == "subscription":
        try:
            session = subs_billing.retrieve_checkout_session(session_id)
        except Exception as exc:
            logger.exception("Stripe subscription status fetch failed")
            raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

        # Capture customer & subscription IDs on the user record after first payment
        customer_id = session.customer if isinstance(session.customer, str) else (
            session.customer.id if session.customer else None
        )
        subscription_obj = session.subscription if not isinstance(session.subscription, str) else None
        subscription_id = (
            session.subscription if isinstance(session.subscription, str)
            else (subscription_obj.id if subscription_obj else None)
        )
        if customer_id:
            await db.users.update_one(
                {"id": current_user.id, "stripe_customer_id": {"$in": [None, ""]}},
                {"$set": {"stripe_customer_id": customer_id}},
            )

        summary = await _credit_successful_payment(
            session_id=session_id,
            payment_status=session.payment_status or "unpaid",
            session_status=session.status or "open",
            amount_total_cents=int(session.amount_total or 0),
            currency=(session.currency or "usd"),
            metadata=dict(session.metadata or {}),
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
        )
        return {
            "session_id": session_id,
            "status": session.status,
            "payment_status": session.payment_status,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "plan_id": summary.get("plan_id"),
            "processed": summary.get("processed", False),
            "subscription_id": subscription_id,
            "mode": "subscription",
        }

    # ---- Fallback: one-time payment via emergentintegrations test key ----
    client = _stripe_client(http_request)
    try:
        status: CheckoutStatusResponse = await client.get_checkout_status(session_id)
    except Exception as exc:
        logger.exception("Stripe status fetch failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    summary = await _credit_successful_payment(
        session_id=session_id,
        payment_status=status.payment_status,
        session_status=status.status,
        amount_total_cents=int(status.amount_total or 0),
        currency=(status.currency or "usd"),
        metadata=dict(status.metadata or {}),
    )
    return {
        "session_id": session_id,
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "plan_id": summary.get("plan_id"),
        "processed": summary.get("processed", False),
        "mode": "payment",
    }


@api_router.post("/webhook/stripe")
async def stripe_webhook(http_request: Request):
    """Stripe webhook receiver — credits payments idempotently.

    When STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET are configured, we verify
    against the owner's real webhook secret and handle:
      • checkout.session.completed       → first payment, capture subscription_id
      • invoice.paid                     → recurring renewal (extends pro_until + accrues MRR commission)
      • customer.subscription.deleted    → cancellation (marks sub inactive)

    Falls back to the emergentintegrations webhook flow for the platform test key.
    """
    body = await http_request.body()
    signature = http_request.headers.get("Stripe-Signature", "")

    owner_secret = (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if subs_billing.is_configured() and owner_secret:
        try:
            event = subs_billing.verify_webhook(body, signature, owner_secret)
        except Exception:
            logger.exception("Owner Stripe webhook verification failed")
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")

        event_type = event.get("type") if isinstance(event, dict) else event["type"]
        data_object = event["data"]["object"]

        try:
            if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
                session_id = data_object.get("id")
                customer_id = data_object.get("customer")
                subscription_id = data_object.get("subscription")
                meta = data_object.get("metadata") or {}
                user_id = meta.get("user_id")
                if customer_id and user_id:
                    await db.users.update_one(
                        {"id": user_id, "stripe_customer_id": {"$in": [None, ""]}},
                        {"$set": {"stripe_customer_id": customer_id}},
                    )
                await _credit_successful_payment(
                    session_id=session_id,
                    payment_status=data_object.get("payment_status") or "paid",
                    session_status=data_object.get("status") or "complete",
                    amount_total_cents=int(data_object.get("amount_total") or 0),
                    currency=(data_object.get("currency") or "usd"),
                    metadata=meta,
                    stripe_subscription_id=subscription_id,
                    stripe_customer_id=customer_id,
                )

            elif event_type == "invoice.paid":
                # Recurring renewal — billing_reason='subscription_cycle' is the renewal one.
                # For the first invoice (billing_reason='subscription_create'), the
                # checkout.session.completed event already credited us. Idempotent guard:
                # we key off invoice.id so each renewal is processed exactly once.
                billing_reason = data_object.get("billing_reason")
                if billing_reason in ("subscription_cycle", "subscription_threshold", "subscription_update"):
                    await _process_subscription_renewal(
                        invoice=data_object,
                    )

            elif event_type == "customer.subscription.deleted":
                stripe_sub_id = data_object.get("id")
                if stripe_sub_id:
                    await db.subscriptions.update_one(
                        {"stripe_subscription_id": stripe_sub_id},
                        {"$set": {
                            "active": False,
                            "cancelled_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }},
                    )

            elif event_type == "customer.subscription.updated":
                # Track cancel_at_period_end so the UI can show "Cancels on X"
                stripe_sub_id = data_object.get("id")
                if stripe_sub_id:
                    await db.subscriptions.update_one(
                        {"stripe_subscription_id": stripe_sub_id},
                        {"$set": {
                            "cancel_at_period_end": bool(data_object.get("cancel_at_period_end")),
                            "stripe_status": data_object.get("status"),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }},
                    )
        except Exception:
            logger.exception("Webhook event processing failed (event=%s)", event_type)
        return {"received": True, "event_type": event_type}

    # ---- Fallback: emergentintegrations webhook handler (test key) ----
    client = _stripe_client(http_request)
    try:
        event = await client.handle_webhook(body, signature)
    except Exception:
        logger.exception("Stripe webhook handling failed")
        raise HTTPException(status_code=400, detail="Invalid webhook payload or signature.")

    if event.event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        try:
            status_resp = await client.get_checkout_status(event.session_id)
            await _credit_successful_payment(
                session_id=event.session_id,
                payment_status=status_resp.payment_status,
                session_status=status_resp.status,
                amount_total_cents=int(status_resp.amount_total or 0),
                currency=(status_resp.currency or "usd"),
                metadata=dict(status_resp.metadata or event.metadata or {}),
            )
        except Exception:
            logger.exception("Webhook follow-up status fetch failed")
    return {"received": True, "event_type": event.event_type}


async def _process_subscription_renewal(*, invoice: dict) -> None:
    """Credit a recurring renewal payment.

    Keyed off `invoice.id` for idempotency — we record each invoice once in
    `payment_transactions` (with `processed=True`) and update the subscription's
    pro_until + payments_count. Also accrues MRR commission if eligible.
    """
    invoice_id = invoice.get("id")
    if not invoice_id:
        return

    existing = await db.payment_transactions.find_one({"session_id": invoice_id}, {"_id": 0})
    if existing and existing.get("processed"):
        return  # already credited

    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")
    amount_paid_cents = int(invoice.get("amount_paid") or 0)
    currency = invoice.get("currency") or "usd"
    if amount_paid_cents <= 0 or not customer_id:
        return

    user_doc = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0})
    if not user_doc:
        # Try to find via the existing subscription record
        sub = await db.subscriptions.find_one(
            {"stripe_subscription_id": subscription_id}, {"_id": 0}
        )
        if not sub:
            logger.warning("Renewal received for unknown customer/sub: %s / %s",
                           customer_id, subscription_id)
            return
        user_doc = await db.users.find_one({"id": sub["user_id"]}, {"_id": 0})
        if not user_doc:
            return

    # Resolve plan from subscription record
    existing_sub = await db.subscriptions.find_one({"user_id": user_doc["id"]}, {"_id": 0})
    plan_id = (existing_sub or {}).get("plan_id")
    plan = get_plan(plan_id) if plan_id else None
    if not plan:
        # Fallback: infer from amount
        amount_dollars = amount_paid_cents / 100.0
        for pid, p in PLANS.items():
            if abs(p["amount"] - amount_dollars) < 0.01:
                plan = p
                plan_id = pid
                break
        if not plan:
            logger.warning("Renewal — could not resolve plan for invoice %s", invoice_id)
            return

    # Insert a new transaction row (one per invoice) for the renewal
    txn = new_transaction_record(
        session_id=invoice_id,
        user_id=user_doc["id"],
        email=user_doc.get("email", ""),
        plan_id=plan_id,
        amount=amount_paid_cents / 100.0,
        currency=currency,
        metadata={"source": "dlp_subscription_renewal", "mode": "subscription"},
    )
    await db.payment_transactions.insert_one(txn)

    await _credit_successful_payment(
        session_id=invoice_id,
        payment_status="paid",
        session_status="complete",
        amount_total_cents=amount_paid_cents,
        currency=currency,
        metadata={"user_id": user_doc["id"], "plan_id": plan_id},
        stripe_subscription_id=subscription_id,
        stripe_customer_id=customer_id,
    )


@api_router.post("/billing/portal")
async def billing_portal(
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe Customer Portal session so the user can manage their card / cancel."""
    if not subs_billing.is_configured():
        raise HTTPException(status_code=400, detail="Customer portal requires the owner Stripe key.")
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    customer_id = (user_doc or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail="No Stripe customer on file — subscribe to a plan first.",
        )
    origin = str(http_request.headers.get("referer") or http_request.base_url).rstrip("/")
    # Strip query / path back to origin
    from urllib.parse import urlparse
    parsed = urlparse(origin)
    return_url = f"{parsed.scheme}://{parsed.netloc}/billing"
    try:
        portal = subs_billing.create_portal_session(
            stripe_customer_id=customer_id,
            return_url=return_url,
        )
    except Exception as exc:
        logger.exception("Stripe portal session failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")
    return {"url": portal.url}


@api_router.get("/billing/diagnostics")
async def billing_diagnostics():
    """Public-safe diagnostics so the frontend can show LIVE / TEST badges."""
    return {
        "subscription_billing_configured": subs_billing.is_configured(),
        "live_mode": subs_billing.is_live_mode(),
        "webhook_secret_configured": bool((os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()),
    }


# --- COMMISSIONS (affiliate earnings) ---

@api_router.get("/billing/commissions")
async def my_commissions(current_user: User = Depends(get_current_user)):
    """List commissions earned by the current user (as a referrer)."""
    cursor = db.commissions.find(
        {"referrer_user_id": current_user.id}, {"_id": 0}
    ).sort("created_at", -1)
    rows = await cursor.to_list(500)
    pending_total = round(sum(r["amount"] for r in rows if r.get("status") == "pending"), 2)
    paid_total = round(sum(r["amount"] for r in rows if r.get("status") == "paid"), 2)
    return {
        "commissions": rows,
        "totals": {
            "pending": pending_total,
            "paid": paid_total,
            "count": len(rows),
        },
    }


@api_router.get("/admin/commissions")
async def admin_list_commissions(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    _require_super_admin(current_user)
    query: dict = {}
    if status:
        query["status"] = status
    cursor = db.commissions.find(query, {"_id": 0}).sort("created_at", -1)
    rows = await cursor.to_list(2000)

    # Hydrate referrer names for the admin view
    user_ids = list({r["referrer_user_id"] for r in rows})
    user_map: dict = {}
    if user_ids:
        async for u in db.users.find(
            {"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}
        ):
            user_map[u["id"]] = u
    for r in rows:
        ref = user_map.get(r["referrer_user_id"], {})
        r["referrer_name"] = ref.get("name")
        r["referrer_email"] = ref.get("email")

    totals_by_user: dict = {}
    for r in rows:
        if r.get("status") != "pending":
            continue
        key = r["referrer_user_id"]
        totals_by_user.setdefault(key, {
            "user_id": key,
            "name": r.get("referrer_name"),
            "email": r.get("referrer_email"),
            "pending_total": 0.0,
            "count": 0,
        })
        totals_by_user[key]["pending_total"] = round(
            totals_by_user[key]["pending_total"] + float(r["amount"]), 2
        )
        totals_by_user[key]["count"] += 1
    return {
        "commissions": rows,
        "pending_by_user": list(totals_by_user.values()),
    }


class PayoutMarkPaidRequest(BaseModel):
    commission_ids: List[str]
    payout_method: Optional[str] = "manual"  # manual | stripe_connect | wire | paypal
    payout_reference: Optional[str] = None   # e.g. Stripe transfer id, check number


@api_router.post("/admin/commissions/mark-paid")
async def admin_mark_commissions_paid(
    payload: PayoutMarkPaidRequest,
    current_user: User = Depends(get_current_user),
):
    _require_super_admin(current_user)
    if not payload.commission_ids:
        raise HTTPException(status_code=400, detail="commission_ids cannot be empty.")
    result = await db.commissions.update_many(
        {"id": {"$in": payload.commission_ids}, "status": "pending"},
        {
            "$set": {
                "status": "paid",
                "paid_at": datetime.now(timezone.utc).isoformat(),
                "payout_method": payload.payout_method,
                "payout_reference": payload.payout_reference,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    return {"marked_paid": result.modified_count}


# --- STRIPE CONNECT — affiliate auto-payouts ---

class ConnectOnboardRequest(BaseModel):
    origin_url: str


def _connect_urls(origin: str) -> tuple[str, str]:
    origin = (origin or "").strip().rstrip("/")
    return (
        f"{origin}/affiliate/connect/refresh",
        f"{origin}/affiliate/connect/return",
    )


@api_router.post("/affiliate/connect/onboard")
async def affiliate_connect_onboard(
    payload: ConnectOnboardRequest,
    current_user: User = Depends(get_current_user),
):
    """Start (or resume) Stripe Express onboarding for the affiliate.

    On first call we create a connected Account and persist its ID on the user.
    On every call we mint a fresh single-use AccountLink and return its URL.
    """
    if not subs_billing.is_configured():
        raise HTTPException(status_code=400, detail="Stripe Connect requires the owner Stripe key.")

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found.")

    account_id = (user_doc or {}).get("stripe_connect_account_id")
    try:
        if not account_id:
            acct = subs_billing.create_express_account(
                email=current_user.email,
                user_id=current_user.id,
            )
            account_id = acct.id
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {"stripe_connect_account_id": account_id}},
            )
        refresh_url, return_url = _connect_urls(payload.origin_url)
        link = subs_billing.create_onboarding_link(
            account_id=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
        )
    except stripe.error.InvalidRequestError as exc:
        msg = exc.user_message or str(exc)
        if "signed up for Connect" in msg or "you can do that at" in msg:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Stripe Connect is not yet enabled on the platform account. "
                    "The owner must enable it at https://dashboard.stripe.com/connect "
                    "before affiliates can onboard."
                ),
            )
        raise HTTPException(status_code=502, detail=f"Stripe error: {msg}")
    except Exception as exc:
        logger.exception("Connect onboarding failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    return {"account_id": account_id, "url": link.url, "expires_at": link.expires_at}


@api_router.get("/affiliate/connect/status")
async def affiliate_connect_status(current_user: User = Depends(get_current_user)):
    """Return this affiliate's Connect onboarding state for the dashboard card."""
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    account_id = (user_doc or {}).get("stripe_connect_account_id")
    if not account_id:
        return {"connected": False, "account_id": None}
    if not subs_billing.is_configured():
        return {"connected": True, "account_id": account_id, "configured": False}
    try:
        status = subs_billing.retrieve_account_status(account_id)
    except stripe.error.InvalidRequestError as exc:
        # Account may have been deleted from Stripe Dashboard
        logger.warning("Connect account %s not retrievable: %s", account_id, exc)
        return {"connected": False, "account_id": None, "error": "stripe_account_missing"}
    except Exception as exc:
        logger.exception("Connect status fetch failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")
    return {"connected": True, **status, "ready_for_payouts": status.get("payouts_enabled") and status.get("charges_enabled")}


@api_router.post("/affiliate/connect/dashboard-link")
async def affiliate_connect_dashboard(current_user: User = Depends(get_current_user)):
    """SSO link into the affiliate's Stripe Express dashboard."""
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    account_id = (user_doc or {}).get("stripe_connect_account_id")
    if not account_id:
        raise HTTPException(status_code=400, detail="No connected account yet — onboard first.")
    try:
        link = subs_billing.create_express_login_link(account_id=account_id)
    except Exception as exc:
        logger.exception("Connect dashboard link failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")
    return {"url": link.url}


class AutoPayoutRequest(BaseModel):
    commission_ids: List[str]


@api_router.post("/admin/commissions/auto-payout")
async def admin_auto_payout(
    payload: AutoPayoutRequest,
    current_user: User = Depends(get_current_user),
):
    """Batch-transfer pending commissions to each affiliate's Stripe Connect account.

    Logic per row:
      1. Look up the referrer user → must have stripe_connect_account_id.
      2. Verify the account is ready (charges_enabled & payouts_enabled).
      3. Create a Stripe Transfer for the commission amount.
      4. Mark the commission row paid, store the transfer ID for traceability.
    Failed rows are returned in the response with reasons; successful rows are paid.
    """
    _require_super_admin(current_user)
    if not subs_billing.is_configured():
        raise HTTPException(status_code=400, detail="Stripe is not configured.")
    if not payload.commission_ids:
        raise HTTPException(status_code=400, detail="commission_ids cannot be empty.")

    rows = await db.commissions.find(
        {"id": {"$in": payload.commission_ids}, "status": "pending"},
        {"_id": 0},
    ).to_list(2000)
    if not rows:
        return {"paid": 0, "failed": [], "transfers": []}

    # Group by referrer for fewer Stripe API calls
    by_referrer: dict = {}
    for r in rows:
        by_referrer.setdefault(r["referrer_user_id"], []).append(r)

    # Cache account-status lookups per referrer
    paid_ids: list = []
    transfers_out: list = []
    failed: list = []

    for referrer_id, ref_rows in by_referrer.items():
        ref_user = await db.users.find_one({"id": referrer_id}, {"_id": 0})
        account_id = (ref_user or {}).get("stripe_connect_account_id")
        if not account_id:
            for r in ref_rows:
                failed.append({"commission_id": r["id"], "reason": "no_connect_account"})
            continue
        try:
            status = subs_billing.retrieve_account_status(account_id)
        except Exception as exc:
            for r in ref_rows:
                failed.append({"commission_id": r["id"], "reason": f"account_lookup_failed: {exc}"})
            continue
        if not (status.get("payouts_enabled") and status.get("charges_enabled")):
            for r in ref_rows:
                failed.append({
                    "commission_id": r["id"],
                    "reason": "account_not_ready",
                    "requirements_due": status.get("requirements_due"),
                })
            continue

        for r in ref_rows:
            amount_cents = int(round(float(r["amount"]) * 100))
            if amount_cents <= 0:
                failed.append({"commission_id": r["id"], "reason": "zero_amount"})
                continue
            try:
                transfer = subs_billing.create_transfer(
                    amount_cents=amount_cents,
                    currency=(r.get("currency") or "usd").lower(),
                    destination_account_id=account_id,
                    metadata={
                        "dlp_commission_id": r["id"],
                        "dlp_referrer_user_id": referrer_id,
                        "dlp_referee_user_id": r.get("referee_user_id", ""),
                        "dlp_kind": r.get("kind", ""),
                    },
                    description=f"DLP affiliate commission ({r.get('kind', 'commission')})",
                )
            except stripe.error.InvalidRequestError as exc:
                msg = exc.user_message or str(exc)
                failed.append({"commission_id": r["id"], "reason": f"stripe_invalid: {msg}"})
                continue
            except Exception as exc:
                failed.append({"commission_id": r["id"], "reason": f"stripe_error: {exc}"})
                continue

            now = datetime.now(timezone.utc).isoformat()
            await db.commissions.update_one(
                {"id": r["id"]},
                {"$set": {
                    "status": "paid",
                    "paid_at": now,
                    "payout_method": "stripe_connect",
                    "payout_reference": transfer.id,
                    "stripe_transfer_id": transfer.id,
                    "updated_at": now,
                }},
            )
            paid_ids.append(r["id"])
            transfers_out.append({
                "commission_id": r["id"],
                "transfer_id": transfer.id,
                "amount": r["amount"],
            })

    return {
        "paid": len(paid_ids),
        "failed": failed,
        "transfers": transfers_out,
    }


class ElevenLabsKeyRequest(BaseModel):
    api_key: str


class LLMKeyRequest(BaseModel):
    api_key: str


class PreferredProviderRequest(BaseModel):
    provider: str  # "openai" | "anthropic"


def _user_response_from(user: User) -> "UserResponse":
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        has_elevenlabs_key=bool(user.elevenlabs_api_key),
        has_openai_key=bool(user.openai_api_key),
        has_anthropic_key=bool(user.anthropic_api_key),
        preferred_llm_provider=(user.preferred_llm_provider or "anthropic"),
        referral_code=user.referral_code,
        is_super_admin=user.is_super_admin,
        created_at=user.created_at,
    )


@api_router.get("/auth/me/llm-providers")
async def list_llm_providers():
    """Public — the LLM providers the app knows how to route through."""
    return {
        "providers": [
            {"key": "anthropic", "label": PROVIDER_LABELS["anthropic"], "model": PROVIDER_DEFAULT_MODEL["anthropic"]},
            {"key": "openai",    "label": PROVIDER_LABELS["openai"],    "model": PROVIDER_DEFAULT_MODEL["openai"]},
        ],
        "default": "anthropic",
    }


@api_router.put("/auth/me/openai-key", response_model=UserResponse)
async def set_openai_key(
    payload: LLMKeyRequest,
    current_user: User = Depends(get_current_user),
):
    key = (payload.api_key or "").strip()
    if not key or not key.startswith("sk-") or len(key) < 20:
        raise HTTPException(status_code=400, detail="OpenAI API key looks invalid (expected sk-... at least 20 chars).")
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"openai_api_key": encrypt_secret(key)}},
    )
    current_user.openai_api_key = key
    return _user_response_from(current_user)


@api_router.delete("/auth/me/openai-key", response_model=UserResponse)
async def clear_openai_key(current_user: User = Depends(get_current_user)):
    await db.users.update_one(
        {"id": current_user.id},
        {"$unset": {"openai_api_key": ""}},
    )
    current_user.openai_api_key = None
    return _user_response_from(current_user)


@api_router.put("/auth/me/anthropic-key", response_model=UserResponse)
async def set_anthropic_key(
    payload: LLMKeyRequest,
    current_user: User = Depends(get_current_user),
):
    key = (payload.api_key or "").strip()
    if not key or not key.startswith("sk-") or len(key) < 20:
        raise HTTPException(status_code=400, detail="Anthropic API key looks invalid (expected sk-... at least 20 chars).")
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"anthropic_api_key": encrypt_secret(key)}},
    )
    current_user.anthropic_api_key = key
    return _user_response_from(current_user)


@api_router.delete("/auth/me/anthropic-key", response_model=UserResponse)
async def clear_anthropic_key(current_user: User = Depends(get_current_user)):
    await db.users.update_one(
        {"id": current_user.id},
        {"$unset": {"anthropic_api_key": ""}},
    )
    current_user.anthropic_api_key = None
    return _user_response_from(current_user)


@api_router.put("/auth/me/preferred-provider", response_model=UserResponse)
async def set_preferred_provider(
    payload: PreferredProviderRequest,
    current_user: User = Depends(get_current_user),
):
    prov = (payload.provider or "").strip().lower()
    if prov not in ("openai", "anthropic"):
        raise HTTPException(status_code=400, detail="Provider must be 'openai' or 'anthropic'.")
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"preferred_llm_provider": prov}},
    )
    current_user.preferred_llm_provider = prov
    return _user_response_from(current_user)


@api_router.put("/auth/me/elevenlabs-key", response_model=UserResponse)
async def set_elevenlabs_key(
    payload: ElevenLabsKeyRequest,
    current_user: User = Depends(get_current_user),
):
    key = (payload.api_key or "").strip()
    if not key or len(key) < 20:
        raise HTTPException(status_code=400, detail="ElevenLabs API key looks invalid.")
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"elevenlabs_api_key": encrypt_secret(key)}},
    )
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        has_elevenlabs_key=True,
        referral_code=current_user.referral_code,
        is_super_admin=current_user.is_super_admin,
        created_at=current_user.created_at,
    )


@api_router.delete("/auth/me/elevenlabs-key", response_model=UserResponse)
async def clear_elevenlabs_key(current_user: User = Depends(get_current_user)):
    await db.users.update_one(
        {"id": current_user.id},
        {"$unset": {"elevenlabs_api_key": ""}},
    )
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        has_elevenlabs_key=False,
        referral_code=current_user.referral_code,
        is_super_admin=current_user.is_super_admin,
        created_at=current_user.created_at,
    )

# --- DOCUMENT ROUTES ---

@api_router.post("/documents", response_model=DocumentResponse)
async def create_document(doc_data: DocumentCreate, current_user: User = Depends(get_current_user)):
    document = DocumentModel(
        title=doc_data.title,
        content=doc_data.content or "",
        user_id=current_user.id,
        format=doc_data.format or "6x9"
    )
    
    # Create initial version
    initial_version = Version(
        content=document.content,
        created_by=current_user.id,
        version_number=1
    )
    document.versions.append(initial_version)
    
    doc = document.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    doc['versions'] = [{
        **v,
        'created_at': v['created_at'].isoformat() if isinstance(v['created_at'], datetime) else v['created_at']
    } for v in doc['versions']]
    
    await db.documents.insert_one(doc)
    
    fresh = await db.documents.find_one({"id": document.id}, {"_id": 0})
    return _build_document_response(fresh, current_user.id)

@api_router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(current_user: User = Depends(get_current_user)):
    docs = await db.documents.find({"user_id": current_user.id}, {"_id": 0}).to_list(1000)
    return [_build_document_response(d, current_user.id) for d in docs]

@api_router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _build_document_response(doc, current_user.id)

@api_router.put("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(document_id: str, update_data: DocumentUpdate, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    update_fields = {}
    if update_data.title is not None:
        update_fields['title'] = update_data.title
    if update_data.content is not None:
        update_fields['content'] = update_data.content
        # Create new version
        versions = doc.get('versions', [])
        new_version = {
            'id': str(uuid.uuid4()),
            'content': update_data.content,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'created_by': current_user.id,
            'version_number': len(versions) + 1
        }
        versions.append(new_version)
        update_fields['versions'] = versions
    if update_data.format is not None:
        update_fields['format'] = update_data.format
    if update_data.metadata is not None:
        update_fields['metadata'] = update_data.metadata.model_dump()
    
    update_fields['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    await db.documents.update_one(
        {"id": document_id},
        {"$set": update_fields}
    )
    
    updated_doc = await db.documents.find_one({"id": document_id}, {"_id": 0})
    return _build_document_response(updated_doc, current_user.id)

@api_router.delete("/documents/{document_id}")
async def delete_document(document_id: str, current_user: User = Depends(get_current_user)):
    result = await db.documents.delete_one({"id": document_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted"}

# --- UPLOAD ROUTE ---

@api_router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    filename = file.filename or "untitled"
    lower = filename.lower()

    if lower.endswith(".pages"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Apple Pages files (.pages) are not supported directly. "
                "Please open the file in Pages, then choose File → Export To → Word (.docx), "
                "and upload the resulting .docx file."
            ),
        )

    if lower.endswith(".docx"):
        file_bytes = await file.read()
        try:
            content = docx_to_html(file_bytes)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not parse .docx file: {exc}")
    elif lower.endswith(".txt"):
        file_bytes = await file.read()
        try:
            raw = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw = file_bytes.decode("latin-1", errors="replace")
        # Convert plain text paragraphs (blank-line separated) into HTML
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
        content = "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs) or "<p></p>"
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .docx or .txt file. "
                   "For .pages files, export from Apple Pages as .docx first.",
        )

    title = filename.rsplit('.', 1)[0]
    document = DocumentModel(
        title=title,
        content=content,
        user_id=current_user.id,
        original_filename=filename,
    )

    initial_version = Version(
        content=content,
        created_by=current_user.id,
        version_number=1,
    )
    document.versions.append(initial_version)

    doc = document.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    doc['versions'] = [{
        **v,
        'created_at': v['created_at'].isoformat() if isinstance(v['created_at'], datetime) else v['created_at']
    } for v in doc['versions']]

    await db.documents.insert_one(doc)

    fresh = await db.documents.find_one({"id": document.id}, {"_id": 0})
    return _build_document_response(fresh, current_user.id)

# --- VERSION ROUTES ---

@api_router.get("/documents/{document_id}/versions", response_model=List[Version])
async def get_versions(document_id: str, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    versions = doc.get('versions', [])
    result = []
    for v in versions:
        if isinstance(v['created_at'], str):
            v['created_at'] = datetime.fromisoformat(v['created_at'])
        result.append(Version(**v))
    
    return result

# --- COMMENT ROUTES ---

@api_router.post("/documents/{document_id}/comments", response_model=Comment)
async def add_comment(document_id: str, comment_data: CommentCreate, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    comment = Comment(
        user_id=current_user.id,
        user_name=current_user.name,
        content=comment_data.content,
        position=comment_data.position
    )
    
    comments = doc.get('comments', [])
    comment_dict = comment.model_dump()
    comment_dict['created_at'] = comment_dict['created_at'].isoformat()
    comments.append(comment_dict)
    
    await db.documents.update_one(
        {"id": document_id},
        {"$set": {"comments": comments}}
    )
    
    return comment

@api_router.get("/documents/{document_id}/comments", response_model=List[Comment])
async def get_comments(document_id: str, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    comments = doc.get('comments', [])
    result = []
    for c in comments:
        if isinstance(c['created_at'], str):
            c['created_at'] = datetime.fromisoformat(c['created_at'])
        result.append(Comment(**c))
    
    return result

# --- AI EDITORIAL ROUTES ---

AI_TOOLS = {
    "tighten": "Tightened prose",
    "clarity": "Improved clarity",
    "blurb": "Back-cover blurb",
    "chapter_titles": "Chapter titles",
    "synopsis": "Synopsis",
}


class AIEditRequest(BaseModel):
    tool: str
    content: Optional[str] = None  # If omitted, uses the saved document content


# --- WRITING AGENT (chat + Cmd-K inline command) ---

class AgentChatMessage(BaseModel):
    role: str          # 'user' | 'assistant'
    content: str


class AgentChatRequest(BaseModel):
    document_id: str
    message: str
    voice: Optional[str] = "match_my_voice"
    session_id: Optional[str] = None  # client-supplied per-document session id


class AgentInlineRequest(BaseModel):
    document_id: Optional[str] = None
    selected_text: str
    instruction: str
    voice: Optional[str] = "match_my_voice"


async def _user_has_active_subscription(user_id: str) -> bool:
    """True if the user has a paid plan that hasn't expired."""
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    return is_subscription_active(sub)


def _voice_sample_from_doc(doc: dict, max_chars: int = 3000) -> Optional[str]:
    """Pull a representative voice sample from the document for voice-matching."""
    if not doc:
        return None
    content = doc.get("content") or ""
    if not content:
        return None
    # Strip HTML inline using a small helper (we already have one in ai_editor)
    import re as _re
    text = _re.sub(r"<br\s*/?>", "\n", content)
    text = _re.sub(r"</p\s*>", "\n\n", text)
    text = _re.sub(r"</(h[1-6])\s*>", "\n\n", text)
    text = _re.sub(r"<[^>]+>", "", text)
    text = _re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= max_chars:
        return text or None
    # Take the middle of the document — usually the most representative voice
    mid = len(text) // 2
    half = max_chars // 2
    return text[max(0, mid - half): mid + half]


@api_router.get("/ai/agent/voices")
async def list_agent_voices():
    """Public — voice presets the writer can choose from."""
    return {
        "voices": [
            {"key": k, "label": v["label"], "description": v["description"]}
            for k, v in VOICE_PRESETS.items()
        ]
    }


@api_router.get("/ai/agent/quota")
async def writing_agent_quota(current_user: User = Depends(get_current_user)):
    """Read-only quota state so the UI can show 'N of 5 left today'."""
    active = await _user_has_active_subscription(current_user.id)
    return await agent_quota_snapshot(db, user_id=current_user.id, subscription_active=active)


@api_router.post("/ai/agent/chat")
async def writing_agent_chat(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
):
    """One turn with the per-document writing agent."""
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(msg) > 4000:
        raise HTTPException(status_code=400, detail="Message is too long (4000 chars max).")

    doc = await db.documents.find_one(
        {"id": payload.document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Resolve provider + key (BYO bypasses quota entirely)
    provider, model_name, api_key, is_byo = resolve_provider_and_key(
        preferred_provider=current_user.preferred_llm_provider,
        user_openai_key=current_user.openai_api_key,
        user_anthropic_key=current_user.anthropic_api_key,
    )

    # Quota gate — only apply when NOT using the user's own key
    sub_active = await _user_has_active_subscription(current_user.id)
    if is_byo:
        remaining, daily_limit = None, None
    else:
        remaining, daily_limit = await agent_check_and_charge(
            db, user_id=current_user.id, subscription_active=sub_active,
        )
        if remaining == -1:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "agent_quota_exceeded",
                    "message": (
                        f"You've used all {daily_limit} free agent messages today. "
                        "Upgrade to Author Pro, or plug in your own OpenAI / Anthropic key in Settings."
                    ),
                    "limit": daily_limit,
                    "used": daily_limit,
                    "remaining": 0,
                    "resets_at": "midnight UTC",
                },
            )

    # Load history for this document/session
    session_id = payload.session_id or f"doc-{payload.document_id}"
    history_doc = await db.agent_sessions.find_one(
        {"user_id": current_user.id, "document_id": payload.document_id, "session_id": session_id},
        {"_id": 0},
    )
    history: List[dict] = (history_doc or {}).get("messages", [])

    voice_sample = _voice_sample_from_doc(doc) if payload.voice in (None, "match_my_voice") else None

    try:
        reply = await agent_chat(
            user_message=msg,
            history=history,
            document_title=doc.get("title"),
            document_html=doc.get("content"),
            voice=payload.voice,
            voice_sample=voice_sample,
            session_id=session_id,
            provider=provider,
            model=model_name,
            api_key=api_key,
        )
    except Exception as exc:
        # Roll back the quota increment on upstream failure so users don't
        # lose a free message to a transient LLM error.
        if not is_byo:
            await agent_refund_charge(
                db, user_id=current_user.id, subscription_active=sub_active,
            )
        logger.exception("Writing agent chat failed")
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}")

    now_iso = datetime.now(timezone.utc).isoformat()
    new_history = history + [
        {"role": "user", "content": msg, "ts": now_iso},
        {"role": "assistant", "content": reply, "ts": now_iso},
    ]
    # Cap stored history to last 40 turns to keep documents lean
    new_history = new_history[-40:]

    await db.agent_sessions.update_one(
        {"user_id": current_user.id, "document_id": payload.document_id, "session_id": session_id},
        {"$set": {
            "user_id": current_user.id,
            "document_id": payload.document_id,
            "session_id": session_id,
            "messages": new_history,
            "voice": payload.voice or "match_my_voice",
            "updated_at": now_iso,
        }},
        upsert=True,
    )

    return {
        "reply": reply,
        "session_id": session_id,
        "history_count": len(new_history),
        "provider": provider,
        "model": model_name,
        "byo_key": is_byo,
        "quota": {
            "unlimited": daily_limit is None,
            "remaining": remaining,
            "limit": daily_limit,
        },
    }


@api_router.get("/ai/agent/history/{document_id}")
async def writing_agent_history(
    document_id: str,
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Return the saved conversation history for this document/session."""
    sid = session_id or f"doc-{document_id}"
    sess = await db.agent_sessions.find_one(
        {"user_id": current_user.id, "document_id": document_id, "session_id": sid},
        {"_id": 0},
    )
    return {
        "session_id": sid,
        "messages": (sess or {}).get("messages", []),
        "voice": (sess or {}).get("voice", "match_my_voice"),
    }


@api_router.delete("/ai/agent/history/{document_id}")
async def clear_writing_agent_history(
    document_id: str,
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Wipe the saved conversation history for this document."""
    sid = session_id or f"doc-{document_id}"
    await db.agent_sessions.delete_one(
        {"user_id": current_user.id, "document_id": document_id, "session_id": sid},
    )
    return {"cleared": True}


@api_router.post("/ai/agent/command")
async def writing_agent_inline_command(
    payload: AgentInlineRequest,
    current_user: User = Depends(get_current_user),
):
    """Cmd-K behaviour: take selected text + an instruction, return rewritten text."""
    provider, model_name, api_key, is_byo = resolve_provider_and_key(
        preferred_provider=current_user.preferred_llm_provider,
        user_openai_key=current_user.openai_api_key,
        user_anthropic_key=current_user.anthropic_api_key,
    )
    sub_active = await _user_has_active_subscription(current_user.id)
    if is_byo:
        remaining, daily_limit = None, None
    else:
        remaining, daily_limit = await agent_check_and_charge(
            db, user_id=current_user.id, subscription_active=sub_active,
        )
        if remaining == -1:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "agent_quota_exceeded",
                    "message": (
                        f"You've used all {daily_limit} free agent messages today. "
                        "Upgrade to Author Pro, or plug in your own OpenAI / Anthropic key in Settings."
                    ),
                    "limit": daily_limit,
                    "used": daily_limit,
                    "remaining": 0,
                    "resets_at": "midnight UTC",
                },
            )

    doc = None
    if payload.document_id:
        doc = await db.documents.find_one(
            {"id": payload.document_id, "user_id": current_user.id}, {"_id": 0}
        )
    voice_sample = _voice_sample_from_doc(doc) if (doc and payload.voice in (None, "match_my_voice")) else None
    try:
        result = await run_inline_command(
            selected_text=payload.selected_text,
            instruction=payload.instruction,
            document_title=(doc or {}).get("title"),
            voice=payload.voice,
            voice_sample=voice_sample,
            provider=provider,
            model=model_name,
            api_key=api_key,
        )
    except ValueError as exc:
        if not is_byo:
            await agent_refund_charge(
                db, user_id=current_user.id, subscription_active=sub_active,
            )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        if not is_byo:
            await agent_refund_charge(
                db, user_id=current_user.id, subscription_active=sub_active,
            )
        logger.exception("Inline command failed")
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}")
    return {
        "result": result,
        "provider": provider,
        "model": model_name,
        "byo_key": is_byo,
        "quota": {
            "unlimited": daily_limit is None,
            "remaining": remaining,
            "limit": daily_limit,
        },
    }


@api_router.get("/ai/tools")
async def list_ai_tools():
    return {"tools": [{"key": k, "label": v} for k, v in AI_TOOLS.items()]}


@api_router.post("/documents/{document_id}/ai")
async def run_ai_edit(
    document_id: str,
    payload: AIEditRequest,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if payload.tool not in AI_TOOLS:
        raise HTTPException(status_code=400, detail=f"Unknown AI tool: {payload.tool}")

    html_content = payload.content if payload.content is not None else (doc.get("content") or "")
    if not html_content.strip():
        raise HTTPException(status_code=400, detail="Document is empty — add content before running AI tools.")

    metadata = doc.get("metadata") or {}
    title = doc.get("title")
    author = metadata.get("author") or current_user.name

    try:
        if payload.tool == "tighten":
            result = await tighten_prose(html_content)
            result_type = "prose"
        elif payload.tool == "clarity":
            result = await improve_clarity(html_content)
            result_type = "prose"
        elif payload.tool == "blurb":
            result = await generate_blurb(html_content, title, author)
            result_type = "blurb"
        elif payload.tool == "chapter_titles":
            result = await suggest_chapter_titles(html_content)
            result_type = "list"
        else:  # synopsis
            result = await generate_synopsis(html_content, title, author)
            result_type = "synopsis"
    except Exception as exc:
        logger.exception("AI editorial call failed")
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}")

    return {
        "tool": payload.tool,
        "label": AI_TOOLS[payload.tool],
        "result": result,
        "result_type": result_type,
    }


# --- COPY-EDIT (FULL EDITORIAL PASS) ---

class CopyEditRequest(BaseModel):
    content: Optional[str] = None
    style_guide: Optional[str] = "house"


@api_router.get("/copyedit/style-guides")
async def list_style_guides():
    return {"style_guides": [{"key": k, "description": v} for k, v in STYLE_GUIDES.items()]}


@api_router.post("/documents/{document_id}/copyedit")
async def run_copyedit(
    document_id: str,
    payload: CopyEditRequest,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    html_content = payload.content if payload.content is not None else (doc.get("content") or "")
    if not html_content.strip():
        raise HTTPException(status_code=400, detail="Document is empty — add content before running the copy editor.")

    style_guide = (payload.style_guide or "house").lower()
    if style_guide not in STYLE_GUIDES:
        style_guide = "house"

    try:
        result = await run_copyedit_pass(html_content=html_content, style_guide=style_guide)
    except Exception as exc:
        logger.exception("Copy-edit pass failed")
        raise HTTPException(status_code=502, detail=f"Copy editor service error: {exc}")

    return result


# --- AUDIO STUDIO (TTS / AUDIOBOOK) ---

class NarrateRequest(BaseModel):
    text: Optional[str] = None
    content: Optional[str] = None  # HTML; used when text is omitted
    voice: Optional[str] = "onyx"
    speed: Optional[float] = 1.0


@api_router.get("/tts/voices")
async def tts_voices():
    return {"voices": audio_list_voices()}


@api_router.post("/tts/preview")
async def tts_preview(payload: NarrateRequest, current_user: User = Depends(get_current_user)):
    """Short narration preview — used by 'Read Aloud' in the editor."""
    try:
        if payload.text:
            mp3 = await narrate_text(
                text=payload.text,
                voice=payload.voice or "onyx",
                speed=payload.speed or 1.0,
            )
        elif payload.content:
            mp3 = await narrate_preview(
                html_content=payload.content,
                voice=payload.voice or "onyx",
                speed=payload.speed or 1.0,
            )
        else:
            raise HTTPException(status_code=400, detail="Provide either 'text' or 'content'.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("TTS preview failed")
        raise HTTPException(status_code=502, detail=f"TTS service error: {exc}")

    return Response(
        content=mp3,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


@api_router.post("/documents/{document_id}/audiobook")
async def generate_audiobook(
    document_id: str,
    voice: str = "onyx",
    speed: float = 1.0,
    current_user: User = Depends(get_current_user),
):
    """Generate a full MP3 audiobook of the manuscript and return as a download."""
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    html_content = doc.get("content") or ""
    title = doc.get("title") or "Untitled"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "audiobook"

    try:
        mp3 = await narrate_audiobook(
            html_content=html_content,
            voice=voice,
            speed=speed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except Exception as exc:
        logger.exception("Audiobook generation failed")
        raise HTTPException(status_code=502, detail=f"Audiobook service error: {exc}")

    await db.documents.update_one(
        {"id": document_id},
        {"$set": {"last_audio_export_at": datetime.now(timezone.utc).isoformat()}},
    )
    return Response(
        content=mp3,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_audiobook.mp3"',
            "X-Audiobook-Voice": voice,
            "X-Audiobook-Speed": str(speed),
        },
    )


@api_router.get("/documents/{document_id}/audiobook/chapters/preview")
async def preview_audiobook_chapters(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return the detected chapter list so the UI can preview before exporting."""
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chapters = split_into_chapters(doc.get("content") or "")
    plain_chapters = []
    for idx, (title, html) in enumerate(chapters, start=1):
        from bs4 import BeautifulSoup as _BS
        text = _BS(html, "html.parser").get_text(separator=" ", strip=True)
        plain_chapters.append({
            "index": idx,
            "title": title,
            "char_count": len(text),
            "word_count": len(text.split()) if text else 0,
        })
    return {"chapters": plain_chapters, "total": len(plain_chapters)}


@api_router.post("/documents/{document_id}/audiobook/chapters")
async def export_audiobook_chapters(
    document_id: str,
    voice: str = "onyx",
    speed: float = 1.0,
    current_user: User = Depends(get_current_user),
):
    """Per-chapter audiobook export — returns a ZIP of one MP3 per chapter."""
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    title = doc.get("title") or "Untitled"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "audiobook"

    try:
        zip_bytes = await export_chapters_zip(
            html_content=doc.get("content") or "",
            title=title,
            voice=voice,
            speed=speed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Per-chapter audiobook export failed")
        raise HTTPException(status_code=502, detail=f"Audiobook service error: {exc}")

    await db.documents.update_one(
        {"id": document_id},
        {"$set": {"last_audio_export_at": datetime.now(timezone.utc).isoformat()}},
    )
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_chapters.zip"',
        },
    )


# --- ELEVENLABS (PREMIUM TTS + VOICE CLONING) ---

def _require_elevenlabs_key(current_user: User) -> str:
    key = current_user.elevenlabs_api_key
    if not key:
        raise HTTPException(
            status_code=400,
            detail="No ElevenLabs API key on file. Save your key in Audio Studio first.",
        )
    return key


class ElevenLabsNarrateRequest(BaseModel):
    text: Optional[str] = None
    content: Optional[str] = None
    voice_id: str
    model_id: Optional[str] = None
    stability: Optional[float] = 0.5
    similarity_boost: Optional[float] = 0.75


@api_router.get("/elevenlabs/voices")
async def elevenlabs_voices(current_user: User = Depends(get_current_user)):
    key = _require_elevenlabs_key(current_user)
    try:
        voices = await asyncio.to_thread(eleven_list_voices, key)
    except ElevenLabsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        logger.exception("ElevenLabs voice list failed")
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {exc}")
    return {"voices": voices}


@api_router.post("/elevenlabs/preview")
async def elevenlabs_preview(
    payload: ElevenLabsNarrateRequest,
    current_user: User = Depends(get_current_user),
):
    key = _require_elevenlabs_key(current_user)
    if not payload.voice_id:
        raise HTTPException(status_code=400, detail="voice_id is required.")
    model_id = payload.model_id or ELEVEN_DEFAULT_MODEL

    try:
        if payload.text:
            mp3 = await asyncio.to_thread(
                eleven_narrate_text,
                api_key=key, text=payload.text, voice_id=payload.voice_id,
                model_id=model_id,
                stability=payload.stability or 0.5,
                similarity_boost=payload.similarity_boost or 0.75,
            )
        elif payload.content:
            mp3 = await asyncio.to_thread(
                eleven_narrate_preview,
                api_key=key, html_content=payload.content,
                voice_id=payload.voice_id, model_id=model_id,
            )
        else:
            raise HTTPException(status_code=400, detail="Provide either 'text' or 'content'.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ElevenLabsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ElevenLabsServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("ElevenLabs preview failed")
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {exc}")

    return Response(content=mp3, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@api_router.post("/documents/{document_id}/elevenlabs-audiobook")
async def elevenlabs_audiobook(
    document_id: str,
    voice_id: str,
    model_id: Optional[str] = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    current_user: User = Depends(get_current_user),
):
    key = _require_elevenlabs_key(current_user)
    if not voice_id:
        raise HTTPException(status_code=400, detail="voice_id is required.")

    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    html_content = doc.get("content") or ""
    title = doc.get("title") or "Untitled"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "audiobook"

    try:
        mp3 = await asyncio.to_thread(
            eleven_narrate_audiobook,
            api_key=key, html_content=html_content, voice_id=voice_id,
            model_id=model_id or ELEVEN_DEFAULT_MODEL,
            stability=stability, similarity_boost=similarity_boost,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except ElevenLabsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ElevenLabsServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("ElevenLabs audiobook failed")
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {exc}")

    await db.documents.update_one(
        {"id": document_id},
        {"$set": {"last_audio_export_at": datetime.now(timezone.utc).isoformat()}},
    )
    return Response(
        content=mp3,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_elevenlabs.mp3"',
            "X-Audiobook-Voice-Id": voice_id,
            "X-Audiobook-Model": model_id or ELEVEN_DEFAULT_MODEL,
        },
    )


# --- AUDIOBOOK UPLOADS (author-supplied MP3) ---

@api_router.post("/documents/{document_id}/audiobook/upload")
async def upload_audiobook(
    document_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    data = await file.read()
    try:
        upload = save_audio_upload(current_user.id, document_id, file.filename or "audio.mp3", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.documents.update_one(
        {"id": document_id},
        {"$set": {"audio_upload": upload, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    return {
        "document_id": document_id,
        "filename": upload["filename"],
        "size_bytes": upload["size"],
        "uploaded": True,
    }


@api_router.get("/documents/{document_id}/audiobook")
async def fetch_audiobook(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    upload = find_audio_upload(doc)
    if not upload:
        raise HTTPException(status_code=404, detail="No audiobook uploaded for this document.")
    ext = upload["ext"]
    title = doc.get("title") or "Untitled"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "audiobook"
    return Response(
        content=fetch_audio_bytes(upload["storage_path"]),
        media_type=audio_media_type(ext),
        headers={"Content-Disposition": f'inline; filename="{safe_name}.{ext}"'},
    )


@api_router.delete("/documents/{document_id}/audiobook")
async def remove_audiobook(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    deleted = delete_audio_upload(doc)
    if deleted:
        await db.documents.update_one(
            {"id": document_id},
            {"$unset": {"audio_upload": ""}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    return {"deleted": deleted}


@api_router.get("/documents/{document_id}/audiobook/info")
async def audiobook_info(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    upload = find_audio_upload(doc)
    if not upload:
        return {"uploaded": False}
    return {
        "uploaded": True,
        "filename": upload["filename"],
        "extension": upload["ext"],
        "size_bytes": upload["size"],
    }


# --- COVER IMAGE UPLOADS ---

@api_router.post("/documents/{document_id}/cover/upload")
async def upload_cover(
    document_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    data = await file.read()
    try:
        upload = save_cover_upload(current_user.id, document_id, file.filename or "cover.jpg", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.documents.update_one(
        {"id": document_id},
        {"$set": {
            "cover_upload": upload,
            "cover_image_ext": upload["ext"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {
        "document_id": document_id,
        "filename": upload["filename"],
        "extension": upload["ext"],
        "size_bytes": upload["size"],
        "uploaded": True,
    }


@api_router.get("/documents/{document_id}/cover")
async def fetch_cover(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    upload = find_cover_upload(doc)
    if not upload:
        raise HTTPException(status_code=404, detail="No cover uploaded for this document.")
    ext = upload["ext"]
    return Response(
        content=fetch_cover_bytes(upload["storage_path"]),
        media_type=cover_media_type(ext),
        headers={"Cache-Control": "private, max-age=60"},
    )


@api_router.delete("/documents/{document_id}/cover")
async def remove_cover(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    deleted = delete_cover_upload(doc)
    if deleted:
        await db.documents.update_one(
            {"id": document_id},
            {
                "$unset": {"cover_upload": ""},
                "$set": {"cover_image_ext": None, "updated_at": datetime.now(timezone.utc).isoformat()},
            },
        )
    return {"deleted": deleted}


# --- COVER PDF (for KDP paperback submission) ---

@api_router.post("/documents/{document_id}/cover/pdf")
async def cover_to_pdf(
    document_id: str,
    trim: Optional[str] = None,
    include_bleed: bool = True,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    upload = find_cover_upload(doc)
    if not upload:
        raise HTTPException(status_code=404, detail="No cover image uploaded. Upload a cover first.")

    trim_key = (trim or doc.get("format") or "6x9").strip()
    if trim_key not in KDP_TRIM_SIZES:
        trim_key = "6x9"

    title = doc.get("title") or "Untitled"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "cover"

    try:
        pdf_bytes = image_to_pdf(
            image_bytes=fetch_cover_bytes(upload["storage_path"]),
            trim_key=trim_key,
            title=f"{title}: Cover",
            include_bleed=include_bleed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Cover-to-PDF failed")
        raise HTTPException(status_code=500, detail=f"Cover PDF generation failed: {exc}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_cover_{trim_key}.pdf"',
            "X-Trim-Size": trim_key,
            "X-Bleed": "0.125in" if include_bleed else "none",
        },
    )


@api_router.post("/tools/image-to-pdf")
async def generic_image_to_pdf(
    file: UploadFile = File(...),
    trim: str = "6x9",
    current_user: User = Depends(get_current_user),
):
    """Generic JPG/PNG/WebP → PDF converter at any KDP trim size."""
    if trim not in KDP_TRIM_SIZES:
        trim = "6x9"
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 20 MB).")
    try:
        pdf_bytes = image_to_pdf(
            image_bytes=data,
            trim_key=trim,
            title=(file.filename or "Image"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Generic image-to-PDF failed")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}")

    base = (file.filename or "image").rsplit(".", 1)[0]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_") or "image"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}_{trim}.pdf"',
            "X-Trim-Size": trim,
        },
    )


# --- VOICE MEMOS (per-paragraph audio annotations) ---

@api_router.post("/documents/{document_id}/memos")
async def create_voice_memo(
    document_id: str,
    file: UploadFile = File(...),
    paragraph_index: Optional[int] = None,
    title: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    data = await file.read()
    memo_id = str(uuid.uuid4())
    try:
        upload = save_voice_memo(current_user.id, document_id, memo_id, file.filename or "memo.webm", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    memo = VoiceMemo(
        id=memo_id,
        title=(title or None),
        paragraph_index=paragraph_index,
        ext=upload["ext"],
        size_bytes=upload["size"],
    )
    memo_doc = memo.model_dump()
    memo_doc["created_at"] = memo_doc["created_at"].isoformat()
    memo_doc["storage_path"] = upload["storage_path"]

    await db.documents.update_one(
        {"id": document_id},
        {
            "$push": {"memos": memo_doc},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
    )
    return memo_doc


@api_router.get("/documents/{document_id}/memos")
async def list_voice_memos(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0, "memos": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"memos": doc.get("memos", [])}


@api_router.get("/documents/{document_id}/memos/{memo_id}")
async def fetch_voice_memo_audio(
    document_id: str,
    memo_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    memo = find_memo_file(doc, memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo audio not found")
    ext = memo["ext"]
    return Response(
        content=fetch_memo_bytes(memo["storage_path"]),
        media_type=memo_media_type(ext),
        headers={"Cache-Control": "private, max-age=60"},
    )


@api_router.post("/documents/{document_id}/memos/{memo_id}/transcribe")
async def transcribe_voice_memo(
    document_id: str,
    memo_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # If we already transcribed this memo, return the cached transcript
    memos = doc.get("memos") or []
    memo_record = next((m for m in memos if m.get("id") == memo_id), None)
    if memo_record and memo_record.get("transcript"):
        return {"text": memo_record["transcript"], "cached": True}

    found = find_memo_file(doc, memo_id)
    if not found:
        raise HTTPException(status_code=404, detail="Memo audio not found")
    ext = found["ext"]

    try:
        text = await transcribe_audio(
            data=fetch_memo_bytes(found["storage_path"]),
            filename=f"memo.{ext}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Voice-memo transcription failed")
        raise HTTPException(status_code=502, detail=f"Transcription service error: {exc}")

    await db.documents.update_one(
        {"id": document_id, "memos.id": memo_id},
        {"$set": {"memos.$.transcript": text}},
    )
    return {"text": text, "cached": False}


@api_router.delete("/documents/{document_id}/memos/{memo_id}")
async def delete_voice_memo(
    document_id: str,
    memo_id: str,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_memo_file(doc, memo_id)
    result = await db.documents.update_one(
        {"id": document_id},
        {
            "$pull": {"memos": {"id": memo_id}},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
    )
    return {"deleted": result.modified_count > 0}


# --- DICTATION (Whisper STT) ---

@api_router.post("/transcribe")
async def transcribe_dictation(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Transcribe a recorded audio chunk into plain text for the manuscript editor."""
    data = await file.read()
    try:
        text = await transcribe_audio(
            data=data,
            filename=file.filename or "recording.webm",
            language=language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=502, detail=f"Transcription service error: {exc}")
    return {"text": text, "language": language, "filename": file.filename}


# --- EXPORT ROUTES ---

@api_router.get("/export/formats")
async def list_export_formats():
    """Return all supported KDP trim sizes plus digital formats."""
    return {
        "print_trim_sizes": [
            {"key": k, "width_in": w, "height_in": h, "label": _trim_label(k, w, h)}
            for k, (w, h) in KDP_TRIM_SIZES.items()
        ],
        "digital": [
            {"key": "epub", "label": "ePub (Digital eBook)"},
        ],
    }


def _trim_label(key: str, w: float, h: float) -> str:
    common = {
        "5x8": "5×8 — Mass-market paperback",
        "5.06x7.81": "5.06×7.81 — Pocket / A-format",
        "5.25x8": "5.25×8 — Trade",
        "5.5x8.5": "5.5×8.5 — Digest",
        "6x9": "6×9 — Standard novel (most popular)",
        "6.14x9.21": "6.14×9.21 — UK Royal",
        "6.69x9.61": "6.69×9.61 — UK Crown Quarto",
        "7x10": "7×10 — Textbook",
        "7.44x9.69": "7.44×9.69 — Large textbook",
        "7.5x9.25": "7.5×9.25 — Crown Quarto",
        "8x10": "8×10 — Workbook",
        "8.5x11": "8.5×11 — Magazine / Letter",
    }
    return common.get(key, f"{w}×{h}")


@api_router.post("/documents/{document_id}/export")
async def export_document(
    document_id: str,
    format: str,
    trim: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Generate and return a downloadable file.
    - format: 'pdf' or 'epub'
    - trim: trim-size key for PDF (e.g. '6x9', '8.5x11'); defaults to document.format or '6x9'
    """
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    title = doc.get("title") or "Untitled"
    content = doc.get("content") or ""
    metadata = doc.get("metadata") or {}
    author = metadata.get("author") or current_user.name
    publisher = metadata.get("publisher")

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "document"

    if format == "pdf":
        trim_key = trim or doc.get("format") or "6x9"
        if trim_key not in KDP_TRIM_SIZES:
            trim_key = "6x9"
        pdf_bytes = generate_pdf(
            title=title,
            author=author,
            html_content=content,
            trim_key=trim_key,
            publisher=publisher,
        )
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {"last_pdf_export_at": datetime.now(timezone.utc).isoformat()}},
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}_{trim_key}.pdf"',
                "X-Trim-Size": trim_key,
            },
        )

    if format == "epub":
        epub_bytes = generate_epub(
            title=title,
            author=author,
            html_content=content,
            publisher=publisher,
        )
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {"last_epub_export_at": datetime.now(timezone.utc).isoformat()}},
        )
        return Response(
            content=epub_bytes,
            media_type="application/epub+zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}.epub"',
            },
        )

    raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")


# --- PUBLISHING PARTNER ROUTES (preparation only, not direct API integrations) ---
@api_router.post("/integrations/kdp")
async def publish_to_kdp(document_id: str, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Mocked KDP integration
    return {
        "message": "Document prepared for Amazon KDP",
        "status": "ready",
        "document_id": document_id,
        "title": doc['title'],
        "note": "This is a demo integration. Connect your KDP account to publish."
    }

@api_router.post("/integrations/lulu")
async def publish_to_lulu(document_id: str, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Mocked LULU integration
    return {
        "message": "Document prepared for LULU",
        "status": "ready",
        "document_id": document_id,
        "title": doc['title'],
        "note": "This is a demo integration. Connect your LULU account to publish."
    }

# Root route
@api_router.get("/")
async def root():
    return {"message": "Divine Leadership Press API", "status": "running"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',')
        if origin.strip() and origin.strip() != '*'
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


@app.on_event("startup")
async def _init_storage_on_startup():
    try:
        init_object_storage()
    except Exception as exc:
        logger.error(f"Object storage init failed at startup: {exc}")
