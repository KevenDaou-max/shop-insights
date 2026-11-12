"""Read uploaded files safely: enforce a size limit while reading, not after."""
from fastapi import HTTPException, UploadFile, status

CHUNK_BYTES = 1024 * 1024


def read_limited(upload: UploadFile, max_mb: int) -> bytes:
    max_bytes = max_mb * 1024 * 1024
    chunks, size = [], 0
    while chunk := upload.file.read(CHUNK_BYTES):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"'{upload.filename}' is larger than the {max_mb} MB limit.",
            )
        chunks.append(chunk)
    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"'{upload.filename}' is empty.")
    return b"".join(chunks)
