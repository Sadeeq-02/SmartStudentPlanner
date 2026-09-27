from flask import Flask, render_template, request, redirect, session
from dotenv import load_dotenv
import os
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import random
import time
import smtplib
from email.message import EmailMessage

load_dotenv()

MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

def send_otp_email(recipient, otp):

    message = EmailMessage()

    message["Subject"] = "Big Dollar University - Password Reset OTP"
    message["From"] = MAIL_USERNAME
    message["To"] = recipient

    message.set_content(
        f"""Your Big Dollar University password reset OTP is:

{otp}

This OTP is valid for 10 minutes.

If you did not request a password reset, ignore this email.
"""
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
        smtp.send_message(message)
app = Flask(__name__)
app.secret_key = "change-this-to-a-random-secret-key"
def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function
DATABASE = "planner.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection

@app.route("/register", methods=["GET", "POST"])
def register():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        register_number = request.form["register_number"].strip()
        full_name = request.form["full_name"].strip()
        password = request.form["password"]

        if not register_number or not full_name or not password:
            connection.close()
            return "All fields are required."

        hashed_password = generate_password_hash(password)

        try:
            cursor.execute("""
                INSERT INTO users
                (register_number, full_name, password)
                VALUES (?, ?, ?)
            """, (
                register_number,
                full_name,
                hashed_password
            ))

            connection.commit()

        except sqlite3.IntegrityError:
            connection.close()
            return "That register number is already registered."

        connection.close()

        return redirect("/login")

    connection.close()

    return render_template("register.html")


    


@app.route("/login", methods=["GET", "POST"])
def login():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        register_number = request.form["register_number"].strip()
        password = request.form["password"]

        cursor.execute("""
            SELECT *
            FROM users
            WHERE register_number = ?
        """, (register_number,))

        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["register_number"] = user["register_number"]
            session["full_name"] = user["full_name"]

            connection.close()

            return redirect("/")

        connection.close()

        return "Invalid register number or password."

    connection.close()

    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        register_number = request.form["register_number"].strip()
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            connection.close()
            return "Passwords do not match."

        if not register_number or not new_password:
            connection.close()
            return "All fields are required."

        cursor.execute("""
            SELECT id
            FROM users
            WHERE register_number = ?
        """, (register_number,))

        user = cursor.fetchone()

        if not user:
            connection.close()
            return "Register number not found."

        hashed_password = generate_password_hash(new_password)

        cursor.execute("""
            UPDATE users
            SET password = ?
            WHERE register_number = ?
        """, (hashed_password, register_number))

        connection.commit()
        connection.close()

        return redirect("/login")

    connection.close()

    return render_template("forgot_password.html")

@app.route("/")
@login_required
def home():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM courses")
    total_courses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM study_sessions")
    total_sessions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assignments")
    total_assignments = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM assignments
        WHERE completed = 0
    """)
    pending_assignments = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM exams
        WHERE exam_date >= ?
    """, (date.today().isoformat(),))
    upcoming_exams = cursor.fetchone()[0]

    cursor.execute("""
        SELECT *
        FROM students
        ORDER BY id DESC
        LIMIT 1
    """)
    student = cursor.fetchone()

    cursor.execute("""
        SELECT courses.units, grades.grade
        FROM grades
        JOIN courses
        ON grades.course_id = courses.id
    """)

    grades = cursor.fetchall()

    grade_points = {
        "A": 5,
        "B": 4,
        "C": 3,
        "D": 2,
        "E": 1,
        "F": 0
    }

    total_points = 0
    total_units = 0

    for row in grades:

        grade = row["grade"].upper()
        units = row["units"]

        if grade in grade_points:
            total_points += grade_points[grade] * units
            total_units += units

    if total_units > 0:
        gpa = round(total_points / total_units, 2)
    else:
        gpa = 0

    if total_assignments > 0:
        completed_assignments = total_assignments - pending_assignments

        assignment_progress = round(
            (completed_assignments / total_assignments) * 100
        )
    else:
        completed_assignments = 0
        assignment_progress = 0

    connection.close()

    return render_template(
        "index.html",
        total_courses=total_courses,
        total_sessions=total_sessions,
        pending_assignments=pending_assignments,
        upcoming_exams=upcoming_exams,
        student=student,
        gpa=gpa,
        total_assignments=total_assignments,
        completed_assignments=completed_assignments,
        assignment_progress=assignment_progress
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip()
        department = request.form["department"].strip()
        level = request.form["level"].strip()

        if not name:
            connection.close()
            return "Name is required."

        cursor.execute("""
            INSERT INTO students
            (name, email, department, level)
            VALUES (?, ?, ?, ?)
        """, (name, email, department, level))

        connection.commit()

    cursor.execute("""
        SELECT *
        FROM students
        ORDER BY id DESC
    """)

    students = cursor.fetchall()

    connection.close()

    return render_template(
        "profile.html",
        students=students
    )


@app.route("/courses", methods=["GET", "POST"])
@login_required
def courses():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        course_code = request.form["course_code"].strip()
        course_name = request.form["course_name"].strip()

        try:
            units = int(request.form["units"])
        except ValueError:
            connection.close()
            return "Units must be a number."

        semester_id = request.form.get("semester_id", "").strip()

        if not course_code or not course_name:
            connection.close()
            return "Course code and course name are required."

        if units < 1 or units > 10:
            connection.close()
            return "Units must be between 1 and 10."

        if semester_id:
            try:
                semester_id = int(semester_id)
            except ValueError:
                connection.close()
                return "Invalid semester."

        else:
            semester_id = None

        cursor.execute("""
            INSERT INTO courses
            (course_code, course_name, units, semester_id user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            course_code,
            course_name,
            units,
            semester_id,
            session["user_id"]
        ))

        connection.commit()

    cursor.execute("""
        SELECT *
        FROM semesters
        ORDER BY academic_year DESC, id DESC
    """)

    semesters = cursor.fetchall()

    cursor.execute("""
        SELECT
            courses.id,
            courses.course_code,
            courses.course_name,
            courses.units,
            semesters.name AS semester_name,
            semesters.academic_year
        FROM courses
        LEFT JOIN semesters
        ON courses.semester_id = semesters.id
        WHERE courses.user_id = ?
        ORDER BY courses.id DESC
    """, (session["user_id"],))

    courses_list = cursor.fetchall()

    connection.close()

    return render_template(
        "courses.html",
        courses=courses_list,
        semesters=semesters
    )

@app.route("/timetable", methods=["GET", "POST"])
@login_required
def timetable():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        course_id = request.form["course_id"]
        day = request.form["day"]
        start_time = request.form["start_time"]

        try:
            duration = int(request.form["duration"])
        except ValueError:
            connection.close()
            return "Duration must be a number."

        if duration < 15 or duration > 600:
            connection.close()
            return "Duration must be between 15 and 600 minutes."

        cursor.execute("""
            INSERT INTO study_sessions
            (course_id, day, start_time, duration)
            VALUES (?, ?, ?, ?)
        """, (
            course_id,
            day,
            start_time,
            duration
        ))

        connection.commit()

    cursor.execute("""
        SELECT *
        FROM courses
        ORDER BY course_code
    """)

    courses_list = cursor.fetchall()

    cursor.execute("""
        SELECT
            study_sessions.id,
            courses.course_code,
            courses.course_name,
            study_sessions.day,
            study_sessions.start_time,
            study_sessions.duration
        FROM study_sessions
        JOIN courses
        ON study_sessions.course_id = courses.id
        ORDER BY study_sessions.day, study_sessions.start_time
    """)

    sessions = cursor.fetchall()

    connection.close()

    return render_template(
        "timetable.html",
        courses=courses_list,
        sessions=sessions
    )


@app.route("/assignments", methods=["GET", "POST"])
@login_required
def assignments():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        course_id = request.form["course_id"]
        title = request.form["title"].strip()
        description = request.form["description"].strip()
        deadline = request.form["deadline"].strip()

        if not title or not deadline:
            connection.close()
            return "Title and deadline are required."

        try:
            date.fromisoformat(deadline)
        except ValueError:
            connection.close()
            return "Invalid deadline date."

        cursor.execute("""
            INSERT INTO assignments
            (course_id, title, description, deadline)
            VALUES (?, ?, ?, ?)
        """, (
            course_id,
            title,
            description,
            deadline
        ))

        connection.commit()

    cursor.execute("""
        SELECT *
        FROM courses
        ORDER BY course_code
    """)

    courses_list = cursor.fetchall()

    cursor.execute("""
        SELECT
            assignments.id,
            assignments.title,
            assignments.description,
            assignments.deadline,
            assignments.completed,
            courses.course_code,
            courses.course_name
        FROM assignments
        JOIN courses
        ON assignments.course_id = courses.id
        ORDER BY assignments.deadline
    """)

    assignments_list = cursor.fetchall()

    connection.close()

    return render_template(
        "assignments.html",
        courses=courses_list,
        assignments=assignments_list
    )


@app.route("/assignment/<int:assignment_id>/complete")
@login_required
def complete_assignment(assignment_id):

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE assignments
        SET completed = 1
        WHERE id = ?
    """, (assignment_id,))

    connection.commit()
    connection.close()

    return redirect("/assignments")


@app.route("/exams", methods=["GET", "POST"])
@login_required
def exams():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        course_id = request.form["course_id"]
        exam_date = request.form["exam_date"].strip()
        exam_time = request.form["exam_time"].strip()
        venue = request.form["venue"].strip()

        try:
            date.fromisoformat(exam_date)
        except ValueError:
            connection.close()
            return "Invalid exam date."

        cursor.execute("""
            INSERT INTO exams
            (course_id, exam_date, exam_time, venue)
            VALUES (?, ?, ?, ?)
        """, (
            course_id,
            exam_date,
            exam_time,
            venue
        ))

        connection.commit()

    cursor.execute("""
        SELECT *
        FROM courses
        ORDER BY course_code
    """)

    courses_list = cursor.fetchall()

    cursor.execute("""
        SELECT
            exams.id,
            exams.exam_date,
            exams.exam_time,
            exams.venue,
            courses.course_code,
            courses.course_name
        FROM exams
        JOIN courses
        ON exams.course_id = courses.id
        ORDER BY exams.exam_date, exams.exam_time
    """)

    exams_list = cursor.fetchall()

    connection.close()

    return render_template(
        "exams.html",
        courses=courses_list,
        exams=exams_list
    )


@app.route("/gpa", methods=["GET", "POST"])
@login_required
def gpa():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        course_id = request.form["course_id"]
        grade = request.form["grade"].upper().strip()

        valid_grades = ["A", "B", "C", "D", "E", "F"]

        if grade not in valid_grades:
            connection.close()
            return "Grade must be A, B, C, D, E or F."

        cursor.execute("""
            INSERT INTO grades
            (course_id, grade)
            VALUES (?, ?)
        """, (
            course_id,
            grade
        ))

        connection.commit()

    cursor.execute("""
        SELECT *
        FROM courses
        ORDER BY course_code
    """)

    courses_list = cursor.fetchall()

    cursor.execute("""
        SELECT
            grades.id,
            grades.grade,
            courses.course_code,
            courses.course_name,
            courses.units
        FROM grades
        JOIN courses
        ON grades.course_id = courses.id
        ORDER BY grades.id DESC
    """)

    grades_list = cursor.fetchall()

    grade_points = {
        "A": 5,
        "B": 4,
        "C": 3,
        "D": 2,
        "E": 1,
        "F": 0
    }

    total_points = 0
    total_units = 0

    for row in grades_list:

        grade = row["grade"]
        units = row["units"]

        total_points += grade_points[grade] * units
        total_units += units

    if total_units > 0:
        calculated_gpa = round(
            total_points / total_units,
            2
        )
    else:
        calculated_gpa = 0

    connection.close()

    return render_template(
        "gpa.html",
        courses=courses_list,
        grades=grades_list,
        gpa=calculated_gpa
    )


@app.route("/analytics")
@login_required
def analytics():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM courses")
    total_courses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM study_sessions")
    total_sessions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assignments")
    total_assignments = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM assignments
        WHERE completed = 1
    """)
    completed_assignments = cursor.fetchone()[0]

    pending_assignments = (
        total_assignments - completed_assignments
    )

    if total_assignments > 0:
        assignment_progress = round(
            (completed_assignments / total_assignments) * 100
        )
    else:
        assignment_progress = 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM exams
        WHERE exam_date >= ?
    """, (date.today().isoformat(),))

    upcoming_exams = cursor.fetchone()[0]

    cursor.execute("""
        SELECT courses.units, grades.grade
        FROM grades
        JOIN courses
        ON grades.course_id = courses.id
    """)

    grades = cursor.fetchall()

    grade_points = {
        "A": 5,
        "B": 4,
        "C": 3,
        "D": 2,
        "E": 1,
        "F": 0
    }

    total_points = 0
    total_units = 0

    for row in grades:

        grade = row["grade"].upper()
        units = row["units"]

        if grade in grade_points:
            total_points += (
                grade_points[grade] * units
            )
            total_units += units

    if total_units > 0:
        calculated_gpa = round(
            total_points / total_units,
            2
        )
    else:
        calculated_gpa = 0

    connection.close()

    return render_template(
        "analytics.html",
        total_courses=total_courses,
        total_sessions=total_sessions,
        total_assignments=total_assignments,
        completed_assignments=completed_assignments,
        pending_assignments=pending_assignments,
        assignment_progress=assignment_progress,
        upcoming_exams=upcoming_exams,
        gpa=calculated_gpa
    )


