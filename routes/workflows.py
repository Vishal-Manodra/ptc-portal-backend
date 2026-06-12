from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime ,timedelta
from database import get_db
from models import (
    WorkflowTaskComment,
    WorkflowTemplate,
    WorkflowTemplateStep,
    User,
    Client,
    ClientWorkflow,
    WorkflowTask,
    ActivityLog,
)
from auth import admin_or_employee
class WorkflowAssignmentRequest(BaseModel):
    manager_id: int
    employee_id: int

class TaskCommentRequest(BaseModel):
    comment: str

class AssignTaskRequest(BaseModel):
    user_id: int

class TransferTaskRequest(BaseModel):
    employee_id: int

router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
)
# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def recalculate_workflow_progress(workflow_id: int, db: Session):
    total_tasks = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.workflow_id == workflow_id
        )
        .count()
    )
    completed_tasks = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.workflow_id == workflow_id,
            WorkflowTask.status == "completed"
        )
        .count()
    )
    if total_tasks == 0:
        return 0
    return int(
        (completed_tasks / total_tasks) * 100
    )

@router.post("/templates")
def create_template(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    template = WorkflowTemplate(
        name=data["name"],
        description=data.get("description"),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template

@router.post("/templates/{template_id}/steps")
def create_template_step(
    template_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    template = (
        db.query(WorkflowTemplate)
        .filter(WorkflowTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(
            status_code=404,
            detail="Template not found",
        )
    step = WorkflowTemplateStep(
        template_id=template_id,
        name=data["name"],
        sequence=data["sequence"],
        default_role=data["default_role"],
        approval_required=data.get(
            "approval_required",
            False,
        ),
        estimated_hours=data.get(
            "estimated_hours",
            1,
        ),
    )

    db.add(step)
    db.commit()
    db.refresh(step)

    return step

@router.get("/templates")
def get_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    return (
        db.query(WorkflowTemplate)
        .all()
    )

@router.post("/clients/{client_id}/assign/{template_id}")
def assign_workflow_to_client(
    client_id: int,
    template_id: int,
    data: WorkflowAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    client = (
        db.query(Client)
        .filter(Client.id == client_id)
        .first()
    )

    if not client:
        raise HTTPException(
            status_code=404,
            detail="Client not found",
        )

    template = (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.id == template_id
        )
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=404,
            detail="Template not found",
        )
    workflow = ClientWorkflow(
        client_id=client_id,
        template_id=template_id,
        assigned_manager_id=data.manager_id,
        assigned_employee_id=data.employee_id,
        status="active",
        progress_percent=0,
        current_step=1,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    steps = (
        db.query(WorkflowTemplateStep)
        .filter(
            WorkflowTemplateStep.template_id
            == template_id
        )
        .order_by(
            WorkflowTemplateStep.sequence
        )
        .all()
    )
    for step in steps:

        assigned_user_id = None

        if step.default_role == "employee":
            assigned_user_id = data.employee_id

        elif step.default_role == "manager":
            assigned_user_id = data.manager_id
        
        status = (
            "in_progress"
            if step.sequence == 1
            else "pending"
        )

        task = WorkflowTask(
            workflow_id=workflow.id,
            template_step_id=step.id,
            assigned_user_id=assigned_user_id,
            status=status,
        )

        db.add(task)
    db.add(
        ActivityLog(
            client_id=client_id,
            workflow_id=workflow.id,
            user_id=current_user.id,
            action="WORKFLOW_ASSIGNED",
            description=(
                f"Assigned workflow '{template.name}' "
                f"to client '{client.business_name}'"
            ),
        )
    )
    db.commit()
    return {
        "message": "Workflow assigned successfully",
        "workflow_id": workflow.id,
        "client_id": client_id,
        "template_id": template_id,
        "manager_id": data.manager_id,
        "employee_id": data.employee_id,
    }


@router.get("/client-workflows")
def get_client_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    if current_user.role == "admin":
        workflows = db.query(ClientWorkflow).all()

    elif current_user.role == "manager":
        workflows = (
            db.query(ClientWorkflow)
            .filter(
                ClientWorkflow.assigned_manager_id
                == current_user.id
            )
            .all()
        )

    else:
        workflows = (
            db.query(ClientWorkflow)
            .filter(
                ClientWorkflow.assigned_employee_id
                == current_user.id
            )
            .all()
        )

    result = []

    for workflow in workflows:

        tasks = (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.workflow_id == workflow.id
            )
            .order_by(WorkflowTask.id)
            .all()
        )

        task_data = []

        for task in tasks:
            step = task.template_step

            task_data.append({
                "task_id": task.id,
                "name": step.name,
                "status": task.status,
                "assigned_user_id": task.assigned_user_id,
                "assigned_user":
                    task.assigned_user.name
                    if task.assigned_user
                    else None,
                "completed_at": task.completed_at,
                "original_assignee":
                    task.original_assignee.name
                    if task.original_assignee
                    else None,
                "transferred_to":
                    task.transferred_to.name
                    if task.transferred_to
                    else None,
                "transfer_approved":
                    task.transfer_approved,
                "transferred_completed":
                    task.transferred_completed,
            })

        result.append({
            "workflow_id": workflow.id,
            "client_id": workflow.client_id,
            "client_name": workflow.client.business_name,
            "workflow_name": workflow.template.name,
            "progress_percent": workflow.progress_percent,
            "status": workflow.status,
            "tasks": task_data,
        })
    print("WORKFLOWS FOUND:", len(workflows))
    print("RESULT:", result)
    return result

@router.get("/client/{client_id}")
def get_client_workflows_for_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    workflows = (
        db.query(ClientWorkflow)
        .filter(
            ClientWorkflow.client_id == client_id
        )
        .all()
    )

    result = []

    for workflow in workflows:
        tasks = (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.workflow_id == workflow.id
            )
            .order_by(
                WorkflowTask.id
            )
            .all()
        )
        result.append({
            "workflow_id": workflow.id,
            "workflow_name": workflow.template.name,
            "progress_percent": workflow.progress_percent,
            "status": workflow.status,
            "tasks": [
                {
                    "task_id": t.id,
                    "name": t.template_step.name,
                    "status": t.status,
                    "assigned_user":
                        t.assigned_user.name
                        if t.assigned_user
                        else None,
                }
                for t in tasks
            ]
        })
    return result

@router.get("/dashboard")
def workflow_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    return {
        "total_workflows": db.query(ClientWorkflow).count(),
        "active_workflows": (
            db.query(ClientWorkflow)
            .filter(ClientWorkflow.status == "active")
            .count()
        ),
        "completed_tasks": (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.status == "completed"
            )
            .count()
        ),
        "pending_tasks": (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.status.in_(
                    [
                        "pending",
                        "in_progress",
                        "awaiting_approval",
                    ]
                )
            )
            .count()
        ),
        "pending_approvals": (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.status
                == "awaiting_approval"
            )
            .count()
        ),
    }

@router.get("/employees/work-summary")
def employee_work_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    employees = (
        db.query(User)
        .filter(User.role.in_(["employee", "manager"]))
        .all()
    )

    result = []

    for emp in employees:
        total_tasks = (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.assigned_user_id == emp.id
            )
            .count()
        )

        completed_tasks = (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.assigned_user_id == emp.id,
                WorkflowTask.status == "completed"
            )
            .count()
        )

        pending_tasks = (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.assigned_user_id == emp.id,
                WorkflowTask.status != "completed"
            )
            .count()
        )

        completion_rate = (
            round((completed_tasks / total_tasks) * 100)
            if total_tasks > 0
            else 0
        )

        result.append({
            "employee_id": emp.id,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "completion_rate": completion_rate,
        })

    return result

