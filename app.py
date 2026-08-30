from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
import os
import re
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

def get_detected_skills():
    """
    Gets the skills saved by the latest resume analysis.

    If the JSON file is empty, this function also checks the
    most recently modified PDF in the resumes folder. This
    prevents the Career Assistant from showing 0% simply
    because the skills JSON was empty/reset.
    """

    skills = load_json(SKILLS_FILE)

    if isinstance(skills, list) and skills:
        return sorted(set(str(skill) for skill in skills))

    # Fallback: inspect the newest uploaded PDF.
    try:
        pdf_files = []

        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.lower().endswith(".pdf"):
                path = os.path.join(UPLOAD_FOLDER, filename)

                if os.path.isfile(path):
                    pdf_files.append(path)

        if pdf_files:
            newest_pdf = max(
                pdf_files,
                key=os.path.getmtime
            )

            resume_text = extract_pdf_text(newest_pdf)

            if resume_text:
                skills = extract_skills(resume_text)

                if skills:
                    save_json(SKILLS_FILE, skills)

                    return skills

    except OSError:
        pass

    return []


# =========================================================
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

        flash("Account created successfully! Welcome to CareerNest.")
        return redirect(url_for("profile"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user():
        return redirect(url_for("dashboard"))

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
            return redirect(url_for("dashboard"))

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

    saved_ids = load_json(SAVED_FILE)
    applications = load_json(APPLICATION_FILE)
    detected_skills = get_detected_skills()

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

@app.route(
    "/upload_resume",
    methods=["POST"]
)
def upload_resume():

    resume = request.files.get(
        "resume"
    )

    if resume is None:
        return "No resume selected."

    if resume.filename == "":
        return "Please select a resume."

    if not resume.filename.lower().endswith(".pdf"):
        return "Please upload a PDF resume."

    safe_filename = secure_filename(
        resume.filename
    )

    if not safe_filename:
        return "Invalid resume filename."

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        safe_filename
    )

    resume.save(file_path)

    # -----------------------------------------------------
    # EXTRACT TEXT
    # -----------------------------------------------------

    resume_text = extract_pdf_text(file_path)

    if not resume_text:
        return (
            "Could not extract text from this PDF. "
            "Please upload a text-based PDF resume."
        )

    # -----------------------------------------------------
    # DETECT SKILLS
    # -----------------------------------------------------

    detected_skills = extract_skills(
        resume_text
    )

    # Save skills so Dashboard and Career Assistant
    # can use the same resume analysis.
    save_json(
        SKILLS_FILE,
        detected_skills
    )

    resume_skill_set = set(
        detected_skills
    )

    # -----------------------------------------------------
    # CALCULATE JOB MATCHES
    # -----------------------------------------------------

    recommendations = []

    for job in jobs:

        job_skill_set = extract_job_skills(
            job.get(
                "skills",
                ""
            )
        )

        matched_skills = sorted(
            resume_skill_set.intersection(
                job_skill_set
            )
        )

        missing_skills = sorted(
            job_skill_set
            - resume_skill_set
        )

        if job_skill_set:

            match_percentage = round(
                (
                    len(matched_skills)
                    / len(job_skill_set)
                ) * 100
            )

        else:

            match_percentage = 0

        recommendations.append({

            "id": job["id"],

            "title": job.get(
                "title",
                ""
            ),

            "company": job.get(
                "company",
                ""
            ),

            "location": job.get(
                "location",
                ""
            ),

            "skills": job.get(
                "skills",
                ""
            ),

            "type": job.get(
                "type",
                ""
            ),

            "salary": job.get(
                "salary",
                ""
            ),

            "mode": job.get(
                "mode",
                ""
            ),

            "match": match_percentage,

            "matched_skills":
                matched_skills,

            "missing_skills":
                missing_skills
        })

    # Highest match first.
    recommendations.sort(
        key=lambda job: job["match"],
        reverse=True
    )

    return render_template(
        "resume_result.html",

        resume_text=resume_text,

        detected_skills=detected_skills,

        recommendations=recommendations
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(
        debug=True
    )
