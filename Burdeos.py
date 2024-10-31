from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from datetime import date


conn = sqlite3.connect('study_planner.db', check_same_thread=False)
cursor = conn.cursor()


cursor.execute('''
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    due_date TEXT,
    is_completed INTEGER DEFAULT 0,
    FOREIGN KEY (subject_id) REFERENCES subjects (id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS study_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT
)
''')

conn.commit()


sample_subjects = ["Mathematics", "Science", "History", "Geography", "Art"]
for subject in sample_subjects:
    try:
        cursor.execute("INSERT INTO subjects (name) VALUES (?)", (subject,))
    except sqlite3.IntegrityError:
        pass
conn.commit()


sample_tasks = [
    (1, "Math Homework", "2024-09-20", 0),
    (2, "Science Project", "2024-09-21", 0),
    (3, "History Essay", "2024-09-22", 1),
    (4, "Geography Quiz", "2024-09-23", 0),
    (5, "Art Assignment", "2024-09-24", 1),
]
cursor.executemany("INSERT OR IGNORE INTO tasks (subject_id, title, due_date, is_completed) VALUES (?, ?, ?, ?)", sample_tasks)
conn.commit()


app = FastAPI()


class Subject(BaseModel):
    name: str

class Task(BaseModel):
    subject_name: str
    title: str
    due_date: Optional[str] = None
    is_completed: Optional[str] = "incomplete" 

class StudyPlan(BaseModel):
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class SubjectWithTaskCount(BaseModel):
    id: int
    name: str
    task_count: int



