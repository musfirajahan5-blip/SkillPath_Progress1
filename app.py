from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
import os
import re
import hashlib
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = "careernest_secret_key"

# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "resumes")
DATA_FOLDER = os.path.join(BASE_DIR, "data")

APPLICATION_FILE = os.path.join(DATA_FOLDER, "applications.json")
SAVED_FILE = os.path.join(DATA_FOLDER, "saved_jobs.json")
SKILLS_FILE = os.path.join(DATA_FOLDER, "detected_skills.json")
USERS_FILE = os.path.join(DATA_FOLDER, "users.json")
PROFILE_FILE = os.path.join(DATA_FOLDER, "profile.json")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

def user_storage_key(email):
    return hashlib.sha256(str(email or "").strip().lower().encode("utf-8")).hexdigest()

def user_resume_folder(email):
    folder = os.path.join(UPLOAD_FOLDER, user_storage_key(email))
    os.makedirs(folder, exist_ok=True)
    return folder

def user_skills_file(email):
    folder = os.path.join(DATA_FOLDER, "user_skills")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, user_storage_key(email) + ".json")

def user_resume_file(email):
    return os.path.join(user_resume_folder(email), "resume.pdf")

def has_user_resume(email):
    path = user_resume_file(email)
    return os.path.isfile(path) and os.path.getsize(path) > 0


# =========================================================
# CREATE DATA FILES IF THEY DO NOT EXIST
# =========================================================

def ensure_json_file(filename):
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as file:
            json.dump([], file)


ensure_json_file(APPLICATION_FILE)
ensure_json_file(SAVED_FILE)
ensure_json_file(SKILLS_FILE)
ensure_json_file(USERS_FILE)
ensure_json_file(PROFILE_FILE)


# =========================================================
# JSON HELPERS
# =========================================================

def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)

        return data

    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


# =========================================================
# LOAD JOB DATA
# =========================================================

JOBS_FILE = os.path.join(DATA_FOLDER, "jobs.json")

try:
    with open(JOBS_FILE, "r", encoding="utf-8") as file:
        jobs = json.load(file)
except (FileNotFoundError, json.JSONDecodeError):
    jobs = []

# Give every job a stable numeric ID.
for index, job in enumerate(jobs):
    job["id"] = index


# =========================================================
# SKILL DATABASE
# =========================================================

SKILL_ALIASES = {
    "python": "Python",
    "java": "Java",
    "c++": "C++",

    "javascript": "JavaScript",
    "js": "JavaScript",

    "html": "HTML",
    "css": "CSS",

    "react": "React",

    "node.js": "Node.js",
    "nodejs": "Node.js",
    "node js": "Node.js",

    "sql": "SQL",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "mongodb": "MongoDB",

    "flask": "Flask",
    "django": "Django",

    "machine learning": "Machine Learning",
    "ml": "Machine Learning",

    "deep learning": "Deep Learning",
    "dl": "Deep Learning",

    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",

    "opencv": "OpenCV",
    "yolo": "YOLO",

    "computer vision": "Computer Vision",
    "cv": "Computer Vision",

    "nlp": "NLP",
    "natural language processing": "NLP",

    "transformers": "Transformers",
    "transformer": "Transformers",

    "bert": "BERT",

    "scikit-learn": "Scikit-learn",
    "scikit learn": "Scikit-learn",
    "sklearn": "Scikit-learn",

    "power bi": "Power BI",
    "powerbi": "Power BI",

    "excel": "Excel",

    "aws": "AWS",
    "azure": "Azure",
    "docker": "Docker",
    "linux": "Linux",

    "spring boot": "Spring Boot",

    "rest api": "REST API",
    "restful api": "REST API",

    "statistics": "Statistics",
    "data analysis": "Data Analysis",

    "numpy": "NumPy",
    "pandas": "Pandas",

    "git": "Git",
    "github": "GitHub",

    "cnn": "CNN",
    "rnn": "RNN"
}


# =========================================================
# CAREER PATH DATABASE
# =========================================================

CAREER_PATHS = {
    "AI / ML Engineer": [
        "Python",
        "Machine Learning",
        "Deep Learning",
        "NumPy",
        "Pandas",
        "Scikit-learn",
        "TensorFlow"
    ],

    "Data Scientist": [
        "Python",
        "Machine Learning",
        "Pandas",
        "NumPy",
        "Statistics",
        "SQL",
        "Data Analysis"
    ],

    "Computer Vision Engineer": [
        "Python",
        "Computer Vision",
        "OpenCV",
        "YOLO",
        "Deep Learning",
        "CNN",
        "TensorFlow"
    ],

    "NLP Engineer": [
        "Python",
        "NLP",
        "Machine Learning",
        "Transformers",
        "BERT",
        "Deep Learning"
    ],

    "Full Stack Developer": [
        "HTML",
        "CSS",
        "JavaScript",
        "React",
        "Node.js",
        "SQL",
        "Git"
    ],

    "Python Developer": [
        "Python",
        "Flask",
        "Django",
        "SQL",
        "Git",
        "REST API"
    ],

    "Data Analyst": [
        "Python",
        "SQL",
        "Excel",
        "Statistics",
        "Power BI",
        "Data Analysis"
    ]
}