@router.get("/my-tasks")
def get_my_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    tasks = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.assigned_user_id == current_user.id
        )
        .all()
    )
    result = []
    for task in tasks:
        workflow = task.workflow
        client = workflow.client
        step = task.template_step
        result.append({
            "task_id": task.id,
            "client_id": client.id,
            "client_name": client.business_name,
            "workflow_id": workflow.id,
            "workflow_name": workflow.template.name,
            "step_name": step.name,
            "status": task.status,
            "approved": task.approved,
            "priority": task.priority,
            "due_date": task.due_date,
            "transferred_to":
                task.transferred_to.name
                if task.transferred_to
                else None,
            "transferred_by":
                task.transferred_by.name
                if task.transferred_by
                else None,
            "original_assignee_id":
                task.original_assignee_id,
            "transferred_completed":
                task.transferred_completed,
        })
    return result

@router.get("/pending-approvals")
def get_pending_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    tasks = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.status
            == "awaiting_approval"
        )
        .all()
    )
    result = []
    for task in tasks:
        result.append({
            "task_id": task.id,
            "client_name": task.workflow.client.business_name,
            "workflow_name": task.workflow.template.name,
            "step_name": task.template_step.name,
            "assigned_user": (
                task.assigned_user.name
                if task.assigned_user
                else None
            ),
        })
    return result



