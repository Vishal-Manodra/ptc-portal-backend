# routes/tasks.py
# Task management — the to-do list for the CA firm.
# Each task belongs to a client and can be assigned to an employee.
#
#   GET    /tasks                → list tasks (filtered by role)
#   POST   /tasks                → create a task
#   PATCH  /tasks/{id}           → update status or assignment
#   DELETE /tasks/{id}           → delete a task

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import date

from database import get_db
from models import Task, Client, User
from schemas import TaskCreate, TaskOut
from auth import admin_or_employee, admin_only

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ── LIST TASKS ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[TaskOut])
def list_tasks(
    client_id: int = None,                       # filter by client
    status: str = None,                          # filter by status
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """
    Returns tasks.
    - Admin: sees all tasks across all clients
    - Employee: sees only tasks assigned to them
    Optional filters: ?client_id=3 or ?status=pending or both
    """
    query = db.query(Task).options(
        joinedload(Task.assignee),
        joinedload(Task.client),
    )

    if current_user.role == "employee":
        query = query.filter(Task.assigned_to == current_user.id)
        if client_id:
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client or client.assigned_employee_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not your assigned client")

    if client_id:
        query = query.filter(Task.client_id == client_id)

    if status in ("pending", "done", "overdue"):
        query = query.filter(Task.status == status)

    return query.order_by(Task.due_date.asc().nullslast()).all()


# ── CREATE TASK ───────────────────────────────────────────────────────────────

@router.post("", response_model=TaskOut)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """
    Creates a new task for a client.
    Admin can assign to any employee.
    Employee can only create tasks assigned to themselves.
    """
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if current_user.role == "employee":
        if client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client")
        if data.assigned_to != current_user.id:
            raise HTTPException(status_code=403, detail="Employees can only assign tasks to themselves")

    # Auto-mark as overdue if due date is in the past
    task_status = "pending"
    if data.due_date and data.due_date < date.today():
        task_status = "overdue"

    task = Task(
        client_id=data.client_id,
        title=data.title,
        due_date=data.due_date,
        assigned_to=data.assigned_to,
        status=task_status,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return db.query(Task).options(
        joinedload(Task.assignee),
        joinedload(Task.client),
    ).filter(Task.id == task.id).first()


# ── UPDATE TASK ───────────────────────────────────────────────────────────────

@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    status: str = None,                          # ?status=done
    assigned_to: int = None,                     # ?assigned_to=2
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    """
    Updates a task's status or reassigns it to another employee.
    Employee marks their own task as done.
    Admin can reassign tasks between employees.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "employee":
        if task.assigned_to != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned task")
        client = db.query(Client).filter(Client.id == task.client_id).first()
        if not client or client.assigned_employee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your assigned client")

    if status:
        if status not in ("pending", "done", "overdue"):
            raise HTTPException(status_code=400, detail="Invalid status")
        task.status = status

    if assigned_to is not None:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can reassign tasks")
        emp = db.query(User).filter(User.id == assigned_to).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        task.assigned_to = assigned_to

    db.commit()
    db.refresh(task)

    return db.query(Task).options(
        joinedload(Task.assignee),
        joinedload(Task.client),
    ).filter(Task.id == task.id).first()


# ── DELETE TASK ───────────────────────────────────────────────────────────────

@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}