# =========================================================
# SKILL HELPERS
# =========================================================

def contains_skill(text, skill):
    """
    Safely checks whether a skill occurs as a whole term.

    This prevents false matches such as:
    Java -> JavaScript
    ML -> unrelated words
    CV -> unrelated words
    """

    text = str(text or "").lower()
    skill = str(skill or "").lower()

    pattern = r"(?<!\w)" + re.escape(skill) + r"(?!\w)"

    return re.search(pattern, text) is not None


def extract_skills(text):
    detected_skills = set()

    for keyword, canonical_skill in SKILL_ALIASES.items():
        if contains_skill(text, keyword):
            detected_skills.add(canonical_skill)

    return sorted(detected_skills)


def extract_job_skills(job_skill_text):
    return set(extract_skills(job_skill_text))


# =========================================================
# RESUME TEXT EXTRACTION
# =========================================================

def extract_pdf_text(file_path):
    try:
        reader = PdfReader(file_path)

        text_parts = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text_parts.append(page_text)

        return "\n".join(text_parts).strip()

    except Exception:
        return ""


# =========================================================
# GET CURRENT DETECTED SKILLS
# =========================================================

def get_detected_skills(email=None):
    """Load or analyze skills from the current user's resume only."""
    if email is None:
        user = current_user()
        email = user.get("email") if user else None
    if not email:
        return []
    skills_path = user_skills_file(email)
    skills = load_json(skills_path)
    if isinstance(skills, list) and skills:
        return sorted(set(str(skill) for skill in skills))
    resume_path = user_resume_file(email)
    if os.path.isfile(resume_path):
        text = extract_pdf_text(resume_path)
        skills = extract_skills(text) if text else []
        save_json(skills_path, skills)
        return skills
    return []


# MODULE 10 — AUTHENTICATION & PROFILE HELPERS
# =========================================================

def current_user():
    email = session.get("user_email")

    if not email:
        return None

    users = load_json(USERS_FILE)

    for user in users:
        if user.get("email") == email:
            return user

    session.pop("user_email", None)
    return None


def login_required():
    return current_user() is not None