# ============================================================
# SEMESTER MANAGEMENT
# ============================================================

@app.route("/semesters", methods=["GET", "POST"])
def semesters():

    connection = get_db()
    cursor = connection.cursor()

    if request.method == "POST":

        name = request.form["name"].strip()
        academic_year = request.form["academic_year"].strip()
        term = request.form["term"].strip()

        if not name or not academic_year or not term:
            connection.close()
            return "Semester name, academic year and term are required."

        cursor.execute("""
            INSERT INTO semesters
            (name, academic_year, term, is_current)
            VALUES (?, ?, ?, 0)
        """, (
            name,
            academic_year,
            term
        ))

        connection.commit()

    cursor.execute("""
        SELECT *
        FROM semesters
        ORDER BY id DESC
    """)

    semester_list = cursor.fetchall()

    connection.close()

    return render_template(
        "semesters.html",
        semesters=semester_list
    )


@app.route("/semester/<int:semester_id>/current")
def set_current_semester(semester_id):

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE semesters
        SET is_current = 0
    """)

    cursor.execute("""
        UPDATE semesters
        SET is_current = 1
        WHERE id = ?
    """, (semester_id,))

    connection.commit()
    connection.close()

    return redirect("/semesters")


# ============================================================
# COURSE EDIT
# ============================================================

@app.route("/course/<int:course_id>/edit", methods=["GET", "POST"])
def edit_course(course_id):

    connection = get_db()
    cursor = connection.cursor()

    # Get the course
    cursor.execute("""
        SELECT *
        FROM courses
        WHERE id = ?
    """, (course_id,))

    course = cursor.fetchone()

    if course is None:
        connection.close()
        return "Course not found.", 404

    # Get all semesters
    cursor.execute("""
        SELECT id, name, academic_year
        FROM semesters
        ORDER BY id
    """)

    semesters = cursor.fetchall()

    if request.method == "POST":

        course_code = request.form.get("course_code", "").strip()
        course_name = request.form.get("course_name", "").strip()
        units_text = request.form.get("units", "").strip()
        semester_id = request.form.get("semester_id", "").strip()

        if not course_code or not course_name:
            connection.close()
            return "Course code and course name are required.", 400

        try:
            units = int(units_text)
        except ValueError:
            connection.close()
            return "Units must be a number.", 400

        if units < 1 or units > 10:
            connection.close()
            return "Units must be between 1 and 10.", 400

        if semester_id:
            try:
                semester_id = int(semester_id)
            except ValueError:
                connection.close()
                return "Invalid semester.", 400
        else:
            semester_id = None

        cursor.execute("""
            UPDATE courses
            SET course_code = ?,
                course_name = ?,
                units = ?,
                semester_id = ?
            WHERE id = ?
        """, (
            course_code,
            course_name,
            units,
            semester_id,
            course_id
        ))

        connection.commit()
        connection.close()

        return redirect("/courses")

    connection.close()

    return render_template(
        "edit_course.html",
        course=course,
        semesters=semesters
    )
# ============================================================
# COURSE DELETE
# ============================================================

@app.route("/course/<int:course_id>/delete", methods=["POST"])
def delete_course(course_id):

    connection = get_db()
    cursor = connection.cursor()

    # Check whether the course has study sessions
    cursor.execute("""
        SELECT COUNT(*)
        FROM study_sessions
        WHERE course_id = ?
    """, (course_id,))

    study_sessions = cursor.fetchone()[0]

    # Check whether the course has assignments
    cursor.execute("""
        SELECT COUNT(*)
        FROM assignments
        WHERE course_id = ?
    """, (course_id,))

    assignments_count = cursor.fetchone()[0]

    # Check whether the course has exams
    cursor.execute("""
        SELECT COUNT(*)
        FROM exams
        WHERE course_id = ?
    """, (course_id,))

    exams_count = cursor.fetchone()[0]

    # Check whether the course has grades
    cursor.execute("""
        SELECT COUNT(*)
        FROM grades
        WHERE course_id = ?
    """, (course_id,))

    grades_count = cursor.fetchone()[0]

    if (
        study_sessions > 0
        or assignments_count > 0
        or exams_count > 0
        or grades_count > 0
    ):

        connection.close()

        return """
        <h2>Cannot Delete Course</h2>

        <p>
        This course has related academic records.
        </p>

        <p>
        Please remove or update its related records first.
        </p>

        <a href="/courses">
            ← Back to Courses
        </a>
        """

    cursor.execute("""
        DELETE FROM courses
        WHERE id = ?
    """, (course_id,))

    connection.commit()
    connection.close()

    return redirect("/courses")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
