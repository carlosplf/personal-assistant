from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web_app.auth import create_access_token
from web_app.dependencies import get_assistant_service, get_credential_store, get_current_user, get_current_user_flexible, get_finance_store, get_google_oauth, get_health_store, get_user_store
from web_app.user_store import WebUserStore

load_dotenv()

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

app = FastAPI(title="Personal Assistant PWA", docs_url="/docs", redoc_url=None)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# ---- Request / Response models ----

class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    text: str
    image_urls: list[str] = []


class ConversationCreate(BaseModel):
    title: str = "Nova conversa"


class ConversationRename(BaseModel):
    title: str


class NoteCreate(BaseModel):
    title: str = "Nova anotação"
    content: str = ""
    folder_id: str | None = None


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    folder_id: str | None = "__unset__"


class FolderCreate(BaseModel):
    name: str


class FolderRename(BaseModel):
    name: str


class TaskCreate(BaseModel):
    name: str
    deadline: str | None = None
    project: str | None = None
    tags: list[str] = []
    always_on: bool = False
    observations: str | None = None


class TaskUpdate(BaseModel):
    name: str | None = None
    deadline: str | None = "__unset__"
    project: str | None = "__unset__"
    done: bool | None = None
    always_on: bool | None = None
    tags: list[str] | None = None
    observations: str | None = "__unset__"


# ---- Helpers ----

_MAX_CONVERSATIONS_PER_USER = 100
_MAX_MESSAGES_PER_CONVERSATION = 40  # 20 exchanges (user + assistant)

def _build_channel_id(username: str, conversation_id: str | None) -> str:
    if conversation_id:
        return f"web:{username}:{conversation_id}"
    return f"web:{username}"


def _build_session_id(username: str, conversation_id: str | None) -> str:
    from assistant_connector.service import AssistantService as AService
    user_id = f"web:{username}"
    channel_id = _build_channel_id(username, conversation_id)
    return AService.build_session_id(user_id=user_id, channel_id=channel_id, guild_id=None)


def _check_message_limit(service, username: str, conversation_id: str | None) -> None:
    """Raise 400 if the conversation has reached the message limit."""
    if not conversation_id:
        return
    try:
        session_id = _build_session_id(username, conversation_id)
        count = service._runtime._memory_store.count_messages(session_id)
        if isinstance(count, int) and count >= _MAX_MESSAGES_PER_CONVERSATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Conversa atingiu o limite de {_MAX_MESSAGES_PER_CONVERSATION // 2} trocas de mensagens. Crie uma nova conversa.",
            )
    except HTTPException:
        raise
    except Exception:
        pass


def _extract_image_urls(image_paths: list[str]) -> list[str]:
    urls: list[str] = []
    for img_path in image_paths:
        if os.path.isfile(img_path):
            urls.append(f"/api/chat/images/{os.path.basename(img_path)}")
    return urls


# ---- Page routes ----

@app.get("/", response_class=HTMLResponse)
async def index_page():
    return _read_template("login.html")


@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    return _read_template("chat.html")


@app.get("/manifest.json")
async def manifest():
    return FileResponse(os.path.join(_STATIC_DIR, "manifest.json"), media_type="application/manifest+json")


# ---- Auth endpoints ----

@app.post("/api/auth/login")
async def login(req: LoginRequest, store: WebUserStore = Depends(get_user_store)):
    user = store.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user["id"], username=user["username"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
        },
    }


@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
    }


# ---- Conversation endpoints ----

