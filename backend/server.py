from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Depends, Header
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
    media_type_for as audio_media_type,
    ALLOWED_EXTENSIONS as AUDIO_ALLOWED_EXTENSIONS,
)
from cover_uploads import (
    save_upload as save_cover_upload,
    find_existing as find_cover_upload,
    delete_existing as delete_cover_upload,
    media_type_for as cover_media_type,
    ALLOWED_EXTENSIONS as COVER_ALLOWED_EXTENSIONS,
)
from voice_memos import (
    save_memo as save_voice_memo,
    find_memo_file,
    delete_memo_file,
    media_type_for as memo_media_type,
    ALLOWED_EXTENSIONS as MEMO_ALLOWED_EXTENSIONS,
)
from transcription import transcribe_audio
from image_to_pdf import image_to_pdf

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

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
SECRET_KEY = os.environ.get('JWT_SECRET', 'divine-leadership-press-secret-key-2025')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# --- MODELS ---

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    password_hash: str
    elevenlabs_api_key: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserRegister(BaseModel):
    email: EmailStr
    name: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    has_elevenlabs_key: bool = False
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
    has_audio_upload = bool(find_audio_upload(user_id, doc.get("id", "")))
    return PipelineStatus(
        manuscript=len(_strip_html_text(doc.get("content") or "")) >= 50,
        metadata=bool((metadata.get("author") or "").strip())
                  and bool((metadata.get("description") or "").strip()),
        cover=bool(doc.get("cover_image_ext")) or bool(find_cover_upload(user_id, doc.get("id", ""))),
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
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    return User(**user_doc)

# --- AUTH ROUTES ---

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    existing = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=hash_password(user_data.password)
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
        created_at=user.created_at
    )
    
    return TokenResponse(token=token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        has_elevenlabs_key=bool(current_user.elevenlabs_api_key),
        created_at=current_user.created_at
    )


class ElevenLabsKeyRequest(BaseModel):
    api_key: str


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
        {"$set": {"elevenlabs_api_key": key}},
    )
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        has_elevenlabs_key=True,
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
    style_guide: Optional[str] = "chicago"


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

    style_guide = (payload.style_guide or "chicago").lower()
    if style_guide not in STYLE_GUIDES:
        style_guide = "chicago"

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
        path = save_audio_upload(current_user.id, document_id, file.filename or "audio.mp3", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "document_id": document_id,
        "filename": path.name,
        "size_bytes": path.stat().st_size,
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

    found = find_audio_upload(current_user.id, document_id)
    if not found:
        raise HTTPException(status_code=404, detail="No audiobook uploaded for this document.")
    path, ext = found
    title = doc.get("title") or "Untitled"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "audiobook"
    return Response(
        content=path.read_bytes(),
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
    deleted = delete_audio_upload(current_user.id, document_id)
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
    found = find_audio_upload(current_user.id, document_id)
    if not found:
        return {"uploaded": False}
    path, ext = found
    return {
        "uploaded": True,
        "filename": path.name,
        "extension": ext,
        "size_bytes": path.stat().st_size,
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
        path, ext = save_cover_upload(current_user.id, document_id, file.filename or "cover.jpg", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.documents.update_one(
        {"id": document_id},
        {"$set": {"cover_image_ext": ext, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {
        "document_id": document_id,
        "filename": path.name,
        "extension": ext,
        "size_bytes": path.stat().st_size,
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
    found = find_cover_upload(current_user.id, document_id)
    if not found:
        raise HTTPException(status_code=404, detail="No cover uploaded for this document.")
    path, ext = found
    return Response(
        content=path.read_bytes(),
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
    deleted = delete_cover_upload(current_user.id, document_id)
    if deleted:
        await db.documents.update_one(
            {"id": document_id},
            {"$set": {"cover_image_ext": None, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    return {"deleted": deleted}


# --- COVER PDF (for KDP paperback submission) ---

@api_router.post("/documents/{document_id}/cover/pdf")
async def cover_to_pdf(
    document_id: str,
    trim: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    doc = await db.documents.find_one(
        {"id": document_id, "user_id": current_user.id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    found = find_cover_upload(current_user.id, document_id)
    if not found:
        raise HTTPException(status_code=404, detail="No cover image uploaded. Upload a cover first.")
    path, _ext = found

    trim_key = (trim or doc.get("format") or "6x9").strip()
    if trim_key not in KDP_TRIM_SIZES:
        trim_key = "6x9"

    title = doc.get("title") or "Untitled"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "cover"

    try:
        pdf_bytes = image_to_pdf(
            image_bytes=path.read_bytes(),
            trim_key=trim_key,
            title=f"{title} — Cover",
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
        path, ext = save_voice_memo(current_user.id, document_id, memo_id, file.filename or "memo.webm", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    memo = VoiceMemo(
        id=memo_id,
        title=(title or None),
        paragraph_index=paragraph_index,
        ext=ext,
        size_bytes=path.stat().st_size,
    )
    memo_doc = memo.model_dump()
    memo_doc["created_at"] = memo_doc["created_at"].isoformat()

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
    found = find_memo_file(current_user.id, document_id, memo_id)
    if not found:
        raise HTTPException(status_code=404, detail="Memo audio not found")
    path, ext = found
    return Response(
        content=path.read_bytes(),
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

    found = find_memo_file(current_user.id, document_id, memo_id)
    if not found:
        raise HTTPException(status_code=404, detail="Memo audio not found")
    path, ext = found

    try:
        text = await transcribe_audio(
            data=path.read_bytes(),
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
    delete_memo_file(current_user.id, document_id, memo_id)
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
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
