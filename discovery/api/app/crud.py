from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from sqlalchemy import select, delete
from . import models, schemas

# ===================== WORKFLOWS =====================
async def create_workflow(db: AsyncSession, wf: schemas.WorkflowCreate):
    wf_id = uuid4()
    workflow = models.DiscoveryWorkflow(id=wf_id, name=wf.name, mode=wf.mode)
    db.add(workflow)
    await db.flush()
    for s in wf.steps:
        step = models.DiscoveryStep(
            id=uuid4(),
            workflow_id=wf_id,
            name=s.name,
            order=s.order,
            max_visits=s.max_visits,
        )
        db.add(step)
    await db.commit()
    await db.refresh(workflow)
    return workflow

async def get_workflow(db: AsyncSession, wf_id):
    stmt = select(models.DiscoveryWorkflow).where(models.DiscoveryWorkflow.id == wf_id)
    return (await db.execute(stmt)).scalar_one_or_none()

async def list_workflows(db: AsyncSession):
    stmt = select(models.DiscoveryWorkflow)
    return (await db.execute(stmt)).scalars().all()

async def update_workflow(db: AsyncSession, wf_id, wf_upd: schemas.WorkflowUpdate):
    workflow = await db.get(models.DiscoveryWorkflow, wf_id)
    if not workflow:
        return None
    for k, v in wf_upd.model_dump(exclude_unset=True).items():
        setattr(workflow, k, v)
    await db.commit()
    await db.refresh(workflow)
    return workflow

async def delete_workflow(db: AsyncSession, wf_id):
    workflow = await db.get(models.DiscoveryWorkflow, wf_id)
    if not workflow:
        return False
    await db.delete(workflow)
    await db.commit()
    return True

# =======================  STEPS  ======================
async def create_step(db: AsyncSession, wf_id, s: schemas.StepCreate):
    step = models.DiscoveryStep(
        id=uuid4(),
        workflow_id=wf_id,
        name=s.name,
        order=s.order,
        max_visits=s.max_visits,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step

async def get_step(db: AsyncSession, step_id):
    return await db.get(models.DiscoveryStep, step_id)

async def list_steps(db: AsyncSession, wf_id):
    stmt = select(models.DiscoveryStep).where(models.DiscoveryStep.workflow_id == wf_id)
    return (await db.execute(stmt)).scalars().all()

async def update_step(db: AsyncSession, step_id, s_upd: schemas.StepUpdate):
    step = await db.get(models.DiscoveryStep, step_id)
    if not step:
        return None
    for k, v in s_upd.model_dump(exclude_unset=True).items():
        setattr(step, k, v)
    await db.commit()
    await db.refresh(step)
    return step

async def delete_step(db: AsyncSession, step_id):
    step = await db.get(models.DiscoveryStep, step_id)
    if not step:
        return False
    await db.delete(step)
    await db.commit()
    return True