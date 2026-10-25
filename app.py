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


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="INT533 | Digital Forensics Lab",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# PREMIUM DARK THEME
# =========================================================

st.markdown("""
<style>
    .stApp {
        background:
            radial-gradient(ellipse at top left, #172554 0%, transparent 42%),
            #080e1b;
        color: #e2e8f0;
    }

    [data-testid="stSidebar"] {
        background: #0c1424;
        border-right: 1px solid #26354d;
    }

    .block-container {
        max-width: 1450px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .hero {
        background: linear-gradient(125deg, #172554, #111827, #102b3a);
        border: 1px solid #334b68;
        border-radius: 20px;
        padding: 32px;
        margin-bottom: 24px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.2);
    }

    .hero h1 {
        color: #f8fafc;
        font-size: 2.25rem;
        font-weight: 800;
        letter-spacing: -0.8px;
        margin: 8px 0;
    }

    .hero p {
        color: #a5f3fc;
        font-size: 1rem;
    }

    .student {
        color: #cbd5e1;
        font-size: 0.95rem;
    }

    .eyebrow {
        color: #67e8f9;
        font-size: 12px;
        letter-spacing: 3px;
        font-weight: 700;
    }

    .section-card {
        background: linear-gradient(145deg, #111d30, #0c1525);
        border: 1px solid #293c56;
        padding: 20px;
        border-radius: 14px;
        margin-bottom: 14px;
    }

    .section-card h3 {
        color: #e2e8f0;
    }

    .muted {
        color: #94a3b8;
        font-size: 0.9rem;
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #111d30, #0d1727);
        border: 1px solid #293c56;
        padding: 18px;
        border-radius: 14px;
    }

    div[data-testid="stMetricLabel"] {
        color: #94a3b8;
    }

    div[data-testid="stMetricValue"] {
        color: #67e8f9;
    }

    .stButton > button,
    .stDownloadButton > button {
        border: 1px solid #3b82a0;
        border-radius: 10px;
        min-height: 42px;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: #67e8f9;
        color: #67e8f9;
    }

    div[data-testid="stFileUploader"] {
        background: #101b2d;
        border: 1px dashed #3b5574;
        border-radius: 14px;
        padding: 12px;
    }

    h1, h2, h3 {
        color: #f1f5f9;
    }

    hr {
        border-color: #26354d;
    }

    code {
        overflow-wrap: anywhere;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def calculate_sha256(file_path):
    """Calculate SHA-256 without loading the entire file into memory."""
    digest = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def extract_preview_frames(video_path, limit=6):
    """Extract evenly spaced frames for visual inspection."""
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        cap.release()
        return []

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    previews = []

    if total <= 0:
        cap.release()
        return []

    positions = sorted(set(
        int(i * (total - 1) / max(limit - 1, 1))
        for i in range(min(limit, total))
    ))

    for position in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, position)
        success, frame = cap.read()

        if success:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            previews.append((position, rgb))

    cap.release()
    return previews


def safe_json_value(value):
    """Convert common Python values to JSON-compatible values."""
    if isinstance(value, dict):
        return {str(k): safe_json_value(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [safe_json_value(v) for v in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def format_duration(frame_count, fps):
    if fps > 0:
        seconds = frame_count / fps
        minutes = int(seconds // 60)
        remainder = seconds % 60
        return f"{minutes:02d}:{remainder:05.2f}"

    return "Unavailable"


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown("## 🔎 FORENSICS LAB")
    st.caption("INT533 · DIGITAL FORENSIC LAB")

    st.divider()

    st.markdown("### Vivek Raj")
    st.caption("Student / Developer")
    st.caption("Video Forensic Analysis Project")

    st.divider()

    page = st.radio(
        "INVESTIGATION MODULES",
        [
            "Overview",
            "Video Metadata",
            "Hash Verification",
            "Frame Inspection",
            "Forensic Report"
        ]
    )

    st.divider()

    st.markdown("**WORKFLOW**")
    st.caption("01 · Import video evidence")
    st.caption("02 · Examine video properties")
    st.caption("03 · Calculate file hashes")
    st.caption("04 · Inspect sample frames")
    st.caption("05 · Export analysis report")

    st.divider()
    st.caption("Academic project · INT533")


# =========================================================
# MAIN DASHBOARD HEADER
# =========================================================

st.markdown("""
<div class="hero">
    <div class="eyebrow">INT533 · DIGITAL FORENSIC LAB</div>
    <h1>🔎 Digital Evidence & Video Forensics</h1>
    <p>
        Investigate video properties. Verify file integrity.
        Examine frames. Document your findings.
    </p>
    <div class="student">
        <strong>Student / Developer:</strong> Vivek Raj
        &nbsp; | &nbsp;
        <strong>Subject:</strong> INT533 — Digital Forensic Lab
    </div>
</div>
""", unsafe_allow_html=True)

st.info(
    "Educational forensic analysis workspace. Automated results support "
    "investigation but do not independently establish authenticity or tampering."
)


# =========================================================
# VIDEO UPLOAD
# =========================================================

uploaded_file = st.file_uploader(
    "📂 Import Video Evidence",
    type=["mp4", "avi", "mov", "mkv"],
    help="Upload a video you are authorized to examine."
)

if uploaded_file is None:
    st.markdown("## Welcome to the Digital Forensics Lab")
    st.write(
        "Upload a video to examine its technical properties, calculate "
        "cryptographic hashes, inspect sample frames and generate a report."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="section-card">
            <h3>01 · Metadata</h3>
            <p class="muted">
                Examine frame count, resolution, frame rate and duration.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="section-card">
            <h3>02 · Integrity</h3>
            <p class="muted">
                Calculate MD5 and SHA-256 hashes to support file verification.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="section-card">
            <h3>03 · Reporting</h3>
            <p class="muted">
                Review extracted frames and download a structured JSON report.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.markdown("### About this academic project")
    st.markdown("""
    **Student:** Vivek Raj

    **Subject:** INT533 — Digital Forensic Lab

    This project demonstrates practical video evidence examination,
    cryptographic hashing, metadata review, frame inspection and
    forensic documentation.
    """)

    st.stop()


# =========================================================
# PROCESS UPLOADED VIDEO
# =========================================================

file_bytes = uploaded_file.getvalue()
file_sha256_upload = hashlib.sha256(file_bytes).hexdigest()
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

        with st.spinner("Examining video evidence..."):
            metadata = extract_metadata(temp_path)

            if not isinstance(metadata, dict):
                raise ValueError(
                    "The metadata module did not return a dictionary."
                )

            md5_hash = calculate_hash(temp_path)
            sha256_hash = calculate_sha256(temp_path)

            frame_differences = analyze_frames(temp_path)

            if frame_differences is None:
                frame_differences = []

            previews = extract_preview_frames(temp_path)

            st.session_state["analysis_result"] = {
                "filename": uploaded_file.name,
                "file_size_bytes": len(file_bytes),
                "metadata": metadata,
                "md5": str(md5_hash),
                "sha256": sha256_hash,
                "frame_differences": safe_json_value(frame_differences),
                "previews": previews,
                "analysis_time_utc": datetime.now(
                    timezone.utc
                ).isoformat()
            }

            st.session_state["analysis_key"] = cache_key

    except Exception as error:
        st.error(f"Video analysis failed: {error}")
        st.caption(
            "Check the Streamlit logs if the problem continues. "
            "Your existing analysis modules may use different field names "
            "or return formats."
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
    st.warning("No analysis results are available.")
    st.stop()


# =========================================================
# NORMALIZE METADATA
# =========================================================

metadata = result["metadata"]

frame_count = int(metadata.get("frame_count", 0) or 0)
width = int(metadata.get("frame_width", 0) or 0)
height = int(metadata.get("frame_height", 0) or 0)
fps = float(metadata.get("fps", 0) or 0)

duration = format_duration(frame_count, fps)

frame_differences = result["frame_differences"]

if isinstance(frame_differences, (list, tuple, dict, str)):
    difference_count = len(frame_differences)
else:
    difference_count = 0


# =========================================================
# BUILD REPORT
# =========================================================

report = {
    "project": "Digital Evidence & Video Forensics",
    "student": "Vivek Raj",
    "subject": "INT533 - Digital Forensic Lab",
    "filename": result["filename"],
    "file_size_bytes": result["file_size_bytes"],
    "analysis_time_utc": result["analysis_time_utc"],
    "metadata": safe_json_value(metadata),
    "estimated_duration": duration,
    "integrity_hashes": {
        "md5": result["md5"],
        "sha256": result["sha256"]
    },
    "frame_review": {
        "result_count": difference_count,
        "sample_results": safe_json_value(frame_differences)[:100]
        if isinstance(frame_differences, (list, tuple))
        else safe_json_value(frame_differences),
        "interpretation": (
            "Frame differences require human review. Ordinary motion, "
            "lighting changes, compression and scene cuts can produce "
            "differences. They do not prove manipulation."
        )
    },
    "limitations": [
        "Metadata may be incomplete or inaccurate.",
        "Hash comparison requires a trusted reference hash.",
        "A hash alone does not prove video authenticity.",
        "Automated frame differences do not establish tampering."
    ]
}

report_json = json.dumps(report, indent=4, ensure_ascii=False)


# =========================================================
# OVERVIEW PAGE
# =========================================================

if page == "Overview":
    st.subheader("📊 Investigation Overview")

    st.markdown(
        f"""
        <div class="section-card">
            <div class="muted">CURRENT EVIDENCE FILE</div>
            <h3>{result["filename"]}</h3>
            <p class="muted">
                File size: {result["file_size_bytes"] / (1024 * 1024):.2f} MB
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Frames", f"{frame_count:,}")
    c2.metric("Resolution", f"{width} × {height}")
    c3.metric("Frame Rate", f"{fps:g} FPS")
    c4.metric("Duration", duration)

    st.markdown("### 🔐 Evidence Integrity")

    h1, h2 = st.columns(2)

    with h1:
        st.markdown("**MD5 HASH**")
        st.code(result["md5"])

    with h2:
        st.markdown("**SHA-256 HASH**")
        st.code(result["sha256"])

    st.markdown("### 🎞 Frame Review")

    st.metric("Results from Existing Analyzer", difference_count)

    st.caption(
        "These are preliminary frame-difference results, not confirmed "
        "tampering detections."
    )

    st.download_button(
        "⬇ Download Forensic Report (JSON)",
        data=report_json,
        file_name="video_forensic_report.json",
        mime="application/json",
        use_container_width=True
    )


# =========================================================
# VIDEO METADATA PAGE
# =========================================================

elif page == "Video Metadata":
    st.subheader("📁 Video Metadata Analysis")

    rows = [
        ("File name", result["filename"]),
        ("File size", f'{result["file_size_bytes"]:,} bytes'),
        ("Frame count", f"{frame_count:,}"),
        ("Frame width", f"{width} pixels"),
        ("Frame height", f"{height} pixels"),
        ("Resolution", f"{width} × {height}"),
        ("Frame rate", f"{fps:g} FPS"),
        ("Estimated duration", duration),
        ("Analysis timestamp (UTC)", result["analysis_time_utc"])
    ]

    for label, value in rows:
        left, right = st.columns([1, 2])
        left.markdown(f"**{label}**")
        right.write(value)
        st.divider()

    st.markdown("### Raw Metadata")
    st.json(safe_json_value(metadata))

    st.caption(
        "These are the properties returned by your existing metadata module. "
        "They are not a complete extraction of every video-container field."
    )


# =========================================================
# HASH VERIFICATION PAGE
# =========================================================

elif page == "Hash Verification":
    st.subheader("🔐 Cryptographic Hash Analysis")

    st.write(
        "A hash acts as a digital fingerprint of the file contents. "
        "Comparing it with a trusted reference can help identify changes."
    )

    st.markdown("### MD5")
    st.code(result["md5"])

    st.markdown("### SHA-256")
    st.code(result["sha256"])

    hash_record = {
        "filename": result["filename"],
        "md5": result["md5"],
        "sha256": result["sha256"],
        "analysis_time_utc": result["analysis_time_utc"]
    }

    st.download_button(
        "⬇ Download Hash Record",
        data=json.dumps(hash_record, indent=4),
        file_name="evidence_hashes.json",
        mime="application/json"
    )

    st.warning(
        "This application calculates hashes but does not independently "
        "verify them against a trusted reference file. MD5 is retained for "
        "compatibility; SHA-256 is recommended for modern integrity checks."
    )


# =========================================================
# FRAME INSPECTION PAGE
# =========================================================

elif page == "Frame Inspection":
    st.subheader("🎞 Video Frame Inspection")

    previews = result["previews"]

    st.write(
        f"Sample frames extracted for visual review: {len(previews)}"
    )

    if previews:
        columns = st.columns(3)

        for index, (frame_number, frame_image) in enumerate(previews):
            with columns[index % 3]:
                st.image(
                    frame_image,
                    caption=f"Frame number: {frame_number}",
                    use_container_width=True
                )
    else:
        st.warning(
            "No preview frames could be extracted from this video."
        )

    st.divider()
    st.markdown("### Preliminary Frame-Difference Results")

    st.metric("Results Reported", difference_count)

    if isinstance(frame_differences, (list, tuple)):
        if frame_differences:
            st.write("Sample results:")
            st.json(safe_json_value(frame_differences[:100]))
        else:
            st.write("The existing analyzer returned no flagged results.")
    else:
        st.json(safe_json_value(frame_differences))

    st.info(
        "Motion, lighting, compression and scene changes can all produce "
        "frame differences. Review these results in context; they do not "
        "prove that a video has been altered."
    )


# =========================================================
# FORENSIC REPORT PAGE
# =========================================================

elif page == "Forensic Report":
    st.subheader("📄 Forensic Examination Report")

    st.markdown("""
    <div class="section-card">
        <h3>Report Information</h3>
        <p class="muted">
            Student: Vivek Raj<br>
            Subject: INT533 — Digital Forensic Lab<br>
            Format: JSON
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.json(report)

    st.download_button(
        "⬇ Download Complete Forensic Report",
        data=report_json,
        file_name="video_forensic_report.json",
        mime="application/json",
        use_container_width=True
    )


# =========================================================
# EDUCATIONAL PROJECT EXPLANATION
# =========================================================

st.divider()

st.markdown("## 📘 Project Working & Learning Outcomes")

with st.expander("1. How does this project work?", expanded=True):
    st.markdown("""
    1. **Evidence import:** The user uploads a video file for examination.
    2. **Metadata examination:** The application reads available technical
       properties such as resolution, frame count and frame rate.
    3. **Hash calculation:** The application calculates MD5 and SHA-256
       hashes from the file contents.
    4. **Frame inspection:** Selected video frames are extracted for
       visual examination.
    5. **Preliminary analysis:** Results from the existing frame analyzer
       are presented for human review.
    6. **Reporting:** The findings are packaged into a downloadable JSON
       report for documentation.
    """)

with st.expander("2. Why are hash values beneficial?"):
    st.markdown("""
    A cryptographic hash is a fixed-length digital fingerprint derived
    from a file's contents.

    - **Integrity checking:** Compare the current hash with a trusted hash
      recorded earlier to check whether the file still matches.
    - **Evidence handling:** Record hashes when evidence is acquired and
      whenever it is transferred or examined.
    - **Repeatability:** Another examiner can calculate a hash and compare
      the result with the recorded reference.
    - **Documentation:** Hash values can be included in examination reports.

    MD5 is provided for compatibility with existing workflows. SHA-256
    is a stronger modern choice. A matching hash does not prove that a
    video was genuine before the reference hash was created.
    """)

with st.expander("3. How can this project help people?"):
    st.markdown("""
    - **Digital forensic investigators:** organize technical observations
      and document evidence examination.
    - **Cybersecurity professionals:** compare files against known,
      trusted integrity references.
    - **Legal and investigation teams:** use documented hash values as
      one part of an evidence-handling process.
    - **Students and researchers:** learn practical concepts involving
      video properties, cryptographic hashes and forensic reports.

    This tool supports technical examination. It does not by itself
    establish who created a video, where it originated, or whether it is
    authentic.
    """)

with st.expander("4. How does this align with INT533 — Digital Forensic Lab?"):
    st.markdown("""
    This project demonstrates practical digital forensic concepts:

    - Digital evidence identification and examination.
    - Technical metadata collection.
    - Cryptographic hashing and integrity concepts.
    - Frame-level visual inspection.
    - Structured documentation and forensic reporting.
    - Awareness of evidence preservation and examination limitations.

    The workflow helps connect theoretical digital forensics concepts
    with a practical Python application.
    """)

with st.expander("5. What can we achieve with this tool?"):
    st.markdown("""
    - Inspect supported video files.
    - View basic video properties.
    - Calculate MD5 and SHA-256 hashes.
    - Extract selected frames for manual inspection.
    - Review preliminary frame-difference results.
    - Export a structured JSON report.
    - Learn how digital evidence examination is documented.
    """)

with st.expander("6. Forensic limitations and responsible use"):
    st.markdown("""
    - Preserve the original evidence and examine a working copy when possible.
    - Record how and when evidence was obtained.
    - A hash is only useful for integrity comparison when there is a
      trustworthy reference value.
    - Frame differences can result from ordinary motion, scene cuts,
      lighting changes or compression.
    - This version does not perform validated deepfake detection,
      audio forensics, or a complete chain-of-custody workflow.
    - Human review and appropriate forensic procedures are necessary
      before drawing conclusions.
    """)

st.markdown("""
<div class="section-card">
    <div class="eyebrow">ACADEMIC PROJECT</div>
    <h3>Video Forensic Analysis Tool</h3>
    <p class="muted">
        Student / Developer: Vivek Raj<br>
        Subject: INT533 — Digital Forensic Lab
    </p>
</div>
""", unsafe_allow_html=True)

st.caption(
    "Educational project for digital forensic examination. "
    "Preserve original evidence and document all analysis steps."
)
