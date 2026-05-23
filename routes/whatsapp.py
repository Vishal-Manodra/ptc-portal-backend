# routes/whatsapp.py
# Meta WhatsApp Cloud API integration.
# Two endpoints:
#   GET  /whatsapp/webhook → Meta calls this to VERIFY our webhook (one time setup)
#   POST /whatsapp/webhook → Meta calls this every time a client sends a message
#
# Flow when client sends WhatsApp message:
# 1. Meta sends the message to our POST /whatsapp/webhook
# 2. We look up the client by their phone number
# 3. We understand what they asked (documents list, specific file, status)
# 4. We reply via Meta API with the answer

import os
import httpx
from fastapi import APIRouter, Request, HTTPException, Depends, status as fastapi_status
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from pydantic import BaseModel

from database import get_db
from models import Client, Document, WhatsappMessage, User
from auth import admin_or_employee

load_dotenv()

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
META_WHATSAPP_TOKEN = os.getenv("META_WHATSAPP_TOKEN")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

WHATSAPP_API_URL = f"https://graph.facebook.com/v19.0/{META_PHONE_NUMBER_ID}/messages"


# ── WEBHOOK VERIFICATION (one time, during Meta setup) ────────────────────────

@router.get("/webhook")
def verify_webhook(request: Request):
    """
    Meta calls this URL when you first set up the webhook in the Meta dashboard.
    It sends a challenge string and expects us to return it back.
    This proves we own and control this server.
    After this one-time verification, Meta starts sending messages to POST /webhook.
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        # Return the challenge as plain text — Meta checks this
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=challenge)

    raise HTTPException(status_code=403, detail="Webhook verification failed")


# ── RECEIVE INCOMING MESSAGES ─────────────────────────────────────────────────

@router.post("/webhook")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    """
    Meta calls this every time a client sends a WhatsApp message to your number.
    
    The incoming JSON has a complex nested structure. We extract:
    - sender's phone number
    - message text
    
    Then we figure out what they want and reply.
    """
    body = await request.json()

    # Navigate Meta's nested webhook payload structure
    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Sometimes Meta sends status updates (delivered, read) — ignore those
        if "messages" not in value:
            return {"status": "ignored"}

        message_data = value["messages"][0]
        sender_phone = message_data["from"]        # e.g. "919876543210"
        message_type = message_data.get("type")

        # We only handle text messages for now
        if message_type != "text":
            await send_whatsapp_message(
                sender_phone,
                "Sorry, I can only understand text messages right now. "
                "Please type your request."
            )
            return {"status": "non-text ignored"}

        incoming_text = message_data["text"]["body"].strip().lower()

    except (KeyError, IndexError):
        # Malformed payload — ignore silently (Meta resends if needed)
        return {"status": "ignored"}

    # Log the incoming message
    db.add(WhatsappMessage(
        client_phone=sender_phone,
        direction="inbound",
        message=incoming_text,
    ))
    db.commit()

    # Look up client by phone number
    # Strip country code variations: "919876543210" → try both with and without 91
    client = find_client_by_phone(sender_phone, db)

    if not client:
        reply = (
            "Hello! I couldn't find your account. "
            "Please contact your CA firm to link your WhatsApp number."
        )
        await send_whatsapp_message(sender_phone, reply)
        return {"status": "client not found"}

    # If the user replies with a number, we want to send the actual document file as a media message!
    if incoming_text.strip().isdigit():
        index = int(incoming_text.strip()) - 1
        docs = db.query(Document).filter(
            Document.client_id == client.id,
            Document.visible_to_client == True,
        ).order_by(Document.created_at.desc()).limit(10).all()

        if 0 <= index < len(docs):
            doc = docs[index]
            await send_whatsapp_document(
                to_phone=sender_phone,
                document_url=doc.file_url,
                filename=doc.file_name,
                caption=f"Here is your document: *{doc.file_name}*"
            )
            reply = f"Sent document: {doc.file_name}"
        else:
            reply = f"Invalid number. Please reply with a number between 1 and {len(docs)}."
            await send_whatsapp_message(sender_phone, reply)
    else:
        # Understand what the client wants and build a reply
        reply = await handle_client_request(incoming_text, client, db)
        # Send the reply
        await send_whatsapp_message(sender_phone, reply)

    # Log outbound message
    db.add(WhatsappMessage(
        client_phone=sender_phone,
        direction="outbound",
        message=reply,
    ))
    db.commit()

    return {"status": "ok"}


# ── HELPER: FIND CLIENT BY PHONE ──────────────────────────────────────────────

def find_client_by_phone(whatsapp_phone: str, db: Session):
    """
    WhatsApp sends phone as "919876543210" (with country code, no +).
    Our DB might store it as "9876543210" or "+919876543210".
    We try multiple formats to find a match.
    """
    # Try as-is first
    client = db.query(Client).filter(Client.phone == whatsapp_phone).first()
    if client:
        return client

    # Try without country code (remove leading 91 for India)
    if whatsapp_phone.startswith("91") and len(whatsapp_phone) == 12:
        local = whatsapp_phone[2:]
        client = db.query(Client).filter(Client.phone == local).first()
        if client:
            return client

    # Try with + prefix
    client = db.query(Client).filter(
        Client.phone == f"+{whatsapp_phone}"
    ).first()
    return client


# ── HELPER: UNDERSTAND REQUEST AND BUILD REPLY ────────────────────────────────

async def handle_client_request(text: str, client: Client, db: Session) -> str:
    """
    Simple keyword-based understanding of what the client wants.
    In the full version, this will use an LLM for natural language understanding.
    
    Keywords handled:
    - "hi", "hello", "help" → greeting + menu
    - "documents", "files", "docs" → list their documents
    - "status" → their service statuses
    """
    greeting = f"Hello {client.contact_person or client.business_name}! 👋\n\n"

    # Greeting / help menu
    if any(word in text for word in ["hi", "hello", "hey", "help", "menu"]):
        return (
            f"{greeting}"
            f"Welcome to *{client.business_name}*'s portal.\n\n"
            f"You can ask me:\n"
            f"• *documents* — see your files\n"
            f"• *status* — check your service progress\n"
            f"• Reply with a number to get that document sent directly as a file!\n\n"
            f"Your CA firm: PTC Portal"
        )

    # List documents
    if any(word in text for word in ["document", "documents", "files", "docs", "file"]):
        docs = db.query(Document).filter(
            Document.client_id == client.id,
            Document.visible_to_client == True,
        ).order_by(Document.created_at.desc()).limit(10).all()

        if not docs:
            return "No documents have been shared with you yet. Please contact your CA."

        doc_list = "\n".join([
            f"{i+1}. {doc.file_name} ({doc.file_type.upper() if doc.file_type else 'FILE'})"
            for i, doc in enumerate(docs)
        ])
        return (
            f"📁 *Your documents:*\n\n{doc_list}\n\n"
            f"Reply with the number to get the document file sent directly to your chat.\n"
            f"Example: reply *1* to get the first document."
        )

    # Service status
    if "status" in text or "progress" in text or "update" in text:
        if not client.services:
            return "No services are currently assigned to your account."

        status_list = "\n".join([
            f"• {cs.service.name}: {cs.status.replace('_', ' ').title()} "
            f"({cs.progress}%)"
            for cs in client.services
        ])
        return f"📊 *Your service status:*\n\n{status_list}"

    # Fallback
    return (
        "I didn't understand that. Here's what you can ask:\n\n"
        "• *documents* — see your files\n"
        "• *status* — check service progress\n"
        "• *help* — show this menu"
    )


# ── HELPER: SEND WHATSAPP MESSAGE ─────────────────────────────────────────────

async def send_whatsapp_message(to_phone: str, message: str):
    """
    Sends a text message via Meta WhatsApp Cloud API.
    Uses httpx (async HTTP client) to make the API call.
    """
    headers = {
        "Authorization": f"Bearer {META_WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            WHATSAPP_API_URL,
            headers=headers,
            json=payload,
            timeout=10.0,
        )
        if response.status_code != 200:
            print(f"WhatsApp send failed: {response.text}")


# ── HELPER: SEND WHATSAPP DOCUMENT (FULL FLEDGED FILE) ─────────────────────────

async def send_whatsapp_document(to_phone: str, document_url: str, filename: str, caption: str = None):
    """
    Sends an actual document media file (PDF, image, Excel, etc.) via Meta WhatsApp Cloud API.
    """
    headers = {
        "Authorization": f"Bearer {META_WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "document",
        "document": {
            "link": document_url,
            "filename": filename
        }
    }
    if caption:
        payload["document"]["caption"] = caption

    async with httpx.AsyncClient() as client:
        response = await client.post(
            WHATSAPP_API_URL,
            headers=headers,
            json=payload,
            timeout=10.0,
        )
        if response.status_code != 200:
            print(f"WhatsApp document file send failed: {response.text}")


# ── ADMIN INSTANT SHARE FILE TO CLIENT WHATSAPP ───────────────────────────────

class SendDocumentPayload(BaseModel):
    client_id: int
    document_id: int


@router.post("/send-document")
async def send_document_to_whatsapp(
    payload: SendDocumentPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee)
):
    """
    Directly sends the actual full-fledged document file to the client's WhatsApp number.
    Only admin or employee can call this endpoint.
    """
    client = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.client_id != client.id:
        raise HTTPException(status_code=400, detail="Document does not belong to this client")

    if current_user.role == "employee":
        if client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client")

    # Clean the recipient's phone number
    if not client.phone:
        raise HTTPException(
            status_code=400,
            detail="Client does not have a phone number registered."
        )

    to_phone = "".join(filter(str.isdigit, client.phone))
    if not to_phone.startswith("91") and len(to_phone) == 10:
        to_phone = f"91{to_phone}"

    # Dispatch full-fledged document attachment
    await send_whatsapp_document(
        to_phone=to_phone,
        document_url=doc.file_url,
        filename=doc.file_name,
        caption=f"Hello, here is your document *{doc.file_name}* from PTC Portal."
    )

    # Log outbound entry
    db.add(WhatsappMessage(
        client_phone=to_phone,
        direction="outbound",
        message=f"Directly shared file: {doc.file_name}",
    ))
    db.commit()

    return {"message": f"Document '{doc.file_name}' successfully sent to client WhatsApp number: +{to_phone}"}