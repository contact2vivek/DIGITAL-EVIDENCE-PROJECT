import os
import json
import hashlib
import tempfile
from datetime import datetime, timezone

import cv2
import streamlit as st

from metadata import extract_metadata
from hash_calculator import calculate_hash
from frame_analyzer import analyze_frames


# ---------------- PAGE CONFIGURATION ----------------

st.set_page_config(
    page_title="Digital Evidence | Video Forensics",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------- DARK THEME STYLING ----------------

st.markdown("""
<style>
    .stApp {
        background-color: #0b1120;
        color: #e5e7eb;
    }

    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #273449;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    .hero {
        background: linear-gradient(120deg, #172554, #111827);
        border: 1px solid #334155;
        padding: 28px;
        border-radius: 16px;
        margin-bottom: 24px;
    }

    .hero h1 {
        color: #f8fafc;
        margin-bottom: 8px;
    }

    .hero p {
        color: #a5b4fc;
        margin-bottom: 0;
    }

    div[data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #273449;
        padding: 18px;
        border-radius: 12px;
    }

    .section-card {
        background: #111827;
        border: 1px solid #273449;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 12px;
    }

    .muted {
        color: #94a3b8;
        font-size: 0.9rem;
    }

    code {
        overflow-wrap: anywhere;
    }

    div.stButton > button,
    div.stDownloadButton > button {
        border-radius: 8px;
        min-height: 42px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------- HELPER FUNCTIONS ----------------

def calculate_sha256(file_path):
    """Calculate SHA-256 using chunks to avoid loading the entire file."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def get_frame_previews(video_path, number_of_previews=6):
    """Extract a small selection of frames for visual inspection."""
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        cap.release()
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    previews = []

    if total_frames <= 0:
        cap.release()
        return []

    # Choose evenly spaced frames.
    positions = sorted(set(
        int(i * (total_frames - 1) / max(number_of_previews - 1, 1))
        for i in range(min(number_of_previews, total_frames))
    ))

    for position in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, position)
        success, frame = cap.read()

        if success:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            previews.append((position, frame_rgb))

    cap.release()
    return previews


def format_duration(frame_count, fps):
    if fps and fps > 0:
        seconds = frame_count / fps
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes:02d}:{remaining_seconds:05.2f}"

    return "Unavailable"


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown("## 🔎 Evidence Lab")
    st.caption("VIDEO FORENSICS WORKSPACE")
    st.divider()

    page = st.radio(
        "NAVIGATION",
        [
            "Overview",
            "Video Metadata",
            "Hash Verification",
            "Frame Inspection",
            "Forensic Report"
        ]
    )

    st.divider()
    st.markdown("### Investigation")
    st.caption("Local session analysis")
    st.caption("Upload a video to begin.")

    st.divider()
    st.caption("Use only evidence you are authorized to examine.")


# ---------------- HEADER ----------------

st.markdown("""
<div class="hero">
    <h1>🔎 Video Forensic Analysis</h1>
    <p>Digital evidence inspection · Metadata · Integrity hashes · Frame review</p>
</div>
""", unsafe_allow_html=True)

st.info(
    "This tool provides preliminary technical analysis. "
    "Frame differences alone do not prove manipulation, and hashes prove "
    "identity only when compared with a trusted reference hash."
)


# ---------------- UPLOAD ----------------

uploaded_file = st.file_uploader(
    "Import video evidence",
    type=["mp4", "avi", "mov"],
    help="Supported formats: MP4, AVI and MOV."
)

if uploaded_file is None:
    st.markdown("### Welcome to Evidence Lab")
    st.write(
        "Upload a video to view its technical properties, calculate "
        "integrity hashes, inspect sample frames and export a report."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            '<div class="section-card"><h3>01 · Metadata</h3>'
            '<p class="muted">Resolution, frame rate, frame count and duration.</p>'
            '</div>',
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            '<div class="section-card"><h3>02 · Integrity</h3>'
            '<p class="muted">MD5 and SHA-256 hashes for later verification.</p>'
            '</div>',
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            '<div class="section-card"><h3>03 · Frame Review</h3>'
            '<p class="muted">Sample frames and preliminary frame-difference review.</p>'
            '</div>',
            unsafe_allow_html=True
        )

    st.stop()


