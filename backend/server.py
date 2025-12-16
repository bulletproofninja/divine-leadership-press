from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Depends, Header
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
from docx import Document
import io
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

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
    created_at: datetime

class TokenResponse(BaseModel):
    token: str
    user: UserResponse

class DocumentMetadata(BaseModel):
    isbn: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    language: Optional[str] = "English"
    page_count: Optional[int] = None
    genre: Optional[str] = None
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

class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str = ""
    user_id: str
    format: str = "6x9"
    original_filename: Optional[str] = None
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    versions: List[Version] = Field(default_factory=list)
    comments: List[Comment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    created_at: datetime
    updated_at: datetime
    version_count: int
    comment_count: int

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
        created_at=user.created_at
    )
    
    return TokenResponse(token=token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        created_at=current_user.created_at
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
    
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        user_id=document.user_id,
        format=document.format,
        original_filename=document.original_filename,
        metadata=document.metadata,
        created_at=document.created_at,
        updated_at=document.updated_at,
        version_count=len(document.versions),
        comment_count=len(document.comments)
    )

@api_router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(current_user: User = Depends(get_current_user)):
    docs = await db.documents.find({"user_id": current_user.id}, {"_id": 0}).to_list(1000)
    
    results = []
    for doc in docs:
        if isinstance(doc['created_at'], str):
            doc['created_at'] = datetime.fromisoformat(doc['created_at'])
        if isinstance(doc['updated_at'], str):
            doc['updated_at'] = datetime.fromisoformat(doc['updated_at'])
        
        results.append(DocumentResponse(
            id=doc['id'],
            title=doc['title'],
            content=doc['content'],
            user_id=doc['user_id'],
            format=doc['format'],
            original_filename=doc.get('original_filename'),
            metadata=DocumentMetadata(**doc.get('metadata', {})),
            created_at=doc['created_at'],
            updated_at=doc['updated_at'],
            version_count=len(doc.get('versions', [])),
            comment_count=len(doc.get('comments', []))
        ))
    
    return results

@api_router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if isinstance(doc['created_at'], str):
        doc['created_at'] = datetime.fromisoformat(doc['created_at'])
    if isinstance(doc['updated_at'], str):
        doc['updated_at'] = datetime.fromisoformat(doc['updated_at'])
    
    return DocumentResponse(
        id=doc['id'],
        title=doc['title'],
        content=doc['content'],
        user_id=doc['user_id'],
        format=doc['format'],
        original_filename=doc.get('original_filename'),
        metadata=DocumentMetadata(**doc.get('metadata', {})),
        created_at=doc['created_at'],
        updated_at=doc['updated_at'],
        version_count=len(doc.get('versions', [])),
        comment_count=len(doc.get('comments', []))
    )

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
    if isinstance(updated_doc['created_at'], str):
        updated_doc['created_at'] = datetime.fromisoformat(updated_doc['created_at'])
    if isinstance(updated_doc['updated_at'], str):
        updated_doc['updated_at'] = datetime.fromisoformat(updated_doc['updated_at'])
    
    return DocumentResponse(
        id=updated_doc['id'],
        title=updated_doc['title'],
        content=updated_doc['content'],
        user_id=updated_doc['user_id'],
        format=updated_doc['format'],
        original_filename=updated_doc.get('original_filename'),
        metadata=DocumentMetadata(**updated_doc.get('metadata', {})),
        created_at=updated_doc['created_at'],
        updated_at=updated_doc['updated_at'],
        version_count=len(updated_doc.get('versions', [])),
        comment_count=len(updated_doc.get('comments', []))
    )

@api_router.delete("/documents/{document_id}")
async def delete_document(document_id: str, current_user: User = Depends(get_current_user)):
    result = await db.documents.delete_one({"id": document_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted"}

# --- UPLOAD ROUTE ---

@api_router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    content = ""
    filename = file.filename or "untitled"
    
    if filename.endswith('.docx'):
        file_content = await file.read()
        doc = Document(io.BytesIO(file_content))
        content = "\n\n".join([paragraph.text for paragraph in doc.paragraphs])
    elif filename.endswith('.txt'):
        file_content = await file.read()
        content = file_content.decode('utf-8')
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload .docx or .txt files")
    
    # Create document
    title = filename.rsplit('.', 1)[0]
    document = DocumentModel(
        title=title,
        content=content,
        user_id=current_user.id,
        original_filename=filename
    )
    
    initial_version = Version(
        content=content,
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
    
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        user_id=document.user_id,
        format=document.format,
        original_filename=document.original_filename,
        metadata=document.metadata,
        created_at=document.created_at,
        updated_at=document.updated_at,
        version_count=len(document.versions),
        comment_count=len(document.comments)
    )

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

# --- EXPORT ROUTES (Mocked integrations for KDP, LULU) ---

@api_router.post("/documents/{document_id}/export")
async def export_document(document_id: str, format: str, current_user: User = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": document_id, "user_id": current_user.id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # This is a simplified export - in production would generate actual files
    return {
        "message": f"Document exported to {format}",
        "document_id": document_id,
        "format": format,
        "title": doc['title']
    }

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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
