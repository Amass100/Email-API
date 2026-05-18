from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import pyodbc
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from fastapi import Query
from datetime import date


load_dotenv()

app = FastAPI()


class Email(BaseModel):
    subject: Optional[str] = ""
    sender: Optional[str] = ""
    date: Optional[str] = ""
    category: Optional[str] = ""
    attachment_link: Optional[str] = ""
    mailbox: Optional[str] = ""
    body_preview: Optional[str] = ""
    recipients: Optional[str] = ""
    email_id: Optional[str] = ""


def get_connection():
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.getenv('FABRIC_SERVER')};"
        f"DATABASE={os.getenv('FABRIC_DATABASE')};"
        f"UID={os.getenv('FABRIC_USERNAME')};"
        f"PWD={os.getenv('FABRIC_PASSWORD')};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return pyodbc.connect(conn_str)


@app.get("/")
def home():
    conn = get_connection()
    conn.close()
    return {"status": "Database connection successful"}


@app.post("/emails")
def receive_email(email: Email):
    conn = get_connection()
    cursor = conn.cursor()

    if email.date and email.date.strip():
        try:
            received_dt = datetime.fromisoformat(
                email.date.replace("Z", "+00:00")
            )
        except Exception:
            received_dt = datetime.utcnow()
    else:
        received_dt = datetime.utcnow()

    print("DEBUG:")
    print("Subject:", email.subject)
    print("Sender:", email.sender)

    cursor.execute(
        """
        INSERT INTO dbo.EmailLogs (
            EmailID,
            Subject,
            Sender,
            Recipients,
            ReceivedDateTime,
            Category,
            AttachmentLink,
            Mailbox,
            BodyPreview,
            InsertedAt
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        email.email_id or "",
        email.subject or "",
        email.sender or "",
        email.recipients or "",
        received_dt,
        email.category or "",
        email.attachment_link or "",
        email.mailbox or "",
        email.body_preview or "",
        datetime.now(timezone.utc)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Email saved successfully"}


@app.get("/emails")
def get_emails(
    date_filter: Optional[date] = Query(None, alias="date"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,

    # New timestamp filters
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None,

    # Existing filters
    category: Optional[str] = None,

    # New filters
    mailbox: Optional[str] = None,
    sender: Optional[str] = None,
    subject_contains: Optional[str] = None,

    limit: int = 100
):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            EmailID,
            Subject,
            Sender,
            Recipients,
            ReceivedDateTime,
            Category,
            AttachmentLink,
            Mailbox,
            BodyPreview,
            InsertedAt
        FROM dbo.EmailLogs
        WHERE 1 = 1
    """

    params = []

    # Filter by specific date
    if date_filter:
        query += " AND CAST(ReceivedDateTime AS DATE) = ?"
        params.append(date_filter)

    # Filter by date range
    if start_date:
        query += " AND CAST(ReceivedDateTime AS DATE) >= ?"
        params.append(start_date)

    if end_date:
        query += " AND CAST(ReceivedDateTime AS DATE) <= ?"
        params.append(end_date)

    # Filter by exact timestamp range
    if start_datetime:
        query += " AND ReceivedDateTime >= ?"
        params.append(start_datetime)

    if end_datetime:
        query += " AND ReceivedDateTime <= ?"
        params.append(end_datetime)

    # Category filter
    if category:
        query += " AND Category = ?"
        params.append(category)

    # Mailbox filter (Inbox, Spam, etc.)
    if mailbox:
        query += " AND Mailbox = ?"
        params.append(mailbox)

    # Sender filter
    if sender:
        query += " AND Sender LIKE ?"
        params.append(f"%{sender}%")

    # Subject keyword search
    if subject_contains:
        query += " AND Subject LIKE ?"
        params.append(f"%{subject_contains}%")

    # Apply limit and sort
    query = query.replace("SELECT", f"SELECT TOP {limit}", 1)
    query += " ORDER BY ReceivedDateTime DESC"

    cursor.execute(query, params)

    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()

    results = []

    for row in rows:
        record = dict(zip(columns, row))

        # Format ReceivedDateTime
        if record.get("ReceivedDateTime"):
            record["ReceivedDateTime"] = (
                record["ReceivedDateTime"]
                .strftime("%m-%d-%Y %I:%M:%S %p UTC")
            )

        # Format InsertedAt
        if record.get("InsertedAt"):
            record["InsertedAt"] = (
                record["InsertedAt"]
                .strftime("%m-%d-%Y %I:%M:%S %p UTC")
            )

        results.append(record)

    cursor.close()
    conn.close()

    return {
        "count": len(results),
        "filters": {
            "date": date_filter,
            "start_date": start_date,
            "end_date": end_date,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "category": category,
            "mailbox": mailbox,
            "sender": sender,
            "subject_contains": subject_contains,
            "limit": limit
        },
        "emails": results
    }