# ---------------- PROCESS VIDEO ----------------

file_bytes = uploaded_file.getvalue()
file_sha256_upload = hashlib.sha256(file_bytes).hexdigest()

# Cache results for this exact file so switching pages does not
# repeat the full analysis unnecessarily.
cache_key = f"{uploaded_file.name}:{file_sha256_upload}"

if st.session_state.get("analysis_key") != cache_key:
    temp_path = None

    try:
        suffix = os.path.splitext(uploaded_file.name)[1].lower()

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False
        ) as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        with st.spinner("Analyzing video evidence. Large files may take time..."):
            metadata = extract_metadata(temp_path)

            if not metadata or metadata.get("frame_count", 0) <= 0:
                raise ValueError(
                    "OpenCV could not read video frames. "
                    "Try a valid MP4, AVI or MOV file."
                )

            md5_hash = calculate_hash(temp_path)
            sha256_hash = calculate_sha256(temp_path)

            # Existing analyzer compares consecutive frames.
            # Its results are frame differences, not confirmed alterations.
            frame_differences = analyze_frames(temp_path)

            previews = get_frame_previews(temp_path)

        st.session_state["analysis_key"] = cache_key
        st.session_state["analysis_result"] = {
            "filename": uploaded_file.name,
            "file_size_bytes": len(file_bytes),
            "metadata": metadata,
            "md5": md5_hash,
            "sha256": sha256_hash,
            "frame_differences": frame_differences,
            "previews": previews,
            "analysis_time_utc": datetime.now(timezone.utc).isoformat()
        }

    except Exception as error:
        st.error(f"Could not analyze this video: {error}")
        st.caption(
            "If this continues, open Streamlit Manage app → Logs "
            "and inspect the full error."
        )
        st.stop()

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


result = st.session_state.get("analysis_result")

if not result:
    st.warning("No analysis results are available yet.")
    st.stop()

metadata = result["metadata"]
frame_count = int(metadata.get("frame_count", 0))
width = int(metadata.get("frame_width", 0))
height = int(metadata.get("frame_height", 0))
fps = float(metadata.get("fps", 0) or 0)
duration = format_duration(frame_count, fps)


# ---------------- REPORT DATA ----------------

report = {
    "tool": "Video Forensic Analysis Tool",
    "filename": result["filename"],
    "file_size_bytes": result["file_size_bytes"],
    "analysis_time_utc": result["analysis_time_utc"],
    "metadata": metadata,
    "duration": duration,
    "integrity_hashes": {
        "md5": result["md5"],
        "sha256": result["sha256"]
    },
    "frame_difference_review": {
        "count_reported_by_existing_analyzer": len(
            result["frame_differences"]
        ),
        "sample_frame_numbers": result["frame_differences"][:100],
        "note": (
            "The existing analyzer flags frames that differ from the "
            "previous frame. Ordinary motion and scene changes can trigger "
            "this. These results are not proof of tampering."
        )
    },
    "limitations": [
        "Metadata may be missing or inaccurate.",
        "A hash is useful for integrity verification when compared with "
        "a trusted reference hash.",
        "Automated frame differences require human review."
    ]
}

report_json = json.dumps(report, indent=4)


# ---------------- OVERVIEW ----------------