@router.get("/activity-logs")
def get_activity_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    logs = (
        db.query(ActivityLog)
        .order_by(
            ActivityLog.created_at.desc()
        )
        .limit(100)
        .all()
    )
    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "action": log.action,
            "description": log.description,
            "client_id": log.client_id,
            "workflow_id": log.workflow_id,
            "task_id": log.task_id,
            "user_id": log.user_id,
            "created_at": log.created_at,
        })
    return result

@router.get("/{workflow_id}")
def get_workflow_details(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    workflow = (
        db.query(ClientWorkflow)
        .filter(
            ClientWorkflow.id == workflow_id
        )
        .first()
    )
    if not workflow:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found",
        )
    tasks = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.workflow_id
            == workflow_id
        )
        .all()
    )
    return {
        "workflow": workflow,
        "tasks": tasks,
    }

@router.patch("/tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    task = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    workflow = task.workflow

    # Transferred task requires original owner approval
    if task.original_assignee_id:
        task.transferred_completed = True
        task.status = "awaiting_approval"

    # Step requires manager approval
    elif task.template_step.approval_required:
        task.status = "awaiting_approval"

    # Normal task
    else:
        task.status = "completed"
        task.approved = True

        workflow.progress_percent = (
            recalculate_workflow_progress(
                workflow.id,
                db,
            )
        )

        next_task = (
            db.query(WorkflowTask)
            .filter(
                WorkflowTask.workflow_id == workflow.id,
                WorkflowTask.status == "pending",
            )
            .order_by(WorkflowTask.id)
            .first()
        )

        if (
            not task.template_step.approval_required
            and not task.original_assignee_id
        ):
            if next_task:
                next_task.status = "in_progress"

    task.completed_at = datetime.utcnow() + timedelta(
        hours=5,
        minutes=30,
    )

    db.add(
        ActivityLog(
            client_id=workflow.client_id,
            workflow_id=workflow.id,
            task_id=task.id,
            user_id=current_user.id,
            action="TASK_SUBMITTED",
            description=f"Task {task.id} submitted",
        )
    )

    db.commit()

    return {
        "message": "Task completed"
    }

@router.patch("/tasks/{task_id}/approve-transfer")
def approve_transfer(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    task = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    if not task.original_assignee_id:
        raise HTTPException(
            status_code=400,
            detail="This task was not transferred",
        )

    if task.original_assignee_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only original assignee can approve",
        )

    workflow = task.workflow

    task.transfer_approved = True
    task.status = "completed"
    task.approved = True

    workflow.progress_percent = (
        recalculate_workflow_progress(
            workflow.id,
            db,
        )
    )

    next_task = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.workflow_id == workflow.id,
            WorkflowTask.status == "pending",
        )
        .order_by(WorkflowTask.id)
        .first()
    )

    if next_task:
        next_task.status = "in_progress"

    db.add(
        ActivityLog(
            client_id=workflow.client_id,
            workflow_id=workflow.id,
            task_id=task.id,
            user_id=current_user.id,
            action="TRANSFER_APPROVED",
            description=(
                f"Transferred task {task.id} approved"
            ),
        )
    )

    db.commit()

    return {
        "message": "Transfer approved"
    }