@app.post("/subjects/", status_code=status.HTTP_201_CREATED)
def create_subject(subject: Subject):

    cursor.execute("SELECT id FROM subjects WHERE name=?", (subject.name,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Subject already exists")

    cursor.execute("INSERT INTO subjects (name) VALUES (?)", (subject.name,))
    conn.commit()
    return {"message": "Subject created successfully"}


@app.get("/subjects/", response_model=List[Subject])
def get_subjects():
    cursor.execute("SELECT id, name FROM subjects")
    rows = cursor.fetchall()
    return [{"id": row[0], "name": row[1]} for row in rows]


@app.post("/tasks/", status_code=status.HTTP_201_CREATED)
def create_task(task: Task):
    
    cursor.execute("SELECT id FROM subjects WHERE name=?", (task.subject_name,))
    subject = cursor.fetchone()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    subject_id = subject[0]

    is_completed = 1 if task.is_completed.lower() == "complete" else 0
    cursor.execute("INSERT INTO tasks (subject_id, title, due_date, is_completed) VALUES (?, ?, ?, ?)",
                   (subject_id, task.title, task.due_date, is_completed))
    conn.commit()
    return {"message": "Task created successfully"}


@app.get("/subjects/{subject_name}/tasks/", response_model=List[Task])
def get_tasks_for_subject(subject_name: str):

    cursor.execute("SELECT id FROM subjects WHERE name=?", (subject_name,))
    subject = cursor.fetchone()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    subject_id = subject[0]
    cursor.execute("SELECT id, subject_id, title, due_date, is_completed FROM tasks WHERE subject_id=?", (subject_id,))
    rows = cursor.fetchall()
    return [
        {"id": row[0], "subject_name": subject_name, "title": row[2], "due_date": row[3], "is_completed": "complete" if row[4] == 1 else "incomplete"}
        for row in rows
    ]


@app.put("/tasks/{task_id}/complete/")
def complete_task(task_id: int):
    cursor.execute("UPDATE tasks SET is_completed=1 WHERE id=?", (task_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    conn.commit()
    return {"message": "Task marked as complete"}


@app.get("/tasks/", response_model=List[Task])
def get_all_tasks():
    cursor.execute("""
        SELECT tasks.id, subjects.name AS subject_name, tasks.title, tasks.due_date, tasks.is_completed
        FROM tasks
        JOIN subjects ON tasks.subject_id = subjects.id
    """)
    rows = cursor.fetchall()
    return [
        {"id": row[0], "subject_name": row[1], "title": row[2], "due_date": row[3], "is_completed": "complete" if row[4] == 1 else "incomplete"}
        for row in rows
    ]


@app.put("/tasks/{task_id}/")
def update_task(task_id: int, task: Task):
    
    cursor.execute("SELECT id FROM subjects WHERE name=?", (task.subject_name,))
    subject = cursor.fetchone()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    subject_id = subject[0]
    
    is_completed = 1 if task.is_completed.lower() == "complete" else 0
    cursor.execute("""
        UPDATE tasks
        SET subject_id=?, title=?, due_date=?, is_completed=?
        WHERE id=?
    """, (subject_id, task.title, task.due_date, is_completed, task_id))
    
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    conn.commit()
    return {"message": "Task updated successfully"}



@app.delete("/tasks/{task_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    conn.commit()
    return {"message": "Task deleted successfully"}


@app.post("/study_plans/", status_code=status.HTTP_201_CREATED)
def create_study_plan(study_plan: StudyPlan):
    cursor.execute("INSERT INTO study_plans (name, start_date, end_date) VALUES (?, ?, ?)",
                   (study_plan.name, study_plan.start_date, study_plan.end_date))
    conn.commit()
    return {"message": "Study plan created successfully"}


@app.get("/study_plans/", response_model=List[StudyPlan])
def get_all_study_plans():
    cursor.execute("SELECT id, name, start_date, end_date FROM study_plans")
    rows = cursor.fetchall()
    return [{"id": row[0], "name": row[1], "start_date": row[2], "end_date": row[3]} for row in rows]


@app.put("/study_plans/{plan_id}/")
def update_study_plan(plan_id: int, study_plan: StudyPlan):
    cursor.execute("""
        UPDATE study_plans
        SET name=?, start_date=?, end_date=?
        WHERE id=?
    """, (study_plan.name, study_plan.start_date, study_plan.end_date, plan_id))
    
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Study plan not found")
    
    conn.commit()
    return {"message": "Study plan updated successfully"}


@app.put("/tasks/{task_id}/incomplete/")
def mark_task_incomplete(task_id: int):
    cursor.execute("UPDATE tasks SET is_completed=0 WHERE id=?", (task_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    conn.commit()
    return {"message": "Task marked as incomplete"}


@app.delete("/subjects/{subject_name}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(subject_name: str):
    cursor.execute("DELETE FROM subjects WHERE name=?", (subject_name,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Subject not found")
    conn.commit()
    return {"message": "Subject deleted successfully"}


@app.get("/study_plans/name/{plan_name}/")
def get_study_plan_by_name(plan_name: str):
    cursor.execute("SELECT id, name, start_date, end_date FROM study_plans WHERE name=?", (plan_name,))
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "name": row[1], "start_date": row[2], "end_date": row[3]}
    else:
        raise HTTPException(status_code=404, detail="Study plan not found")


@app.get("/study_plans/date_range/")
def get_study_plans_by_date_range(start_date: str, end_date: str):
    cursor.execute("""
        SELECT id, name, start_date, end_date
        FROM study_plans
        WHERE (start_date >= ? AND end_date <= ?)
    """, (start_date, end_date))
    
    rows = cursor.fetchall()
    return [{"id": row[0], "name": row[1], "start_date": row[2], "end_date": row[3]} for row in rows]


@app.get("/study_plans/{plan_id}/")
def get_study_plan_by_id(plan_id: int):
    cursor.execute("SELECT id, name, start_date, end_date FROM study_plans WHERE id=?", (plan_id,))
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "name": row[1], "start_date": row[2], "end_date": row[3]}
    else:
        raise HTTPException(status_code=404, detail="Study plan not found")


@app.put("/subjects/{subject_name}/")
def update_subject(subject_name: str, subject: Subject):
    cursor.execute("UPDATE subjects SET name=? WHERE name=?", (subject.name, subject_name))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Subject not found")
    conn.commit()
    return {"message": "Subject updated successfully"}


@app.get("/tasks/due_today/", response_model=List[Task])
def get_tasks_due_today():
    today = date.today().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT tasks.id, subjects.name AS subject_name, tasks.title, tasks.due_date, tasks.is_completed
        FROM tasks
        JOIN subjects ON tasks.subject_id = subjects.id
        WHERE tasks.due_date=?
    """, (today,))
    rows = cursor.fetchall()
    return [
        {"id": row[0], "subject_name": row[1], "title": row[2], "due_date": row[3], "is_completed": "complete" if row[4] == 1 else "incomplete"}
        for row in rows
    ]


@app.delete("/study_plans/{plan_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_study_plan(plan_id: int):
    cursor.execute("DELETE FROM study_plans WHERE id=?", (plan_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Study plan not found")
    conn.commit()
    return {"message": "Study plan deleted successfully"}


@app.get("/subjects/task_count/", response_model=List[SubjectWithTaskCount])
def get_subjects_with_task_count():
    cursor.execute('''
        SELECT subjects.id, subjects.name, COUNT(tasks.id) as task_count
        FROM subjects
        LEFT JOIN tasks ON subjects.id = tasks.subject_id
        GROUP BY subjects.id
    ''')
    rows = cursor.fetchall()
    return [{"id": row[0], "name": row[1], "task_count": row[2]} for row in rows]