if page == "Overview":
    st.subheader("Investigation Overview")

    st.markdown(
        f'<div class="section-card"><b>Evidence file</b><br>'
        f'{result["filename"]}<br>'
        f'<span class="muted">Size: '
        f'{result["file_size_bytes"] / (1024 * 1024):.2f} MB</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Frames", f"{frame_count:,}")
    c2.metric("Resolution", f"{width} × {height}")
    c3.metric("Frame rate", f"{fps:g} FPS")
    c4.metric("Duration", duration)

    st.markdown("### Integrity summary")

    h1, h2 = st.columns(2)

    with h1:
        st.markdown("**MD5**")
        st.code(result["md5"])

    with h2:
        st.markdown("**SHA-256**")
        st.code(result["sha256"])

    st.markdown("### Frame review summary")
    st.metric(
        "Frames flagged for review",
        f'{len(result["frame_differences"]):,}'
    )
    st.caption(
        "A frame being flagged means it differs from the previous frame "
        "according to the existing analyzer. This is expected in normal "
        "video and does not establish tampering."
    )

    st.download_button(
        "⬇ Download forensic report (JSON)",
        data=report_json,
        file_name="video_forensic_report.json",
        mime="application/json",
        use_container_width=True
    )


# ---------------- METADATA PAGE ----------------

elif page == "Video Metadata":
    st.subheader("📁 Video Metadata")

    rows = [
        ("File name", result["filename"]),
        ("File size", f'{result["file_size_bytes"]:,} bytes'),
        ("Frame count", f"{frame_count:,}"),
        ("Frame width", f"{width} pixels"),
        ("Frame height", f"{height} pixels"),
        ("Resolution", f"{width} × {height}"),
        ("Frames per second", f"{fps:g}"),
        ("Estimated duration", duration),
        ("Analysis time (UTC)", result["analysis_time_utc"])
    ]

    for label, value in rows:
        left, right = st.columns([1, 2])
        left.markdown(f"**{label}**")
        right.write(value)
        st.divider()

    st.caption(
        "These properties are read from the video using OpenCV. "
        "They are not a complete forensic extraction of container metadata."
    )


# ---------------- HASH PAGE ----------------

elif page == "Hash Verification":
    st.subheader("🔐 Evidence Integrity Hashes")

    st.write(
        "Use these hashes to identify this exact file and compare it with "
        "a separately recorded trusted reference."
    )

    st.markdown("**MD5**")
    st.code(result["md5"])

    st.markdown("**SHA-256**")
    st.code(result["sha256"])

    st.download_button(
        "⬇ Download hash record",
        data=json.dumps({
            "filename": result["filename"],
            "md5": result["md5"],
            "sha256": result["sha256"],
            "analysis_time_utc": result["analysis_time_utc"]
        }, indent=4),
        file_name="evidence_hashes.json",
        mime="application/json"
    )

    st.warning(
        "Calculating a hash does not by itself prove authenticity. "
        "Compare it with a trusted hash recorded earlier to check whether "
        "the file matches that reference."
    )


# ---------------- FRAME INSPECTION PAGE ----------------

elif page == "Frame Inspection":
    st.subheader("🎞 Frame Inspection")

    st.write(
        f"Extracted {len(result['previews'])} sample frames for visual review."
    )

    if result["previews"]:
        columns = st.columns(3)

        for index, (frame_number, frame_image) in enumerate(
            result["previews"]
        ):
            with columns[index % 3]:
                st.image(
                    frame_image,
                    caption=f"Frame {frame_number}",
                    use_container_width=True
                )
    else:
        st.warning("No preview frames could be extracted.")

    st.markdown("### Frame-difference review")

    differences = result["frame_differences"]

    st.metric("Frames flagged by existing analyzer", len(differences))

    if differences:
        st.write("Sample frame numbers:")
        st.write(differences[:100])

        if len(differences) > 100:
            st.caption("Only the first 100 frame numbers are displayed.")
    else:
        st.write("The analyzer did not flag any frame differences.")

    st.info(
        "Important: normal motion, camera movement, compression and scene "
        "changes can all cause frame differences. This method does not "
        "reliably identify altered or forged frames on its own."
    )


# ---------------- REPORT PAGE ----------------

elif page == "Forensic Report":
    st.subheader("📄 Forensic Report")

    st.write("Review the JSON report before downloading it.")
    st.json(report)

    st.download_button(
        "⬇ Download complete forensic report",
        data=report_json,
        file_name="video_forensic_report.json",
        mime="application/json",
        use_container_width=True
    )


# ---------------- FOOTER ----------------

st.divider()
st.caption(
    "Video Forensic Analysis Tool · Preliminary technical analysis · "
    "Preserve the original evidence file and document all examination steps."
)
