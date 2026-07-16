//! Length-prefixed frame codec (Core Channel, doc 10 §6.1).
//!
//! A frame is a 4-byte big-endian unsigned length header followed by that many
//! bytes of UTF-8 JSON. One message = one frame. This is the **exact** framing
//! the Python Core's `kanal.cerceve` uses — the shell speaks it verbatim and
//! never invents a new protocol. The codec is pure transport: it moves bytes,
//! it does not know what JSON they carry.

use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};

use crate::errors::{ShellError, ShellResult};

/// Size of the big-endian length header, in bytes.
pub const HEADER_SIZE: usize = 4;

/// Upper bound on a single frame payload (64 MiB), matching the Core
/// (`cerceve.MAX_FRAME_BYTES`). Anything larger belongs on the bulk plane
/// (doc 10 §11), never inlined as a control/stream frame.
pub const MAX_FRAME_BYTES: u32 = 64 * 1024 * 1024;

/// Write `payload` as one length-prefixed frame and flush it.
///
/// # Errors
/// Returns [`ShellError::Ipc`] if the payload exceeds [`MAX_FRAME_BYTES`] or the
/// underlying stream write fails.
pub async fn write_frame<W>(writer: &mut W, payload: &[u8]) -> ShellResult<()>
where
    W: AsyncWrite + Unpin + ?Sized,
{
    let len = u32::try_from(payload.len())
        .ok()
        .filter(|len| *len <= MAX_FRAME_BYTES)
        .ok_or_else(|| {
            ShellError::Ipc(format!(
                "frame payload of {} bytes exceeds max {MAX_FRAME_BYTES}",
                payload.len()
            ))
        })?;
    writer
        .write_all(&len.to_be_bytes())
        .await
        .map_err(|err| ShellError::Ipc(format!("could not write frame header: {err}")))?;
    writer
        .write_all(payload)
        .await
        .map_err(|err| ShellError::Ipc(format!("could not write frame payload: {err}")))?;
    writer
        .flush()
        .await
        .map_err(|err| ShellError::Ipc(format!("could not flush frame: {err}")))
}

/// Read one frame, or `Ok(None)` on a clean EOF at a frame boundary.
///
/// A clean EOF (the stream closes with no header bytes pending) is the orderly
/// end of the channel and yields `None`, mirroring the Core's `decode_frame`.
/// An EOF *inside* a header or payload is a protocol desync and surfaces as
/// [`ShellError::Ipc`].
///
/// # Errors
/// Returns [`ShellError::Ipc`] on a mid-frame EOF, an oversized length header,
/// or an underlying stream read failure.
pub async fn read_frame<R>(reader: &mut R) -> ShellResult<Option<Vec<u8>>>
where
    R: AsyncRead + Unpin + ?Sized,
{
    let mut header = [0u8; HEADER_SIZE];
    match fill(reader, &mut header).await? {
        Fill::Eof => return Ok(None),
        Fill::Full => {}
    }

    let length = u32::from_be_bytes(header);
    if length > MAX_FRAME_BYTES {
        return Err(ShellError::Ipc(format!(
            "frame length {length} exceeds max {MAX_FRAME_BYTES}"
        )));
    }
    if length == 0 {
        return Ok(Some(Vec::new()));
    }

    let mut payload = vec![0u8; length as usize];
    match fill(reader, &mut payload).await? {
        Fill::Full => Ok(Some(payload)),
        Fill::Eof => Err(ShellError::Ipc(format!(
            "stream closed mid-frame: expected {length}-byte payload"
        ))),
    }
}

/// Outcome of trying to fill a buffer: either fully filled, or a clean EOF
/// before any byte of it was read.
enum Fill {
    Full,
    Eof,
}

/// Read exactly `buf.len()` bytes, distinguishing a boundary EOF (no bytes read)
/// from a desync (stream ends after a partial fill).
async fn fill<R>(reader: &mut R, buf: &mut [u8]) -> ShellResult<Fill>
where
    R: AsyncRead + Unpin + ?Sized,
{
    let mut filled = 0;
    while filled < buf.len() {
        let read = reader
            .read(&mut buf[filled..])
            .await
            .map_err(|err| ShellError::Ipc(format!("could not read frame: {err}")))?;
        if read == 0 {
            if filled == 0 {
                return Ok(Fill::Eof);
            }
            return Err(ShellError::Ipc(format!(
                "stream closed mid-frame: read {filled}/{} bytes",
                buf.len()
            )));
        }
        filled += read;
    }
    Ok(Fill::Full)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[tokio::test]
    async fn round_trips_a_payload() {
        let mut buf = Vec::new();
        write_frame(&mut buf, b"hello").await.expect("write");
        let mut cursor = Cursor::new(buf);
        let frame = read_frame(&mut cursor).await.expect("read");
        assert_eq!(frame.as_deref(), Some(&b"hello"[..]));
    }

    #[tokio::test]
    async fn round_trips_json_with_embedded_newlines() {
        // The whole reason for length-prefixing over newline-delimited JSON.
        let payload = b"{\"text\":\"line1\\nline2\"}";
        let mut buf = Vec::new();
        write_frame(&mut buf, payload).await.expect("write");
        let mut cursor = Cursor::new(buf);
        let frame = read_frame(&mut cursor).await.expect("read");
        assert_eq!(frame.as_deref(), Some(&payload[..]));
    }

    #[tokio::test]
    async fn reads_back_to_back_frames_in_order() {
        let mut buf = Vec::new();
        write_frame(&mut buf, b"one").await.expect("write one");
        write_frame(&mut buf, b"two").await.expect("write two");
        let mut cursor = Cursor::new(buf);
        assert_eq!(
            read_frame(&mut cursor).await.expect("read one").as_deref(),
            Some(&b"one"[..])
        );
        assert_eq!(
            read_frame(&mut cursor).await.expect("read two").as_deref(),
            Some(&b"two"[..])
        );
    }

    #[tokio::test]
    async fn clean_eof_at_boundary_yields_none() {
        let mut cursor = Cursor::new(Vec::new());
        assert!(read_frame(&mut cursor).await.expect("read").is_none());
    }

    #[tokio::test]
    async fn empty_payload_is_a_valid_frame() {
        let mut buf = Vec::new();
        write_frame(&mut buf, b"").await.expect("write");
        let mut cursor = Cursor::new(buf);
        let frame = read_frame(&mut cursor).await.expect("read");
        assert_eq!(frame.as_deref(), Some(&b""[..]));
    }

    #[tokio::test]
    async fn mid_frame_eof_is_a_desync_error() {
        // A header promising 10 bytes but only 3 arrive.
        let mut bytes = 10u32.to_be_bytes().to_vec();
        bytes.extend_from_slice(b"abc");
        let mut cursor = Cursor::new(bytes);
        let err = read_frame(&mut cursor).await.expect_err("desync");
        assert_eq!(err.kind(), "ipc");
    }

    #[tokio::test]
    async fn oversized_length_header_is_rejected() {
        let mut cursor = Cursor::new((MAX_FRAME_BYTES + 1).to_be_bytes().to_vec());
        let err = read_frame(&mut cursor).await.expect_err("too large");
        assert_eq!(err.kind(), "ipc");
    }
}