@app.get("/api/conversations")
async def list_conversations(
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    conversations = store.list_conversations(user["id"])
    return {"conversations": conversations}


@app.post("/api/conversations", status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    store.prune_oldest_conversations(user["id"], _MAX_CONVERSATIONS_PER_USER - 1)
    conv = store.create_conversation(user["id"], body.title)
    return conv


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    body: ConversationRename,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    if not body.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be empty")
    updated = store.rename_conversation(conversation_id, user["id"], body.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok"}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
    service=Depends(get_assistant_service),
):
    conv = store.get_conversation(conversation_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Clear the session messages from the memory store
    channel_id = _build_channel_id(user["username"], conversation_id)
    user_id = f"web:{user['username']}"
    await asyncio.to_thread(
        service.reset_chat,
        user_id=user_id,
        channel_id=channel_id,
        guild_id=None,
    )

    store.delete_conversation(conversation_id, user["id"])
    return {"status": "ok"}


@app.get("/api/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
    service=Depends(get_assistant_service),
):
    conv = store.get_conversation(conversation_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    session_id = _build_session_id(user["username"], conversation_id)
    messages = service._runtime._memory_store.get_recent_messages(session_id, limit=200)
    return {
        "messages": messages,
        "message_count": len(messages),
        "message_limit": _MAX_MESSAGES_PER_CONVERSATION,
    }


# ---- Chat endpoints ----

@app.post("/api/chat")
async def chat_send(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
    service=Depends(get_assistant_service),
):
    if not req.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

    _check_message_limit(service, user["username"], req.conversation_id)

    user_id = f"web:{user['username']}"
    channel_id = _build_channel_id(user["username"], req.conversation_id)

    response = await asyncio.to_thread(
        service.chat,
        user_id=user_id,
        channel_id=channel_id,
        guild_id=None,
        message=req.message.strip(),
    )

    if req.conversation_id:
        store.touch_conversation(req.conversation_id, user["id"])

    return {"text": response.text, "image_urls": _extract_image_urls(response.image_paths)}


@app.post("/api/chat/reset")
async def chat_reset(
    user: dict = Depends(get_current_user),
    service=Depends(get_assistant_service),
    conversation_id: str | None = Query(None),
):
    user_id = f"web:{user['username']}"
    channel_id = _build_channel_id(user["username"], conversation_id)

    await asyncio.to_thread(
        service.reset_chat,
        user_id=user_id,
        channel_id=channel_id,
        guild_id=None,
    )
    return {"status": "ok"}


@app.post("/api/chat/upload")
async def chat_upload(
    file: UploadFile = File(...),
    caption: str = Form(""),
    conversation_id: str = Form(""),
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
    service=Depends(get_assistant_service),
):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    user_id = f"web:{user['username']}"
    conv_id = conversation_id if conversation_id else None

    _check_message_limit(service, user["username"], conv_id)

    channel_id = _build_channel_id(user["username"], conv_id)

    response = await asyncio.to_thread(
        service.handle_file_upload,
        user_id=user_id,
        channel_id=channel_id,
        guild_id=None,
        filename=file.filename or "file",
        file_bytes=file_bytes,
        mime_type=file.content_type or "",
        caption=caption,
    )

    if conv_id:
        store.touch_conversation(conv_id, user["id"])

    return {"text": response.text, "image_urls": _extract_image_urls(response.image_paths)}


@app.post("/api/chat/audio")
async def chat_audio(
    audio: UploadFile = File(...),
    conversation_id: str = Form(""),
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
    service=Depends(get_assistant_service),
):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio")

    from openai_connector import llm_api
    from utils import create_logger

    logger = create_logger.create_logger()
    filename = audio.filename or "recording.webm"
    mime_type = audio.content_type or "audio/webm"

    transcribed_text = await asyncio.to_thread(
        llm_api.transcribe_audio_input,
        audio_bytes,
        filename,
        mime_type,
        logger,
    )

    if not transcribed_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not transcribe audio")

    user_id = f"web:{user['username']}"
    conv_id = conversation_id if conversation_id else None

    _check_message_limit(service, user["username"], conv_id)

    channel_id = _build_channel_id(user["username"], conv_id)

    response = await asyncio.to_thread(
        service.chat,
        user_id=user_id,
        channel_id=channel_id,
        guild_id=None,
        message=transcribed_text,
    )

    if conv_id:
        store.touch_conversation(conv_id, user["id"])

    return {
        "text": response.text,
        "transcribed_text": transcribed_text,
        "image_urls": _extract_image_urls(response.image_paths),
    }


@app.get("/api/chat/images/{filename}")
async def get_chat_image(filename: str, user: dict = Depends(get_current_user)):
    charts_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "charts_output")
    )
    files_dir = os.getenv(
        "ASSISTANT_FILES_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "files")),
    )
    safe_filename = os.path.basename(filename)

    # Charts are UUID-named and generated per-session; any authenticated user may access.
    charts_candidate = os.path.join(charts_dir, safe_filename)
    if os.path.isfile(charts_candidate):
        return FileResponse(charts_candidate)

    # Uploaded files are scoped to the current user's directory.
    user_session_id = f"web:{user['username']}"
    user_files_dir = os.path.realpath(os.path.join(files_dir, user_session_id))
    candidate = os.path.join(user_files_dir, safe_filename)
    real = os.path.realpath(candidate)
    if real.startswith(user_files_dir + os.sep) and os.path.isfile(real):
        return FileResponse(real)

    raise HTTPException(status_code=404, detail="Image not found")


# ---- Note image endpoints ----

_NOTE_IMAGES_DIR = os.path.abspath(
    os.getenv(
        "NOTES_IMAGES_DIR",
        os.path.join(os.path.dirname(__file__), "..", "note_images"),
    )
)
_NOTE_IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_NOTE_IMAGE_ACCEPTED_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_NOTE_IMAGE_ACCEPTED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _get_user_note_images_dir(username: str) -> str:
    safe = "".join(c for c in username if c.isalnum() or c in ("-", "_"))
    return os.path.realpath(os.path.join(_NOTE_IMAGES_DIR, safe))


@app.post("/api/notes/images", status_code=201)
async def upload_note_image(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    import uuid as _uuid

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _NOTE_IMAGE_ACCEPTED_MIMES:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo de arquivo não suportado. Use: {', '.join(sorted(_NOTE_IMAGE_ACCEPTED_MIMES))}",
        )

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _NOTE_IMAGE_ACCEPTED_EXTS:
        ext = "." + content_type.split("/")[-1].replace("jpeg", "jpg")

    data = await file.read()
    if len(data) > _NOTE_IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Imagem excede o tamanho máximo ({_NOTE_IMAGE_MAX_BYTES // (1024 * 1024)} MB).",
        )

    user_dir = _get_user_note_images_dir(user["username"])
    os.makedirs(user_dir, exist_ok=True)

    filename = f"{_uuid.uuid4().hex}{ext}"
    dest = os.path.join(user_dir, filename)
    # Path traversal guard
    if not os.path.realpath(dest).startswith(user_dir + os.sep) and os.path.realpath(dest) != user_dir:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    with open(dest, "wb") as f:
        f.write(data)

    return {"url": f"/api/notes/images/{filename}"}


@app.get("/api/notes/images/{filename}")
async def serve_note_image(
    filename: str,
    user: dict = Depends(get_current_user_flexible),
):
    safe_filename = os.path.basename(filename)
    user_dir = _get_user_note_images_dir(user["username"])
    candidate = os.path.join(user_dir, safe_filename)
    real = os.path.realpath(candidate)

    if not real.startswith(user_dir + os.sep) and real != user_dir:
        raise HTTPException(status_code=404, detail="Image not found")
    if not os.path.isfile(real):
        raise HTTPException(status_code=404, detail="Image not found")

    ext = os.path.splitext(safe_filename)[1].lower()
    media_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                   ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(real, media_type=media_type, headers={"Cache-Control": "private, max-age=86400"})


# ---- Note endpoints ----

@app.get("/api/notes/tags")
async def list_note_tags(
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    tags = store.list_user_tags(user["id"])
    return {"tags": tags}


@app.get("/api/notes/folders")
async def list_folders(
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    folders = store.list_folders(user["id"])
    return {"folders": folders}


@app.post("/api/notes/folders", status_code=201)
async def create_folder(
    body: FolderCreate,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    try:
        folder = store.create_folder(user["id"], body.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return folder


@app.patch("/api/notes/folders/{folder_id}")
async def rename_folder(
    folder_id: str,
    body: FolderRename,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    try:
        updated = store.rename_folder(folder_id, user["id"], body.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Folder not found")
    return {"status": "ok"}


@app.delete("/api/notes/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    deleted = store.delete_folder(folder_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Folder not found")
    return {"status": "ok"}


@app.get("/api/notes")
async def list_notes(
    tag: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    notes = store.list_notes(user["id"], tag=tag)
    return {"notes": notes}


@app.post("/api/notes", status_code=201)
async def create_note(
    body: NoteCreate,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    try:
        note = store.create_note(user["id"], body.title, body.content, folder_id=body.folder_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return note


@app.get("/api/notes/{note_id}")
async def get_note(
    note_id: str,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    note = store.get_note(note_id, user["id"])
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@app.patch("/api/notes/{note_id}")
async def update_note(
    note_id: str,
    body: NoteUpdate,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    if body.title is not None and not body.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be empty")
    folder_id_arg = ... if body.folder_id == "__unset__" else body.folder_id
    try:
        updated = store.update_note(note_id, user["id"], title=body.title, content=body.content, tags=body.tags, folder_id=folder_id_arg)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "ok"}


@app.post("/api/notes/{note_id}/generate-metadata")
async def generate_note_metadata_endpoint(
    note_id: str,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    note = store.get_note(note_id, user["id"])
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    from openai_connector.llm_api import generate_note_metadata, OpenAICallError
    from utils import create_logger

    logger = create_logger.create_logger()
    try:
        metadata = await asyncio.get_event_loop().run_in_executor(
            None, generate_note_metadata, note["content"], logger
        )
    except OpenAICallError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    store.update_note(note_id, user["id"], title=metadata["title"], tags=metadata["tags"])
    return {"title": metadata["title"], "tags": metadata["tags"]}


@app.delete("/api/notes/{note_id}")
async def delete_note(
    note_id: str,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    deleted = store.delete_note(note_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "ok"}


# ---- Google OAuth endpoints ----

@app.get("/api/google/status")
async def google_status(user: dict = Depends(get_current_user)):
    oauth = get_google_oauth()
    if oauth is None:
        return {"configured": False, "connected": False}
    user_id = f"web:{user['username']}"
    connected = oauth.has_valid_token(user_id)
    return {"configured": True, "connected": connected}


@app.get("/api/google/auth-url")
async def google_auth_url(user: dict = Depends(get_current_user)):
    oauth = get_google_oauth()
    if oauth is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured. Set GOOGLE_OAUTH_CALLBACK_URL in .env.",
        )
    user_id = f"web:{user['username']}"
    try:
        auth_url = oauth.start_flow(user_id)
        return {"auth_url": auth_url}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@app.get("/auth/google/callback", response_class=HTMLResponse)
async def google_oauth_callback(
    code: str = "",
    state: str = "",
    error: str = "",
):
    from web_app.google_oauth import _ERROR_HTML, _SUCCESS_HTML

    if error:
        return HTMLResponse(_ERROR_HTML.format(message=f"Google recusou: {error}"), status_code=400)
    if not code or not state:
        return HTMLResponse(_ERROR_HTML.format(message="Parâmetros ausentes."), status_code=400)

    oauth = get_google_oauth()
    if oauth is None:
        return HTMLResponse(_ERROR_HTML.format(message="Google OAuth não configurado no servidor."), status_code=500)

    ok, message, _user_id = oauth.handle_callback(code, state)
    if ok:
        return HTMLResponse(_SUCCESS_HTML, status_code=200)
    return HTMLResponse(_ERROR_HTML.format(message=message), status_code=400)


@app.delete("/api/google/disconnect")
async def google_disconnect(user: dict = Depends(get_current_user)):
    oauth = get_google_oauth()
    if oauth is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth not configured.")
    user_id = f"web:{user['username']}"
    oauth.revoke_token(user_id)
    return {"status": "ok"}


# ---- Memories endpoints ----


@app.get("/api/memories")
async def list_memories(user: dict = Depends(get_current_user)):
    """List and return contents of user memory files."""
    import re

    user_id = f"web:{user['username']}"
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", user_id)

    base_dir = os.getenv(
        "ASSISTANT_MEMORIES_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "memories")),
    )
    user_dir = os.path.join(base_dir, safe_id)

    if not os.path.isdir(user_dir):
        return {"files": [], "count": 0}

    reserved = {"readme.md"}
    files = sorted(
        f
        for f in os.listdir(user_dir)
        if f.lower().endswith(".md") and f.lower() not in reserved
    )

    result = []
    for fname in files:
        fpath = os.path.join(user_dir, fname)
        real = os.path.realpath(fpath)
        if not real.startswith(os.path.realpath(user_dir)):
            continue  # path traversal guard
        try:
            with open(real, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            content = "(erro ao ler arquivo)"

        # Derive a display name from filename
        display_name = fname.replace("-", " ").replace("_", " ")
        if display_name.lower().endswith(".md"):
            display_name = display_name[:-3]
        display_name = display_name.title()

        result.append({
            "filename": fname,
            "display_name": display_name,
            "content": content,
        })

    return {"files": result, "count": len(result)}


_MAX_MEMORY_CONTENT = 100 * 1024  # 100 KB


@app.put("/api/memories/{filename}")
async def update_memory(
    filename: str,
    body: dict,
    user: dict = Depends(get_current_user),
):
    """Update the content of a user memory file."""
    import re

    # Validate filename: must be a .md file with no path separators
    if (
        not filename.lower().endswith(".md")
        or "/" in filename
        or "\\" in filename
        or ".." in filename
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    reserved = {"readme.md"}
    if filename.lower() in reserved:
        raise HTTPException(status_code=403, detail="Cannot edit reserved file")

    content = body.get("content", "")
    if not isinstance(content, str):
        raise HTTPException(status_code=400, detail="content must be a string")
    if len(content) > _MAX_MEMORY_CONTENT:
        raise HTTPException(status_code=413, detail="Content too large")

    user_id = f"web:{user['username']}"
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", user_id)

    base_dir = os.getenv(
        "ASSISTANT_MEMORIES_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "memories")),
    )
    user_dir = os.path.join(base_dir, safe_id)

    if not os.path.isdir(user_dir):
        try:
            os.makedirs(user_dir, exist_ok=True, mode=0o700)
        except OSError:
            raise HTTPException(status_code=500, detail="Could not create memory directory")

    fpath = os.path.join(user_dir, filename)
    real = os.path.realpath(fpath)
    if not real.startswith(os.path.realpath(user_dir)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.isfile(real):
        raise HTTPException(status_code=404, detail="Memory file not found")

    try:
        with open(real, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to write file")

    return {"ok": True, "filename": filename}





_VALID_MEAL_TYPES = {"ALMOÇO", "JANTAR", "LANCHE", "CAFÉ DA MANHÃ", "SUPLEMENTO"}

_MAX_FOOD_LEN = 200
_MAX_ACTIVITY_LEN = 200
_MAX_QUANTITY_LEN = 100
_MAX_OBSERVATIONS_LEN = 500
_MAX_CALORIES = 50000
_MAX_FUTURE_DAYS = 30


def _parse_date_param(date_str: str | None, default_date=None) -> str:
    """Validate and return a YYYY-MM-DD date string."""
    import datetime as _dt

    from utils.timezone_utils import today_in_configured_timezone

    if not date_str:
        return (default_date or today_in_configured_timezone()).isoformat()
    try:
        parsed = _dt.date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be a valid YYYY-MM-DD")
    today = today_in_configured_timezone()
    if (parsed - today).days > _MAX_FUTURE_DAYS:
        raise HTTPException(status_code=400, detail=f"date cannot be more than {_MAX_FUTURE_DAYS} days in the future")
    return parsed.isoformat()


@app.get("/api/health/dashboard")
async def health_dashboard(
    date: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    user: dict = Depends(get_current_user),
):
    """Daily health dashboard: meals + exercises + totals for a given date."""
    from assistant_connector.health_store import HealthStore

    target_date = _parse_date_param(date)
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()

    async def fetch_meals():
        try:
            return await asyncio.to_thread(
                store.list_meals_by_date_range,
                user_id=user_id,
                start_date=target_date,
                end_date=target_date,
            )
        except Exception:
            return []

    async def fetch_exercises():
        try:
            return await asyncio.to_thread(
                store.list_exercises_by_date_range,
                user_id=user_id,
                start_date=target_date,
                end_date=target_date,
            )
        except Exception:
            return []

    meals, exercises = await asyncio.gather(fetch_meals(), fetch_exercises())

    calories_consumed = sum(float(m.get("calories") or 0) for m in meals)
    calories_burned = sum(float(e.get("calories") or 0) for e in exercises)

    return {
        "date": target_date,
        "meals": meals,
        "exercises": exercises,
        "totals": {
            "calories_consumed": round(calories_consumed, 1),
            "calories_burned": round(calories_burned, 1),
            "balance": round(calories_consumed - calories_burned, 1),
        },
    }


@app.get("/api/health/weekly")
async def health_weekly(
    end_date: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    user: dict = Depends(get_current_user),
):
    """Weekly summary: per-day calorie totals for the last 7 days."""
    import datetime as _dt

    from assistant_connector.health_store import HealthStore

    target_end = _parse_date_param(end_date)
    end = _dt.date.fromisoformat(target_end)
    start = end - _dt.timedelta(days=6)
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()

    async def fetch_meals():
        try:
            return await asyncio.to_thread(
                store.list_meals_by_date_range,
                user_id=user_id,
                start_date=start.isoformat(),
                end_date=target_end,
            )
        except Exception:
            return []

    async def fetch_exercises():
        try:
            return await asyncio.to_thread(
                store.list_exercises_by_date_range,
                user_id=user_id,
                start_date=start.isoformat(),
                end_date=target_end,
            )
        except Exception:
            return []

    meals, exercises = await asyncio.gather(fetch_meals(), fetch_exercises())

    days_map: dict[str, dict] = {}
    for i in range(7):
        d = (start + _dt.timedelta(days=i)).isoformat()
        days_map[d] = {"date": d, "calories_consumed": 0.0, "calories_burned": 0.0, "meal_count": 0, "exercise_count": 0}

    for m in meals:
        d = str(m.get("date", ""))[:10]
        if d in days_map:
            days_map[d]["calories_consumed"] += float(m.get("calories") or 0)
            days_map[d]["meal_count"] += 1

    for e in exercises:
        d = str(e.get("date", ""))[:10]
        if d in days_map:
            days_map[d]["calories_burned"] += float(e.get("calories") or 0)
            days_map[d]["exercise_count"] += 1

    days = []
    for d in sorted(days_map):
        entry = days_map[d]
        entry["calories_consumed"] = round(entry["calories_consumed"], 1)
        entry["calories_burned"] = round(entry["calories_burned"], 1)
        days.append(entry)

    return {"days": days}


@app.post("/api/health/analysis")
async def health_nutritional_analysis(
    user: dict = Depends(get_current_user),
):
    """Generate a detailed 7-day nutritional analysis via LLM."""
    import datetime as _dt

    from assistant_connector.health_store import HealthStore
    from openai_connector.llm_api import OpenAICallError, generate_nutritional_analysis
    from utils import create_logger

    logger = create_logger.create_logger()

    end = _dt.date.today()
    start = end - _dt.timedelta(days=6)
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()

    async def fetch_meals():
        try:
            return await asyncio.to_thread(
                store.list_meals_by_date_range,
                user_id=user_id,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
        except Exception as exc:
            logger.error("Failed to fetch meals for analysis: %s", exc)
            return []

    async def fetch_exercises():
        try:
            return await asyncio.to_thread(
                store.list_exercises_by_date_range,
                user_id=user_id,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
        except Exception as exc:
            logger.error("Failed to fetch exercises for analysis: %s", exc)
            return []

    async def fetch_goals():
        try:
            goals = await asyncio.to_thread(store.get_health_goals, user_id)
            return goals.get("calorie_goal")
        except Exception as exc:
            logger.error("Failed to fetch health goals for analysis: %s", exc)
            return None

    meals, exercises, calorie_goal = await asyncio.gather(fetch_meals(), fetch_exercises(), fetch_goals())

    logger.info("Health analysis: %d meals, %d exercises for %s to %s", len(meals), len(exercises), start, end)

    try:
        analysis = await asyncio.to_thread(
            generate_nutritional_analysis, meals, exercises, logger, calorie_goal
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar análise: {exc}")

    return {"analysis": analysis}


class MealItemRequest(BaseModel):
    food: str
    quantity: str
    estimated_calories: float | None = None


class CreateMealRequest(BaseModel):
    meal_type: str
    date: str | None = None
    items: list[MealItemRequest]


class UpdateMealItemRequest(BaseModel):
    food: str | None = None
    quantity: str | None = None
    calories: float | None = None


class UpdateMealGroupRequest(BaseModel):
    meal_type: str | None = None
    date: str | None = None


@app.post("/api/health/meals")
async def create_health_meal(
    body: CreateMealRequest,
    user: dict = Depends(get_current_user),
):
    """Register a meal with multiple food items in the local SQLite health database.

    Items without explicit calories are saved with calories=0 and calories_pending=True.
    A background task estimates their calories via a single LLM batch call.
    """
    from assistant_connector.health_store import HealthStore, parse_quantity_details, normalize_quantity
    from openai_connector.llm_api import estimate_calories_batch
    from utils.timezone_utils import today_iso_in_configured_timezone

    meal_type = body.meal_type.strip().upper()
    if meal_type not in _VALID_MEAL_TYPES:
        raise HTTPException(status_code=400, detail=f"meal_type must be one of: {', '.join(sorted(_VALID_MEAL_TYPES))}")
    if not body.items:
        raise HTTPException(status_code=400, detail="items must not be empty")

    # Validate items
    for item in body.items:
        food = item.food.strip()
        if not food or len(food) > _MAX_FOOD_LEN:
            raise HTTPException(status_code=400, detail=f"food must be 1-{_MAX_FOOD_LEN} characters")
        quantity = item.quantity.strip()
        if not quantity or len(quantity) > _MAX_QUANTITY_LEN:
            raise HTTPException(status_code=400, detail=f"quantity must be 1-{_MAX_QUANTITY_LEN} characters")

    meal_group_id = __import__("uuid").uuid4().hex
    import datetime as _dt
    meal_date = today_iso_in_configured_timezone()
    if body.date:
        try:
            _dt.date.fromisoformat(body.date)
            meal_date = body.date
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be a valid ISO date (YYYY-MM-DD)")

    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()

    # Items with no explicit calories will be marked pending and estimated in background
    items_needing_estimate = []
    results = []
    for item in body.items:
        food = item.food.strip()
        quantity = item.quantity.strip()
        has_explicit_calories = item.estimated_calories is not None
        calories = float(item.estimated_calories) if has_explicit_calories else 0.0
        pending = not has_explicit_calories

        normalized_amount = None
        normalized_unit = None
        try:
            qty_details = parse_quantity_details(quantity)
            qty_normalized = normalize_quantity(qty_details)
            normalized_amount = qty_normalized["amount"]
            normalized_unit = qty_normalized["unit"]
        except Exception:
            pass

        result = await asyncio.to_thread(
            store.create_meal,
            user_id=user_id,
            food=food,
            meal_type=meal_type,
            quantity=quantity,
            calories=calories,
            date=meal_date,
            normalized_amount=normalized_amount,
            normalized_unit=normalized_unit,
            meal_group_id=meal_group_id,
            calories_pending=pending,
        )
        results.append(result)
        if pending:
            items_needing_estimate.append({"meal_id": result["id"], "food": food, "quantity": quantity})

    any_pending = len(items_needing_estimate) > 0

    # Spawn background task to estimate calories for items without explicit values
    if any_pending:
        async def _estimate_and_update():
            batch_items = [{"food": x["food"], "quantity": x["quantity"]} for x in items_needing_estimate]
            try:
                calories_estimated = await asyncio.to_thread(estimate_calories_batch, batch_items)
                meal_ids = [x["meal_id"] for x in items_needing_estimate]
                await asyncio.to_thread(
                    store.update_meal_calories_batch,
                    meal_group_id,
                    meal_ids,
                    calories_estimated,
                )
            except Exception:
                pass  # Best-effort: failures leave calories_pending=True but don't crash

        asyncio.create_task(_estimate_and_update())

    return {"status": "created", "meals": results, "meal_group_id": meal_group_id, "calories_pending": any_pending}


@app.get("/api/health/meals/foods")
async def list_meal_foods(
    user: dict = Depends(get_current_user),
):
    """Return distinct food names previously logged by the user, most frequent first."""
    from assistant_connector.health_store import HealthStore
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    foods = await asyncio.to_thread(store.get_distinct_foods, user_id=user_id)
    return {"foods": foods}


@app.delete("/api/health/meals/group/{meal_group_id}")
async def delete_health_meal_group(
    meal_group_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete all food items belonging to a meal group."""
    from assistant_connector.health_store import HealthStore
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    count = await asyncio.to_thread(store.delete_meal_group, user_id=user_id, meal_group_id=meal_group_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="Meal group not found")
    return {"status": "deleted", "count": count}


@app.patch("/api/health/meals/group/{meal_group_id}")
async def update_health_meal_group(
    meal_group_id: str,
    body: UpdateMealGroupRequest,
    user: dict = Depends(get_current_user),
):
    """Update meal_type and/or date for all food items in a meal group."""
    import datetime as _dt
    from assistant_connector.health_store import HealthStore
    kwargs: dict = {}
    if body.meal_type is not None:
        mt = body.meal_type.strip().upper()
        if mt not in _VALID_MEAL_TYPES:
            raise HTTPException(status_code=400, detail=f"meal_type must be one of: {', '.join(sorted(_VALID_MEAL_TYPES))}")
        kwargs["meal_type"] = mt
    if body.date is not None:
        try:
            _dt.date.fromisoformat(body.date)
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be a valid ISO date (YYYY-MM-DD)")
        kwargs["date"] = body.date
    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    try:
        count = await asyncio.to_thread(store.update_meal_group, user_id=user_id, meal_group_id=meal_group_id, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if count == 0:
        raise HTTPException(status_code=404, detail="Meal group not found")
    return {"status": "updated", "count": count}


@app.delete("/api/health/meals/{meal_id}")
async def delete_health_meal(
    meal_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a single food item from a meal."""
    from assistant_connector.health_store import HealthStore
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    deleted = await asyncio.to_thread(store.delete_meal, user_id=user_id, meal_id=meal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Meal item not found")
    return {"status": "deleted"}


@app.patch("/api/health/meals/{meal_id}")
async def update_health_meal(
    meal_id: str,
    body: UpdateMealItemRequest,
    user: dict = Depends(get_current_user),
):
    """Update a single food item."""
    from assistant_connector.health_store import HealthStore
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    kwargs = {}
    if body.food is not None:
        kwargs["food"] = body.food.strip()
    if body.quantity is not None:
        kwargs["quantity"] = body.quantity.strip()
    if body.calories is not None:
        kwargs["calories"] = body.calories
    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        result = await asyncio.to_thread(store.update_meal, user_id=user_id, meal_id=meal_id, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "updated", "meal": result}



class CreateExerciseRequest(BaseModel):
    activity: str
    calories: float
    date: str | None = None
    observations: str = ""
    done: bool = True
    duration_minutes: int | None = None
    effort_level: int | None = None


@app.post("/api/health/exercises")
async def create_health_exercise(
    body: CreateExerciseRequest,
    user: dict = Depends(get_current_user),
):
    """Register an exercise in the local SQLite health database."""
    import datetime as _dt
    from assistant_connector.health_store import HealthStore

    activity = body.activity.strip()
    if not activity or len(activity) > _MAX_ACTIVITY_LEN:
        raise HTTPException(status_code=400, detail=f"activity must be 1-{_MAX_ACTIVITY_LEN} characters")
    if body.calories <= 0 or body.calories > _MAX_CALORIES:
        raise HTTPException(status_code=400, detail=f"calories must be between 0 and {_MAX_CALORIES}")
    observations = body.observations.strip()
    if len(observations) > _MAX_OBSERVATIONS_LEN:
        raise HTTPException(status_code=400, detail=f"observations must be at most {_MAX_OBSERVATIONS_LEN} characters")
    if body.effort_level is not None and not (0 <= body.effort_level <= 10):
        raise HTTPException(status_code=400, detail="effort_level must be between 0 and 10")

    from utils.timezone_utils import today_iso_in_configured_timezone

    exercise_date = today_iso_in_configured_timezone()
    if body.date:
        try:
            _dt.date.fromisoformat(body.date)
            exercise_date = body.date
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be a valid ISO date (YYYY-MM-DD)")

    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    result = await asyncio.to_thread(
        store.create_exercise,
        user_id=user_id,
        activity=activity,
        calories=body.calories,
        date=exercise_date,
        observations=observations,
        done=body.done,
        duration_minutes=body.duration_minutes,
        effort_level=body.effort_level,
    )
    return {"status": "created", "exercise": result}


class UpdateExerciseRequest(BaseModel):
    activity: str | None = None
    calories: float | None = None
    observations: str | None = None
    done: bool | None = None
    duration_minutes: int | None = None
    effort_level: int | None = None


@app.patch("/api/health/exercises/{exercise_id}")
async def update_health_exercise(
    exercise_id: str,
    body: UpdateExerciseRequest,
    user: dict = Depends(get_current_user),
):
    """Update an exercise in the local SQLite health database."""
    from assistant_connector.health_store import HealthStore

    if not exercise_id.strip():
        raise HTTPException(status_code=400, detail="exercise_id is required")

    kwargs: dict = {}
    if body.activity is not None:
        a = body.activity.strip()
        if not a or len(a) > _MAX_ACTIVITY_LEN:
            raise HTTPException(status_code=400, detail=f"activity must be 1-{_MAX_ACTIVITY_LEN} characters")
        kwargs["activity"] = a
    if body.calories is not None:
        if body.calories <= 0 or body.calories > _MAX_CALORIES:
            raise HTTPException(status_code=400, detail=f"calories must be between 0 and {_MAX_CALORIES}")
        kwargs["calories"] = body.calories
    if body.observations is not None:
        if len(body.observations) > _MAX_OBSERVATIONS_LEN:
            raise HTTPException(status_code=400, detail=f"observations must be at most {_MAX_OBSERVATIONS_LEN} characters")
        kwargs["observations"] = body.observations
    if body.done is not None:
        kwargs["done"] = body.done
    if body.duration_minutes is not None:
        if body.duration_minutes < 1 or body.duration_minutes > 1440:
            raise HTTPException(status_code=400, detail="duration_minutes must be between 1 and 1440")
        kwargs["duration_minutes"] = body.duration_minutes
    if body.effort_level is not None:
        if not (0 <= body.effort_level <= 10):
            raise HTTPException(status_code=400, detail="effort_level must be between 0 and 10")
        kwargs["effort_level"] = body.effort_level

    if not kwargs:
        raise HTTPException(status_code=400, detail="At least one field must be provided to update")

    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    try:
        result = await asyncio.to_thread(
            store.update_exercise,
            user_id=user_id,
            exercise_id=exercise_id.strip(),
            **kwargs,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@app.delete("/api/health/exercises/{exercise_id}")
async def delete_health_exercise(
    exercise_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete an exercise entry."""
    from assistant_connector.health_store import HealthStore
    if not exercise_id.strip():
        raise HTTPException(status_code=400, detail="exercise_id is required")
    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    deleted = await asyncio.to_thread(store.delete_exercise, user_id=user_id, exercise_id=exercise_id.strip())
    if not deleted:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return {"status": "deleted"}


# ---- Finance endpoints ----

_MAX_EXPENSE_NAME_LEN = 200
_MAX_EXPENSE_DESC_LEN = 500
_MAX_BILL_NAME_LEN = 200
_MAX_AMOUNT = 99_999_999.99
_VALID_FINANCE_CATEGORIES = {"Alimentação", "Transporte", "Moradia", "Saúde", "Lazer", "Outros"}


class CreateExpenseRequest(BaseModel):
    name: str
    amount: float
    category: str = "Outros"
    description: str = ""
    date: str | None = None


@app.post("/api/finance/expenses")
async def create_finance_expense(
    body: CreateExpenseRequest,
    user: dict = Depends(get_current_user),
):
    """Register a financial expense."""
    name = body.name.strip()
    if not name or len(name) > _MAX_EXPENSE_NAME_LEN:
        raise HTTPException(status_code=400, detail=f"name must be 1-{_MAX_EXPENSE_NAME_LEN} characters")
    if body.amount <= 0 or body.amount > _MAX_AMOUNT:
        raise HTTPException(status_code=400, detail="amount must be between 0 and 99999999.99")
    category = body.category.strip() or "Outros"
    description = body.description.strip()
    if len(description) > _MAX_EXPENSE_DESC_LEN:
        raise HTTPException(status_code=400, detail=f"description must be at most {_MAX_EXPENSE_DESC_LEN} characters")

    import re
    expense_date = None
    if body.date:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", body.date):
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        expense_date = body.date
    else:
        from utils.timezone_utils import today_iso_in_configured_timezone
        expense_date = today_iso_in_configured_timezone()

    user_id = f"web:{user['username']}"
    store = get_finance_store()
    result = await asyncio.to_thread(
        store.create_expense,
        user_id=user_id,
        name=name,
        amount=body.amount,
        category=category,
        description=description,
        date=expense_date,
    )
    return {"status": "created", "expense": result}


@app.delete("/api/finance/expenses/{expense_id}")
async def delete_finance_expense(
    expense_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a financial expense."""
    user_id = f"web:{user['username']}"
    store = get_finance_store()
    deleted = await asyncio.to_thread(store.delete_expense, user_id, expense_id.strip())
    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"status": "deleted"}


class CreateBillRequest(BaseModel):
    bill_name: str
    budget: float
    category: str = "Outros"
    due_day: int | None = None
    reference_month: str | None = None


@app.post("/api/finance/bills")
async def create_finance_bill(
    body: CreateBillRequest,
    user: dict = Depends(get_current_user),
):
    """Register a fixed monthly bill."""
    bill_name = body.bill_name.strip()
    if not bill_name or len(bill_name) > _MAX_BILL_NAME_LEN:
        raise HTTPException(status_code=400, detail=f"bill_name must be 1-{_MAX_BILL_NAME_LEN} characters")
    if body.budget <= 0 or body.budget > _MAX_AMOUNT:
        raise HTTPException(status_code=400, detail="budget must be between 0 and 99999999.99")
    category = body.category.strip() or "Outros"

    due_day = None
    if body.due_day is not None:
        if not (1 <= body.due_day <= 31):
            raise HTTPException(status_code=400, detail="due_day must be between 1 and 31")
        due_day = body.due_day

    import re
    ref_month = body.reference_month
    if ref_month:
        if not re.match(r"^\d{4}-\d{2}$", ref_month):
            raise HTTPException(status_code=400, detail="reference_month must be YYYY-MM")
    else:
        from utils.timezone_utils import today_iso_in_configured_timezone
        ref_month = today_iso_in_configured_timezone()[:7]

    user_id = f"web:{user['username']}"
    store = get_finance_store()
    result = await asyncio.to_thread(
        store.create_bill,
        user_id=user_id,
        bill_name=bill_name,
        budget=body.budget,
        category=category,
        due_day=due_day,
        reference_month=ref_month,
    )
    return {"status": "created", "bill": result}


class UpdateBillRequest(BaseModel):
    paid: bool | None = None
    paid_amount: float | None = None
    bill_name: str | None = None
    budget: float | None = None
    category: str | None = None
    due_day: int | None = None


@app.patch("/api/finance/bills/{bill_id}")
async def update_finance_bill(
    bill_id: str,
    body: UpdateBillRequest,
    user: dict = Depends(get_current_user),
):
    """Update a bill (mark paid, change amount, etc)."""
    if body.paid is None and body.paid_amount is None and body.bill_name is None and body.budget is None:
        raise HTTPException(status_code=400, detail="At least one field must be provided")

    user_id = f"web:{user['username']}"
    store = get_finance_store()

    if body.paid is not None or body.paid_amount is not None:
        try:
            result = await asyncio.to_thread(
                store.update_bill_payment,
                user_id=user_id,
                bill_id=bill_id.strip(),
                paid=body.paid if body.paid is not None else False,
                paid_amount=body.paid_amount,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return result

    raise HTTPException(status_code=400, detail="Only payment updates are supported via this endpoint")


@app.delete("/api/finance/bills/{bill_id}")
async def delete_finance_bill(
    bill_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a bill."""
    user_id = f"web:{user['username']}"
    store = get_finance_store()
    deleted = await asyncio.to_thread(store.delete_bill, user_id, bill_id.strip())
    if not deleted:
        raise HTTPException(status_code=404, detail="Bill not found")
    return {"status": "deleted"}


# ---- Income endpoints ----

_MAX_INCOME_NAME_LEN = 200
_VALID_INCOME_CATEGORIES = {"Salário", "Consultoria", "Investimentos", "Transferência", "Outros"}


class CreateIncomeRequest(BaseModel):
    name: str
    amount: float
    category: str = "Outros"
    date: str | None = None


@app.post("/api/finance/income")
async def create_finance_income(
    body: CreateIncomeRequest,
    user: dict = Depends(get_current_user),
):
    """Register a financial income entry."""
    name = body.name.strip()
    if not name or len(name) > _MAX_INCOME_NAME_LEN:
        raise HTTPException(status_code=400, detail=f"name must be 1-{_MAX_INCOME_NAME_LEN} characters")
    if body.amount <= 0 or body.amount > _MAX_AMOUNT:
        raise HTTPException(status_code=400, detail="amount must be between 0 and 99999999.99")
    category = body.category.strip() or "Outros"

    import re
    income_date = None
    if body.date:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", body.date):
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        income_date = body.date
    else:
        from utils.timezone_utils import today_iso_in_configured_timezone
        income_date = today_iso_in_configured_timezone()

    user_id = f"web:{user['username']}"
    store = get_finance_store()
    result = await asyncio.to_thread(
        store.create_income,
        user_id=user_id,
        name=name,
        amount=body.amount,
        category=category,
        date=income_date,
    )
    return {"status": "created", "income": result}


@app.delete("/api/finance/income/{income_id}")
async def delete_finance_income(
    income_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete an income entry."""
    user_id = f"web:{user['username']}"
    store = get_finance_store()
    deleted = await asyncio.to_thread(store.delete_income, user_id, income_id.strip())
    if not deleted:
        raise HTTPException(status_code=404, detail="Income not found")
    return {"status": "deleted"}


# ---- Finance dashboard ----


@app.get("/api/finance/dashboard")
async def finance_dashboard(
    month: str | None = Query(None, description="YYYY-MM, defaults to current month"),
    user: dict = Depends(get_current_user),
):
    """Monthly finance dashboard: income + expenses + bills + totals."""
    import re
    from utils.timezone_utils import today_iso_in_configured_timezone

    if month:
        if not re.match(r"^\d{4}-\d{2}$", month):
            raise HTTPException(status_code=400, detail="month must be YYYY-MM")
        target_month = month
    else:
        target_month = today_iso_in_configured_timezone()[:7]

    user_id = f"web:{user['username']}"
    store = get_finance_store()

    async def fetch_expenses():
        try:
            return await asyncio.to_thread(store.list_expenses_by_month, user_id, target_month)
        except Exception:
            return []

    async def fetch_bills():
        try:
            return await asyncio.to_thread(store.list_bills_by_month, user_id, target_month)
        except Exception:
            return []

    async def fetch_income():
        try:
            return await asyncio.to_thread(store.list_income_by_month, user_id, target_month)
        except Exception:
            return []

    expenses, bills, income = await asyncio.gather(
        fetch_expenses(), fetch_bills(), fetch_income()
    )

    total_expenses = sum(float(e.get("amount") or 0) for e in expenses)
    total_budget = sum(float(b.get("budget") or 0) for b in bills)
    total_paid = sum(float(b.get("paid_amount") or 0) for b in bills if b.get("paid"))
    unpaid_count = sum(1 for b in bills if not b.get("paid"))
    total_income = sum(float(i.get("amount") or 0) for i in income)
    total_outgoing = total_expenses + total_paid
    balance = total_income - total_paid

    # Category breakdown for expenses
    cat_map: dict[str, float] = {}
    for e in expenses:
        cat = e.get("category", "Outros")
        cat_map[cat] = cat_map.get(cat, 0) + float(e.get("amount") or 0)
    category_breakdown = [{"category": k, "total": round(v, 2)} for k, v in sorted(cat_map.items(), key=lambda x: -x[1])]

    return {
        "month": target_month,
        "expenses": expenses,
        "bills": bills,
        "income": income,
        "totals": {
            "total_expenses": round(total_expenses, 2),
            "total_budget": round(total_budget, 2),
            "total_paid": round(total_paid, 2),
            "pending_budget": round(total_budget - total_paid, 2),
            "unpaid_count": unpaid_count,
            "total_income": round(total_income, 2),
            "total_outgoing": round(total_outgoing, 2),
            "balance": round(balance, 2),
        },
        "category_breakdown": category_breakdown,
    }


# ---- Health Goals endpoints ----


class UpdateHealthGoalsRequest(BaseModel):
    calorie_goal: int | None = None
    exercise_calorie_goal: int | None = None
    exercise_time_goal: int | None = None


@app.get("/api/health/goals")
async def get_health_goals_endpoint(user: dict = Depends(get_current_user)):
    from assistant_connector.health_store import HealthStore

    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    return await asyncio.to_thread(store.get_health_goals, user_id)


@app.put("/api/health/goals")
async def set_health_goals_endpoint(
    body: UpdateHealthGoalsRequest,
    user: dict = Depends(get_current_user),
):
    from assistant_connector.health_store import HealthStore

    for field, val in [
        ("calorie_goal", body.calorie_goal),
        ("exercise_calorie_goal", body.exercise_calorie_goal),
        ("exercise_time_goal", body.exercise_time_goal),
    ]:
        if val is not None and (val < 0 or val > 99999):
            raise HTTPException(status_code=400, detail=f"{field} must be between 0 and 99999")

    user_id = f"web:{user['username']}"
    store: HealthStore = get_health_store()
    return await asyncio.to_thread(
        store.set_health_goals,
        user_id,
        body.calorie_goal,
        body.exercise_calorie_goal,
        body.exercise_time_goal,
    )


# ---- Task endpoints ----

import re as _re
_DEADLINE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")


@app.get("/api/tasks/meta")
async def list_tasks_meta(
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    projects = store.list_task_projects(user["id"])
    tags = store.list_task_tags(user["id"])
    return {"projects": projects, "tags": tags}


@app.get("/api/tasks")
async def list_tasks(
    include_done: bool = Query(default=True),
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    tasks = store.list_tasks(user["id"], include_done=include_done)
    return {"tasks": tasks}


@app.post("/api/tasks", status_code=201)
async def create_task(
    body: TaskCreate,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    clean_name = body.name.strip() if body.name else ""
    if not clean_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task name is required")
    if len(clean_name) > 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task name too long (max 200 chars)")
    if body.deadline is not None and not _DEADLINE_RE.match(body.deadline):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deadline must be YYYY-MM-DD")
    clean_project = None
    if body.project is not None:
        clean_project = body.project.strip()[:100] or None
    clean_tags = [t.strip().lower()[:50] for t in (body.tags or []) if t.strip()][:10]
    clean_observations = None
    if body.observations is not None:
        clean_observations = body.observations.strip()[:2000] or None
    if body.always_on:
        current_count = store.count_always_on_tasks(user["id"])
        if current_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limite de 5 tarefas Always ON atingido",
            )
    task = store.create_task(
        user["id"], clean_name, deadline=body.deadline,
        project=clean_project, tags=clean_tags, always_on=body.always_on,
        observations=clean_observations,
    )
    return task


@app.patch("/api/tasks/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    name = None
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task name cannot be empty")
        if len(name) > 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task name too long (max 200 chars)")
    deadline = body.deadline
    if deadline != "__unset__" and deadline is not None and not _DEADLINE_RE.match(deadline):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deadline must be YYYY-MM-DD")
    project = body.project
    if project != "__unset__" and project is not None:
        project = project.strip()[:100] or None
    tags = None
    if body.tags is not None:
        tags = [t.strip().lower()[:50] for t in body.tags if t.strip()][:10]
    observations = body.observations
    if observations != "__unset__" and observations is not None:
        observations = observations.strip()[:2000] or None
    always_on = body.always_on
    if always_on is True:
        current_count = store.count_always_on_tasks(user["id"])
        existing = store.get_task(task_id, user["id"])
        already_on = existing and existing.get("always_on", False)
        if not already_on and current_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limite de 5 tarefas Always ON atingido",
            )
    updated = store.update_task(
        task_id, user["id"],
        name=name,
        deadline=deadline,
        project=project,
        done=body.done,
        always_on=always_on,
        tags=tags,
        observations=observations,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    store: WebUserStore = Depends(get_user_store),
):
    deleted = store.delete_task(task_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---- Template reader ----

def _read_template(name: str) -> str:
    path = os.path.join(_TEMPLATES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
