import os
import uuid
import io
import zipfile
import shutil
import subprocess
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List


# --- Pydantic Models ---
class DownloadFile(BaseModel):
    filename: str
    original_name: str

class DownloadAllRequest(BaseModel):
    files: List[DownloadFile]


# --- App Setup ---
app = FastAPI(title="SlideDeck PDF")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
PDF_DIR = "pdfs"
LO_PROFILE_DIR = "/tmp/libreoffice_profile"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(LO_PROFILE_DIR, exist_ok=True)


# --- Core Conversion Logic (LibreOffice) ---
def convert_ppt_to_pdf(input_path: str, output_dir: str) -> str:
    """
    Uses LibreOffice in headless mode to convert a PPT/PPTX file to PDF.
    Returns the path to the generated PDF.
    """
    abs_input = os.path.abspath(input_path)
    abs_output_dir = os.path.abspath(output_dir)

    env = os.environ.copy()
    env["HOME"] = "/tmp"  # Ensure writable HOME for LibreOffice

    result = subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--norestore",
            "--nofirststartwizard",
            f"-env:UserInstallation=file://{LO_PROFILE_DIR}",
            "--convert-to", "pdf",
            "--outdir", abs_output_dir,
            abs_input,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    print(f"[DEBUG] LibreOffice stdout: {result.stdout}")
    print(f"[DEBUG] LibreOffice stderr: {result.stderr}")
    print(f"[DEBUG] LibreOffice returncode: {result.returncode}")

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion failed (code {result.returncode}): {result.stderr}")

    # LibreOffice names the output file based on the input filename
    input_basename = os.path.splitext(os.path.basename(abs_input))[0]
    expected_pdf = os.path.join(abs_output_dir, f"{input_basename}.pdf")

    if not os.path.exists(expected_pdf):
        raise RuntimeError("Conversion completed but PDF file was not found.")

    print(f"[OK] Converted: {abs_input} -> {expected_pdf}")
    return expected_pdf


# --- API Endpoints ---
@app.post("/api/convert")
async def upload_and_convert(file: UploadFile = File(...)):
    """Accepts a single PPT/PPTX file, converts it to PDF, returns download info."""
    if not file.filename.lower().endswith((".ppt", ".pptx")):
        raise HTTPException(status_code=400, detail="Only .ppt and .pptx files are supported.")

    file_id = str(uuid.uuid4())
    _, ext = os.path.splitext(file.filename)
    safe_filename = f"{file_id}{ext}"
    input_path = os.path.join(UPLOAD_DIR, safe_filename)

    # The user-friendly PDF name
    target_pdf_name = os.path.splitext(file.filename)[0] + ".pdf"

    # Save uploaded file
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Convert using LibreOffice
        generated_pdf_path = convert_ppt_to_pdf(input_path, PDF_DIR)

        # Rename to UUID-based name to avoid collisions
        final_pdf_name = f"{file_id}.pdf"
        final_pdf_path = os.path.join(PDF_DIR, final_pdf_name)
        os.rename(generated_pdf_path, final_pdf_path)

        return {
            "original_filename": file.filename,
            "pdf_filename": target_pdf_name,
            "download_url": f"/api/download/{final_pdf_name}?name={target_pdf_name}",
        }
    except Exception as e:
        print(f"[ERROR] Conversion exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{filename}")
async def download_pdf(filename: str, name: str | None = None):
    """Downloads a single converted PDF file."""
    file_path = os.path.join(PDF_DIR, filename)
    if os.path.exists(file_path):
        download_name = name if name else filename
        return FileResponse(file_path, media_type="application/pdf", filename=download_name)
    raise HTTPException(status_code=404, detail="File not found.")


@app.post("/api/download-all")
async def download_all(request: DownloadAllRequest):
    """Bundles all converted PDFs into a single ZIP for download."""
    if not request.files:
        raise HTTPException(status_code=400, detail="No files provided.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in request.files:
            file_path = os.path.join(PDF_DIR, f.filename)
            if os.path.exists(file_path):
                zf.write(file_path, arcname=f.original_name)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=converted_presentations.zip"},
    )


# --- Health Check ---
@app.get("/api/health")
async def health_check():
    """Simple health check endpoint for Render."""
    return {"status": "ok"}


# --- Serve Frontend ---
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
