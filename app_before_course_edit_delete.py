from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import date

app = Flask(__name__)

DATABASE = "planner.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


@app.route("/")
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

        if not course_code or not course_name:
            connection.close()
            return "Course code and course name are required."

        if units < 1 or units > 10:
            connection.close()
            return "Units must be between 1 and 10."

        cursor.execute("""
            SELECT id
            FROM semesters
            WHERE is_current = 1
            LIMIT 1
        """)

        current_semester = cursor.fetchone()

        if current_semester:
            semester_id = current_semester[0]
        else:
            semester_id = None

        cursor.execute("""
            INSERT INTO courses
            (course_code, course_name, units, semester_id)
            VALUES (?, ?, ?, ?)
        """, (
            course_code,
            course_name,
            units,
            semester_id
        ))

        connection.commit()

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
        ORDER BY courses.id DESC
    """)

    courses_list = cursor.fetchall()

    connection.close()

    return render_template(
        "courses.html",
        courses=courses_list
    )


@app.route("/timetable", methods=["GET", "POST"])
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

        if not name or not academic_year:
            connection.close()
            return "Semester name and academic year are required."

        cursor.execute("""
            INSERT INTO semesters
            (name, academic_year, is_current)
            VALUES (?, ?, 0)
        """, (
            name,
            academic_year
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


if __name__ == "__main__":
    app.run(debug=True)