@router.patch("/tasks/{task_id}/transfer")
def transfer_task(
    task_id: int,
    data: TransferTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    task = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    if not task.original_assignee_id:
        task.original_assignee_id = task.assigned_user_id

    task.transferred_to_id = data.employee_id
    task.transferred_by_id = current_user.id

    task.assigned_user_id = data.employee_id

    task.transferred_completed = False
    task.transfer_approved = False

    db.commit()

    return {
        "message": "Task transferred"
    }

@router.patch("/tasks/{task_id}/transfer-complete")
def transfer_complete(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    task = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.id == task_id
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    task.transferred_completed = True

    db.add(
        ActivityLog(
            client_id=task.workflow.client_id,
            workflow_id=task.workflow_id,
            task_id=task.id,
            user_id=current_user.id,
            action="TRANSFER_WORK_DONE",
            description=(
                f"{current_user.name} completed transferred work"
            ),
        )
    )

    db.commit()

    return {
        "message": "Transferred work completed"
    }

@router.patch("/tasks/{task_id}/approve")
def approve_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    task = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )
    task.status = "completed"
    task.approved = True

    if task.original_assignee_id:
        task.transfer_approved = True

    db.flush()
    workflow = (
        db.query(ClientWorkflow)
        .filter(ClientWorkflow.id == task.workflow_id)
        .first()
    )
    workflow.progress_percent = (
    recalculate_workflow_progress(
        workflow.id,
        db,
    )
    )
    db.add(
        ActivityLog(
            client_id=workflow.client_id,
            workflow_id=workflow.id,
            task_id=task.id,
            user_id=current_user.id,
            action="TASK_APPROVED",
            description=f"Task {task.id} approved",
        )
    )
    next_task = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.workflow_id == workflow.id,
            WorkflowTask.status == "pending"
        )
        .order_by(WorkflowTask.id)
        .first()
    )
    if next_task:
        next_task.status = "in_progress"
    db.commit()
    return {
        "message": "Task approved",
        "progress": workflow.progress_percent,
    }

@router.post("/tasks/{task_id}/comments")
def add_comment(
    task_id: int,
    data: TaskCommentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    task = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )
    comment = WorkflowTaskComment(
        task_id=task_id,
        user_id=current_user.id,
        comment=data.comment,
    )
    db.add(comment)
    db.add(
        ActivityLog(
            client_id=task.workflow.client_id,
            workflow_id=task.workflow_id,
            task_id=task.id,
            user_id=current_user.id,
            action="COMMENT_ADDED",
            description=data.comment,
        )
    )
    db.commit()
    return {
        "message": "Comment added"
    }


@router.get("/tasks/{task_id}/comments")
def get_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    comments = (
        db.query(WorkflowTaskComment)
        .filter(
            WorkflowTaskComment.task_id == task_id
        )
        .order_by(
            WorkflowTaskComment.created_at.desc()
        )
        .all()
    )
    return comments

@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    workflow = (
        db.query(ClientWorkflow)
        .filter(ClientWorkflow.id == workflow_id)
        .first()
    )

    if not workflow:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found"
        )

    # Get all task ids for this workflow
    task_ids = [
        t.id
        for t in db.query(WorkflowTask)
        .filter(
            WorkflowTask.workflow_id == workflow_id
        )
        .all()
    ]

    # Delete logs linked to tasks
    if task_ids:
        db.query(ActivityLog).filter(
            ActivityLog.task_id.in_(task_ids)
        ).delete(synchronize_session=False)

    # Delete logs linked directly to workflow
    db.query(ActivityLog).filter(
        ActivityLog.workflow_id == workflow_id
    ).delete(synchronize_session=False)

    # Delete workflow tasks
    db.query(WorkflowTask).filter(
        WorkflowTask.workflow_id == workflow_id
    ).delete(synchronize_session=False)

    # Delete workflow
    db.delete(workflow)

    db.commit()

    return {
        "message": "Workflow deleted"
    }

@router.patch("/tasks/{task_id}/assign")
def assign_task(
    task_id: int,
    data: AssignTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_or_employee),
):
    print("TASK ID:", task_id)
    print("NEW USER:", data.user_id)

    task = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    task.assigned_user_id = data.user_id

    db.commit()

    db.refresh(task)

    print("SAVED USER:", task.assigned_user_id)

    return {
        "message": "Task reassigned"
    }