@app.context_processor
def inject_user():
    return {
        "current_user": current_user()
    }


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user():
        return redirect(url_for("profile"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Please fill in all required fields.")
            return redirect(url_for("register"))

        if "@" not in email or "." not in email:
            flash("Please enter a valid email address.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must contain at least 6 characters.")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("register"))

        users = load_json(USERS_FILE)

        if any(user.get("email") == email for user in users):
            flash("An account with this email already exists.")
            return redirect(url_for("login"))

        users.append({
            "name": name,
            "email": email,
            "password": generate_password_hash(password)
        })

        save_json(USERS_FILE, users)

        # Create/update a profile for the new user.
        profiles = load_json(PROFILE_FILE)
        profiles = [
            p for p in profiles
            if p.get("email") != email
        ]

        profiles.append({
            "email": email,
            "name": name,
            "phone": "",
            "headline": "",
            "location": "",
            "bio": ""
        })

        save_json(PROFILE_FILE, profiles)

        session["user_email"] = email

        flash("Account created successfully! Welcome to CareerNest. Please upload your resume.")
        return redirect(url_for("upload_resume"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user():
        return redirect(url_for("upload_resume") if not has_user_resume(current_user().get("email")) else url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        users = load_json(USERS_FILE)

        user = next(
            (
                u for u in users
                if u.get("email") == email
            ),
            None
        )

        if user and check_password_hash(
            user.get("password", ""),
            password
        ):
            session["user_email"] = email
            flash("Welcome back to CareerNest! 👋")
            return redirect(url_for("upload_resume") if not has_user_resume(email) else url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.pop("user_email", None)

    flash("You have been logged out.")

    return redirect(url_for("home"))


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile", methods=["GET", "POST"])
def profile():

    user = current_user()

    if not user:
        flash("Please log in to view your profile.")
        return redirect(url_for("login"))

    profiles = load_json(PROFILE_FILE)

    profile_data = next(
        (
            p for p in profiles
            if p.get("email") == user.get("email")
        ),
        {
            "email": user.get("email"),
            "name": user.get("name", ""),
            "phone": "",
            "headline": "",
            "location": "",
            "bio": ""
        }
    )

    if request.method == "POST":

        profile_data["name"] = request.form.get(
            "name",
            profile_data.get("name", "")
        ).strip()

        profile_data["phone"] = request.form.get(
            "phone",
            ""
        ).strip()

        profile_data["headline"] = request.form.get(
            "headline",
            ""
        ).strip()

        profile_data["location"] = request.form.get(
            "location",
            ""
        ).strip()

        profile_data["bio"] = request.form.get(
            "bio",
            ""
        ).strip()

        profile_data["email"] = user.get("email")

        profiles = [
            p for p in profiles
            if p.get("email") != user.get("email")
        ]

        profiles.append(profile_data)

        save_json(PROFILE_FILE, profiles)

        # Keep the displayed account name synchronized.
        users = load_json(USERS_FILE)

        for stored_user in users:
            if stored_user.get("email") == user.get("email"):
                stored_user["name"] = profile_data["name"]

        save_json(USERS_FILE, users)

        flash("Profile updated successfully! ✨")
        return redirect(url_for("profile"))

    return render_template(
        "profile.html",
        profile=profile_data
    )


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    saved_jobs = load_json(SAVED_FILE)

    return render_template(
        "index.html",
        jobs=jobs,
        saved_jobs=saved_jobs
    )


# =========================================================
# SEARCH JOBS
# =========================================================

@app.route("/search")
def search():

    query = request.args.get(
        "query",
        ""
    ).strip().lower()

    if not query:
        filtered_jobs = jobs

    else:
        filtered_jobs = []

        for job in jobs:

            searchable_text = (
                str(job.get("title", "")) + " "
                + str(job.get("company", "")) + " "
                + str(job.get("location", "")) + " "
                + str(job.get("skills", ""))
            ).lower()

            if query in searchable_text:
                filtered_jobs.append(job)

    saved_jobs = load_json(SAVED_FILE)

    return render_template(
        "index.html",
        jobs=filtered_jobs,
        saved_jobs=saved_jobs,
        search_query=query
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    user = current_user()
    if not user:
        flash("Please log in to view your dashboard.")
        return redirect(url_for("login"))
    saved_ids = load_json(SAVED_FILE)
    applications = load_json(APPLICATION_FILE)
    detected_skills = get_detected_skills(user.get("email"))

    applied_count = 0
    interview_count = 0
    selected_count = 0
    rejected_count = 0

    for application in applications:

        status = str(
            application.get("status", "Applied")
        ).strip().lower()

        if status == "applied":
            applied_count += 1

        elif status == "interview":
            interview_count += 1

        elif status == "selected":
            selected_count += 1

        elif status == "rejected":
            rejected_count += 1

    return render_template(
        "dashboard.html",

        jobs=jobs,

        jobs_count=len(jobs),

        saved_count=len(saved_ids),

        applications_count=len(applications),

        skills_count=len(detected_skills),

        detected_skills=detected_skills,

        applications=applications,

        applied_count=applied_count,

        interview_count=interview_count,

        selected_count=selected_count,

        rejected_count=rejected_count
    )


# =========================================================
# 🤖 AI CAREER ASSISTANT — MODULE 9
# =========================================================

@app.route("/career_assistant")
def career_assistant():

    # Get skills from the latest resume analysis.
    detected_skills = get_detected_skills()

    skill_set = set(detected_skills)

    career_results = []

    # -----------------------------------------------------
    # CALCULATE CAREER MATCHES
    # -----------------------------------------------------

    for career, required_skills in CAREER_PATHS.items():

        matched = []
        missing = []

        for skill in required_skills:

            if skill in skill_set:
                matched.append(skill)
            else:
                missing.append(skill)

        if required_skills:
            score = round(
                (
                    len(matched)
                    / len(required_skills)
                ) * 100
            )
        else:
            score = 0

        career_results.append({
            "career": career,
            "score": score,
            "matched": matched,
            "missing": missing
        })

    # Highest career match first.
    career_results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # -----------------------------------------------------
    # BEST CAREER
    # -----------------------------------------------------

    if career_results:

        best_career = career_results[0]

    else:

        best_career = {
            "career": "Explore Career Options",
            "score": 0,
            "matched": [],
            "missing": []
        }

    # -----------------------------------------------------
    # SKILL GAP
    # -----------------------------------------------------

    skill_gap = best_career["missing"][:5]

    # -----------------------------------------------------
    # PERSONALIZED LEARNING ROADMAP
    # -----------------------------------------------------

    roadmap = []

    roadmap_descriptions = {
        "Python":
            "Learn Python fundamentals, functions, OOP and practical programming.",

        "Machine Learning":
            "Study supervised and unsupervised learning and build an ML project.",

        "Deep Learning":
            "Learn neural networks and build a small deep-learning application.",

        "NumPy":
            "Practice numerical computing, arrays and mathematical operations.",

        "Pandas":
            "Learn data cleaning, filtering, grouping and analysis with Pandas.",

        "Scikit-learn":
            "Practice preprocessing, model training, evaluation and ML pipelines.",

        "TensorFlow":
            "Learn neural-network development and train a simple TensorFlow model.",

        "SQL":
            "Practice queries, joins, grouping, subqueries and database operations.",

        "Statistics":
            "Strengthen probability, distributions, hypothesis testing and statistics.",

        "Data Analysis":
            "Learn how to clean, analyze and communicate insights from datasets.",

        "Computer Vision":
            "Learn image processing, object detection and practical computer-vision workflows.",

        "OpenCV":
            "Practice image processing, contours, transformations and video analysis.",

        "YOLO":
            "Learn object detection and build a real-time detection project.",

        "CNN":
            "Understand convolutional neural networks and image classification.",

        "NLP":
            "Learn text preprocessing, embeddings and practical NLP techniques.",

        "Transformers":
            "Learn attention and transformer-based NLP models.",

        "BERT":
            "Understand BERT and practice transformer-based text classification.",

        "HTML":
            "Build responsive web pages using semantic HTML.",

        "CSS":
            "Practice layouts, responsive design, animations and modern styling.",

        "JavaScript":
            "Strengthen DOM manipulation, events, APIs and modern JavaScript.",

        "React":
            "Build component-based interfaces and practice React state and props.",

        "Node.js":
            "Learn backend development, APIs and server-side JavaScript.",

        "Git":
            "Practice version control, branches, commits and GitHub workflows.",

        "Flask":
            "Build Python web applications and REST-style routes with Flask.",

        "Django":
            "Learn Django project structure, models, views and templates.",

        "REST API":
            "Learn how to design, consume and test REST APIs.",

        "Excel":
            "Practice formulas, charts, pivot tables and data analysis.",

        "Power BI":
            "Create dashboards and learn data visualization with Power BI."
    }

    for index, skill in enumerate(
        skill_gap[:5],
        start=1
    ):

        description = roadmap_descriptions.get(
            skill,
            f"Learn the fundamentals of {skill} and build a small practical project."
        )

        roadmap.append({
            "step": index,
            "skill": skill,
            "description": description
        })

    # -----------------------------------------------------
    # CAREER READINESS SCORE
    # -----------------------------------------------------

    # A maximum of 14 detected skills gives 98%.
    # Cap the score at 100%.
    readiness_score = min(
        100,
        len(detected_skills) * 7
    )

    if readiness_score < 30:
        readiness_level = "Beginner"

    elif readiness_score < 60:
        readiness_level = "Developing"

    elif readiness_score < 80:
        readiness_level = "Job Ready"

    else:
        readiness_level = "Highly Prepared"

    return render_template(
        "career_assistant.html",

        detected_skills=detected_skills,

        career_results=career_results,

        best_career=best_career,

        skill_gap=skill_gap,

        roadmap=roadmap,

        readiness_score=readiness_score,

        readiness_level=readiness_level
    )


# =========================================================
# JOB DETAILS
# =========================================================

@app.route("/job/<int:job_id>")
def job_details(job_id):

    if job_id < 0 or job_id >= len(jobs):
        return "Job not found", 404

    job = jobs[job_id]

    saved_jobs = load_json(SAVED_FILE)

    is_saved = job_id in saved_jobs

    return render_template(
        "job_details.html",
        job=job,
        is_saved=is_saved
    )


# =========================================================
# SAVE / UNSAVE JOB
# =========================================================

@app.route(
    "/save_job/<int:job_id>",
    methods=["POST"]
)
def save_job(job_id):

    if job_id < 0 or job_id >= len(jobs):
        return "Job not found", 404

    saved_jobs = load_json(SAVED_FILE)

    # Remove duplicate IDs if they somehow exist.
    saved_jobs = list(dict.fromkeys(saved_jobs))

    if job_id in saved_jobs:

        saved_jobs.remove(job_id)

        message = "Job removed from saved jobs."

    else:

        saved_jobs.append(job_id)

        message = "Job saved successfully! ❤️"

    save_json(
        SAVED_FILE,
        saved_jobs
    )

    flash(message)

    return redirect(
        request.referrer
        or url_for("home")
    )


# =========================================================
# SAVED JOBS
# =========================================================

@app.route("/saved_jobs")
def saved_jobs_page():

    saved_ids = load_json(SAVED_FILE)

    saved_jobs = []

    for job_id in saved_ids:

        try:
            job_id = int(job_id)
        except (TypeError, ValueError):
            continue

        if 0 <= job_id < len(jobs):
            saved_jobs.append(jobs[job_id])

    return render_template(
        "saved_jobs.html",
        jobs=saved_jobs
    )


# =========================================================
# APPLY PAGE
# =========================================================

@app.route("/apply/<int:job_id>")
def apply_page(job_id):

    if job_id < 0 or job_id >= len(jobs):
        return "Job not found", 404

    job = jobs[job_id]

    return render_template(
        "apply.html",
        job=job
    )


# =========================================================
# SUBMIT APPLICATION
# =========================================================

@app.route(
    "/submit_application/<int:job_id>",
    methods=["POST"]
)
def submit_application(job_id):

    if job_id < 0 or job_id >= len(jobs):
        return "Job not found", 404

    job = jobs[job_id]

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    cover_letter = request.form.get(
        "cover_letter",
        ""
    ).strip()

    resume = request.files.get("resume")

    if not name:
        flash("Please enter your name.")
        return redirect(
            url_for(
                "apply_page",
                job_id=job_id
            )
        )

    if not email:
        flash("Please enter your email.")
        return redirect(
            url_for(
                "apply_page",
                job_id=job_id
            )
        )

    if not phone:
        flash("Please enter your phone number.")
        return redirect(
            url_for(
                "apply_page",
                job_id=job_id
            )
        )

    if resume is None or resume.filename == "":
        flash("Please upload your resume.")
        return redirect(
            url_for(
                "apply_page",
                job_id=job_id
            )
        )

    if not resume.filename.lower().endswith(".pdf"):
        flash("Only PDF resumes are allowed.")
        return redirect(
            url_for(
                "apply_page",
                job_id=job_id
            )
        )

    safe_filename = secure_filename(
        resume.filename
    )

    if not safe_filename:
        flash("Invalid resume filename.")
        return redirect(
            url_for(
                "apply_page",
                job_id=job_id
            )
        )

    resume_filename = (
        str(job_id)
        + "_"
        + re.sub(
            r"[^A-Za-z0-9_-]",
            "_",
            name
        )
        + "_"
        + safe_filename
    )

    resume_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        resume_filename
    )

    resume.save(resume_path)

    applications = load_json(
        APPLICATION_FILE
    )

    application = {
        "job_id": job_id,

        "job_title": job.get(
            "title",
            ""
        ),

        "company": job.get(
            "company",
            ""
        ),

        "name": name,

        "email": email,

        "phone": phone,

        "cover_letter": cover_letter,

        "resume": resume_filename,

        "status": "Applied"
    }

    applications.append(application)

    save_json(
        APPLICATION_FILE,
        applications
    )

    return render_template(
        "application_success.html",
        job=job,
        applicant_name=name
    )


# =========================================================
# APPLICATIONS
# =========================================================

@app.route("/applications")
def applications_page():

    applications = load_json(
        APPLICATION_FILE
    )

    return render_template(
        "applications.html",
        applications=applications
    )


# =========================================================
# RESUME UPLOAD + AI ANALYSIS
# =========================================================
@app.route("/upload_resume", methods=["GET", "POST"])
def upload_resume():
    user = current_user()
    if not user:
        flash("Please log in to upload your resume.")
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("resume_upload.html")

    resume = request.files.get("resume")
    if resume is None or not resume.filename:
        flash("Please select a resume.")
        return redirect(url_for("upload_resume"))
    if not resume.filename.lower().endswith(".pdf"):
        flash("Please upload a PDF resume.")
        return redirect(url_for("upload_resume"))

    safe_filename = secure_filename(resume.filename)
    if not safe_filename:
        flash("Invalid resume filename.")
        return redirect(url_for("upload_resume"))

    # Save each user's resume in their own folder, preserving account separation.
    resume_folder = user_resume_folder(user.get("email"))
    file_path = os.path.join(resume_folder, safe_filename)
    resume.save(file_path)

    resume_text = extract_pdf_text(file_path)
    if not resume_text:
        flash("Could not extract text from this PDF. Please upload a text-based PDF resume.")
        return redirect(url_for("upload_resume"))

    detected_skills = extract_skills(resume_text)
    save_json(user_skills_file(user.get("email")), detected_skills)

    resume_skill_set = set(detected_skills)
    recommendations = []
    for job in jobs:
        job_skill_set = set(extract_job_skills(job.get("skills", "")))
        matched_skills = sorted(resume_skill_set.intersection(job_skill_set))
        missing_skills = sorted(job_skill_set - resume_skill_set)
        match_percentage = round(len(matched_skills) / len(job_skill_set) * 100) if job_skill_set else 0
        recommendations.append({
            "id": job.get("id"), "title": job.get("title", ""),
            "company": job.get("company", ""), "location": job.get("location", ""),
            "skills": job.get("skills", ""), "type": job.get("type", ""),
            "salary": job.get("salary", ""), "mode": job.get("mode", ""),
            "match": match_percentage, "matched_skills": matched_skills,
            "missing_skills": missing_skills
        })
    recommendations.sort(key=lambda item: item["match"], reverse=True)
    return render_template("resume_result.html", resume_text=resume_text,
                           detected_skills=detected_skills, recommendations=recommendations)


# MODULE 11 — SKILLPATH CAREER DEVELOPMENT
# =========================================================

@app.route("/skillpath")
def skillpath():

    # -----------------------------------------------------
    # AUTHENTICATION
    # -----------------------------------------------------

    user = current_user()

    if not user:

        flash("Please log in to access SkillPath.")

        return redirect(url_for("login"))

    # -----------------------------------------------------
    # GET DETECTED SKILLS
    # -----------------------------------------------------

    detected_skills = get_detected_skills()

    detected_skill_set = set(detected_skills)

    # -----------------------------------------------------
    # CAREER MATCH ENGINE
    # -----------------------------------------------------

    career_results = []

    for career, required_skills in CAREER_PATHS.items():

        matched_skills = []

        missing_skills = []

        for skill in required_skills:

            if skill in detected_skill_set:

                matched_skills.append(skill)

            else:

                missing_skills.append(skill)

        # Calculate career match percentage.

        if required_skills:

            career_score = round(
                (
                    len(matched_skills)
                    / len(required_skills)
                ) * 100
            )

        else:

            career_score = 0

        # -------------------------------------------------
        # CAREER EXPLANATION
        # -------------------------------------------------

        if matched_skills:

            explanation = (
                f"You already have {len(matched_skills)} "
                f"of the {len(required_skills)} listed "
                f"skills for this career."
            )

        else:

            explanation = (
                "Start by developing the foundational "
                "skills required for this career."
            )

        # -------------------------------------------------
        # STORE CAREER RESULTS
        # -------------------------------------------------

        career_results.append({

            "career": career,

            "score": career_score,

            "matched": matched_skills,

            "missing": missing_skills,

            "required": required_skills,

            "explanation": explanation

        })

    # -----------------------------------------------------
    # SORT CAREER MATCHES
    # -----------------------------------------------------

    career_results.sort(

        key=lambda item: item["score"],

        reverse=True

    )

    # -----------------------------------------------------
    # BEST CAREER
    # -----------------------------------------------------

    if career_results:

        best_career = career_results[0]

    else:

        best_career = {

            "career": "Explore Career Options",

            "score": 0,

            "matched": [],

            "missing": [],

            "required": [],

            "explanation": (
                "Upload your resume to discover career options."
            )

        }

    # -----------------------------------------------------
    # SKILL DNA
    # -----------------------------------------------------

    skill_dna = {

        "Programming": [

            "Python",

            "Java",

            "C++",

            "JavaScript"

        ],

        "AI and Machine Learning": [

            "Machine Learning",

            "Deep Learning",

            "TensorFlow",

            "PyTorch"

        ],

        "Data Analysis": [

            "Pandas",

            "NumPy",

            "Statistics",

            "SQL",

            "Data Analysis"

        ],

        "Web Development": [

            "HTML",

            "CSS",

            "JavaScript",

            "React",

            "Flask",

            "Django"

        ],

        "Computer Vision": [

            "Computer Vision",

            "OpenCV",

            "YOLO",

            "CNN"

        ],

        "Development Tools": [

            "Git",

            "GitHub",

            "Docker",

            "Linux"

        ]

    }

    skill_dna_results = []

    for category, category_skills in skill_dna.items():

        matched = [

            skill

            for skill in category_skills

            if skill in detected_skill_set

        ]

        if category_skills:

            category_score = round(

                len(matched)
                / len(category_skills)
                * 100
            )

        else:

            category_score = 0

        skill_dna_results.append({

            "category": category,

            "score": category_score,

            "matched": matched,

            "total": len(category_skills)

        })

    # -----------------------------------------------------
    # SKILL GAP
    # -----------------------------------------------------

    skill_gap = best_career["missing"]

    # -----------------------------------------------------
    # ROADMAP DESCRIPTIONS
    # -----------------------------------------------------

    roadmap_descriptions = {

        "Python":
            "Learn Python fundamentals, functions, "
            "OOP and practical programming.",

        "Machine Learning":
            "Study supervised and unsupervised learning "
            "and build a machine-learning project.",

        "Deep Learning":
            "Learn neural networks and build a "
            "deep-learning application.",

        "NumPy":
            "Practice numerical computing, arrays "
            "and mathematical operations.",

        "Pandas":
            "Learn data cleaning, filtering, grouping "
            "and data analysis.",

        "Scikit-learn":
            "Practice preprocessing, model training "
            "and model evaluation.",

        "TensorFlow":
            "Learn neural-network development "
            "and train a simple model.",

        "SQL":
            "Practice queries, joins, grouping "
            "and database operations.",

        "Statistics":
            "Strengthen probability, distributions "
            "and statistical analysis.",

        "Data Analysis":
            "Learn how to clean, analyze "
            "and interpret datasets.",

        "Computer Vision":
            "Learn image processing, object detection "
            "and computer-vision workflows.",

        "OpenCV":
            "Practice image processing, contours "
            "and transformations.",

        "YOLO":
            "Learn object detection and build "
            "a real-time detection project.",

        "CNN":
            "Understand convolutional neural networks "
            "and image classification.",

        "NLP":
            "Learn text preprocessing, embeddings "
            "and NLP techniques.",

        "Transformers":
            "Learn attention mechanisms "
            "and transformer-based models.",

        "BERT":
            "Understand BERT and practice "
            "text classification.",

        "HTML":
            "Build responsive web pages "
            "using semantic HTML.",

        "CSS":
            "Practice layouts, responsive design "
            "and modern styling.",

        "JavaScript":
            "Practice DOM manipulation, events "
            "and APIs.",

        "React":
            "Build component-based interfaces "
            "and practice React state.",

        "Node.js":
            "Learn backend development "
            "and server-side JavaScript.",

        "Git":
            "Practice version control, branches "
            "and GitHub workflows.",

        "Flask":
            "Build Python web applications "
            "using Flask.",

        "Django":
            "Learn Django models, views "
            "and templates.",

        "REST API":
            "Learn to design, consume "
            "and test REST APIs.",

        "Excel":
            "Practice formulas, charts "
            "and data analysis.",

        "Power BI":
            "Create dashboards and learn "
            "   data visualization."

    }

    # -----------------------------------------------------
    # PERSONALIZED ROADMAP
    # -----------------------------------------------------

    roadmap = []

    for index, skill in enumerate(

        skill_gap,

        start=1

    ):

        description = roadmap_descriptions.get(

            skill,

            f"Learn the fundamentals of {skill} "
            "and build a practical project."

        )

        roadmap.append({

            "step": index,

            "skill": skill,

            "description": description

        })

    # -----------------------------------------------------
    # READINESS
    # -----------------------------------------------------

    # This is an assessment-free profile indicator.
    # It is NOT an examination score.

    if detected_skills:

        readiness_score = min(

            100,

            round(

                len(detected_skills)
                / max(
                    1,
                    len(SKILL_ALIASES)
                )
                * 100

            )

        )

    else:

        readiness_score = 0

    if readiness_score < 30:

        readiness_level = "Beginner"

    elif readiness_score < 60:

        readiness_level = "Developing"

    elif readiness_score < 80:

        readiness_level = "Progressing"

    else:

        readiness_level = "Skill Profile Developed"

    # -----------------------------------------------------
    # RENDER SKILLPATH
    # -----------------------------------------------------

    return render_template(

        "skillpath.html",

        detected_skills=detected_skills,

        career_results=career_results,

        best_career=best_career,

        skill_gap=skill_gap,

        roadmap=roadmap,

        skill_dna_results=skill_dna_results,

        readiness_score=readiness_score,

        readiness_level=readiness_level

    )

# =========================================================
# MODULE 12 — SKILL ASSESSMENT
# =========================================================

ASSESSMENT_FILE = os.path.join(DATA_FOLDER, "assessment_results.json")
ensure_json_file(ASSESSMENT_FILE)

ASSESSMENT_QUESTIONS = {
    "Python": [
        {"question": "Which keyword defines a function?", "options": ["function", "def", "fun", "define"], "answer": "def"},
        {"question": "Which data type stores key-value pairs?", "options": ["List", "Tuple", "Dictionary", "Set"], "answer": "Dictionary"},
        {"question": "What is 2 ** 3?", "options": ["6", "8", "9", "5"], "answer": "8"},
        {"question": "Which method adds an item to the end of a list?", "options": ["add()", "insert()", "append()", "push()"], "answer": "append()"},
        {"question": "Which keyword begins exception handling?", "options": ["catch", "try", "error", "check"], "answer": "try"},
        {"question": "Which symbol begins a Python comment?", "options": ["//", "#", "/*", "--"], "answer": "#"},
        {"question": "Which function returns the length of a list?", "options": ["size()", "length()", "len()", "count()"], "answer": "len()"},
        {"question": "Which data type is immutable?", "options": ["List", "Dictionary", "Set", "Tuple"], "answer": "Tuple"},
        {"question": "Which loop iterates over a sequence?", "options": ["repeat", "foreach", "for", "iterate"], "answer": "for"},
        {"question": "Which keyword creates a class?", "options": ["object", "class", "struct", "define"], "answer": "class"}
    ],
    "SQL": [
        {"question": "Which SQL command retrieves data?", "options": ["GET", "SELECT", "FETCHALL", "OPEN"], "answer": "SELECT"},
        {"question": "Which clause filters rows?", "options": ["ORDER BY", "GROUP BY", "WHERE", "JOIN"], "answer": "WHERE"},
        {"question": "Which command adds a row?", "options": ["INSERT", "UPDATE", "ALTER", "CREATE"], "answer": "INSERT"},
        {"question": "Which function counts rows?", "options": ["SUM()", "COUNT()", "TOTAL()", "NUMBER()"], "answer": "COUNT()"},
        {"question": "Which clause sorts results?", "options": ["SORT", "ORDER BY", "GROUP BY", "ARRANGE"], "answer": "ORDER BY"},
        {"question": "Which command modifies existing records?", "options": ["INSERT", "UPDATE", "CREATE", "SELECT"], "answer": "UPDATE"},
        {"question": "Which keyword removes duplicate results?", "options": ["UNIQUE", "DISTINCT", "REMOVE", "FILTER"], "answer": "DISTINCT"},
        {"question": "Which command deletes a table?", "options": ["REMOVE TABLE", "DELETE TABLE", "DROP TABLE", "CLEAR TABLE"], "answer": "DROP TABLE"},
        {"question": "Which operator checks a range?", "options": ["BETWEEN", "RANGE", "INRANGE", "WITHIN"], "answer": "BETWEEN"},
        {"question": "Which clause groups rows?", "options": ["ORDER BY", "GROUP BY", "WHERE", "JOIN"], "answer": "GROUP BY"}
    ],
    "Machine Learning": [
        {"question": "Which algorithm is commonly used for classification?", "options": ["Linear Regression", "Logistic Regression", "K-Means", "PCA"], "answer": "Logistic Regression"},
        {"question": "What is supervised learning?", "options": ["Learning without data", "Learning from labeled data", "Learning without models", "Clustering only"], "answer": "Learning from labeled data"},
        {"question": "Which algorithm is used for clustering?", "options": ["K-Means", "Linear Regression", "Logistic Regression", "Decision Tree Regression"], "answer": "K-Means"},
        {"question": "What is overfitting?", "options": ["Good training performance but poor unseen-data performance", "Poor performance on all data", "No parameters", "No training data"], "answer": "Good training performance but poor unseen-data performance"},
        {"question": "Which Python library is commonly used for ML?", "options": ["Flask", "Scikit-learn", "BeautifulSoup", "Requests"], "answer": "Scikit-learn"},
        {"question": "Which technique predicts continuous values?", "options": ["Classification", "Linear Regression", "K-Means", "Apriori"], "answer": "Linear Regression"},
        {"question": "What is a feature?", "options": ["Model output", "Input variable", "Error message", "Training algorithm"], "answer": "Input variable"},
        {"question": "What is a test dataset used for?", "options": ["Training", "Evaluating performance", "Removing features", "Increasing training data"], "answer": "Evaluating performance"},
        {"question": "Which technique can reduce overfitting?", "options": ["Regularization", "Removing all training data", "Increasing complexity", "Ignoring validation"], "answer": "Regularization"},
        {"question": "What does a confusion matrix evaluate?", "options": ["Database performance", "Classification performance", "Memory usage", "Dataset size"], "answer": "Classification performance"}
    ]
}

ASSESSMENT_ROADMAP = {
    "Python": ["Revise Python fundamentals and data structures", "Practice functions and object-oriented programming", "Solve coding exercises", "Build a Python mini-project"],
    "SQL": ["Practice SELECT and WHERE queries", "Learn JOIN operations", "Practice GROUP BY and aggregate functions", "Build a database project"],
    "Machine Learning": ["Learn data preprocessing", "Study supervised and unsupervised learning", "Practice model evaluation", "Build a machine-learning project"]
}


def assessment_level(percentage):
    if percentage >= 80:
        return "Advanced"
    if percentage >= 60:
        return "Intermediate"
    if percentage >= 40:
        return "Beginner"
    return "Needs Improvement"


def assessment_recommendation(level):
    return {
        "Advanced": "You demonstrated strong knowledge. Practice advanced problems and build projects.",
        "Intermediate": "You understand the fundamentals. Practice intermediate concepts and practical exercises.",
        "Beginner": "Revise fundamentals and solve beginner-level problems.",
        "Needs Improvement": "Start with the fundamentals and practice regularly."
    }.get(level, "Continue practicing this skill.")


@app.route("/assessment")
def assessment_home():
    user = current_user()
    if not user:
        flash("Please log in to take a skill assessment.")
        return redirect(url_for("login"))
    results = load_json(ASSESSMENT_FILE)
    user_results = [r for r in results if r.get("email") == user.get("email")]

    # Only show assessments for skills found in this user's resume.
    resume_skills = set(get_detected_skills(user.get("email")))
    available_skills = [skill for skill in ASSESSMENT_QUESTIONS if skill in resume_skills]
    return render_template(
        "assessment.html",
        skills=available_skills,
        user_results=user_results,
        resume_skills=sorted(resume_skills),
    )


@app.route("/assessment/start/<skill>")
def assessment_start(skill):
    if not current_user():
        flash("Please log in to take an assessment.")
        return redirect(url_for("login"))
    user = current_user()
    resume_skills = set(get_detected_skills(user.get("email")))
    questions = ASSESSMENT_QUESTIONS.get(skill)
    if questions is None or skill not in resume_skills:
        flash("This assessment is available only for skills detected in your uploaded resume.")
        return redirect(url_for("assessment_home"))
    safe_questions = [{"question": q["question"], "options": q["options"]} for q in questions]
    return render_template("assessment_exam.html", skill=skill, questions=safe_questions)


@app.route("/assessment/submit/<skill>", methods=["POST"])
def submit_assessment(skill):
    user = current_user()
    if not user:
        flash("Please log in to submit your assessment.")
        return redirect(url_for("login"))
    resume_skills = set(get_detected_skills(user.get("email")))
    questions = ASSESSMENT_QUESTIONS.get(skill)
    if questions is None or skill not in resume_skills:
        flash("This assessment is available only for skills detected in your uploaded resume.")
        return redirect(url_for("assessment_home"))

    correct = sum(
        request.form.get(f"question_{index}", "") == question["answer"]
        for index, question in enumerate(questions)
    )
    total = len(questions)
    percentage = round((correct / total) * 100, 2) if total else 0
    level = assessment_level(percentage)
    result = {
        "email": user.get("email"),
        "skill": skill,
        "total_questions": total,
        "correct_answers": correct,
        "percentage": percentage,
        "level": level,
        "recommendation": assessment_recommendation(level),
        "date": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
        "roadmap": ASSESSMENT_ROADMAP.get(skill, [f"Practice {skill} fundamentals", f"Build a {skill} project"])
    }
    results = load_json(ASSESSMENT_FILE)
    if not isinstance(results, list):
        results = []
    results.append(result)
    save_json(ASSESSMENT_FILE, results)
    return render_template("assessment_result.html", result=result)


@app.route("/assessment/history")
def assessment_history():
    user = current_user()
    if not user:
        flash("Please log in to view assessment history.")
        return redirect(url_for("login"))
    results = load_json(ASSESSMENT_FILE)
    user_results = [r for r in results if r.get("email") == user.get("email")]
    user_results.reverse()
    return render_template("assessment_history.html", results=user_results)



# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(
        debug=True
    )