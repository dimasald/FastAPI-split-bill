from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app.models import GroupMember, Expense, ExpenseSplit, User
from app.schemas import ExpenseCreate, ExpenseResponse, BalanceResponse
from app.deps import get_group_member

router = APIRouter(prefix="/groups", tags=["Expenses"])

@router.post("/{group_id}/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    group_id: int,
    expense_in: ExpenseCreate,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)
):
    if not expense_in.splits:
        raise HTTPException(status_code=400, detail="Splits cannot be empty")
        
    if expense_in.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    if expense_in.paid_by != membership.user_id:
        raise HTTPException(status_code=403, detail="You can only create expenses paid by yourself")

    requested_user_ids = [split.user_id for split in expense_in.splits]
    
    if len(requested_user_ids) != len(set(requested_user_ids)):
        raise HTTPException(status_code=400, detail="Duplicate user in splits")
        
    if any(split.amount <= 0 for split in expense_in.splits):
        raise HTTPException(status_code=400, detail="Split amount must be positive")

    total_splits = sum(split.amount for split in expense_in.splits)
    
    if total_splits != expense_in.amount:
        raise HTTPException(status_code=400, detail="Total split amount does not match expense amount")

    valid_members = db.query(GroupMember.user_id).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id.in_(requested_user_ids)
    ).all()
    
    valid_user_ids = {m.user_id for m in valid_members}
    
    if len(valid_user_ids) != len(set(requested_user_ids)):
        raise HTTPException(status_code=400, detail="One or more users are not members of this group")

    new_expense = Expense(
        description=expense_in.description,
        amount=expense_in.amount,
        paid_by=membership.user_id,
        group_id=group_id
    )
    
    db.add(new_expense)
    db.flush()

    db.add_all([
        ExpenseSplit(
            expense_id=new_expense.id,
            user_id=split.user_id,
            amount=split.amount
        )
        for split in expense_in.splits
    ])
    
    try:
        db.commit()
        db.refresh(new_expense)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save expense")
        
    return new_expense


@router.get("/{group_id}/balances", response_model=List[BalanceResponse])
def get_group_balances(
    group_id: int,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)
):
    member_ids = {
        m.user_id 
        for m in db.query(GroupMember.user_id).filter(GroupMember.group_id == group_id).all()
    }
    
    balances = {user_id: 0 for user_id in member_ids}

    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    for exp in expenses:
        if exp.paid_by in member_ids:
            balances[exp.paid_by] += exp.amount

    splits = (
        db.query(ExpenseSplit)
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .filter(Expense.group_id == group_id)
        .all()
    )
    for split in splits:
        if split.user_id in member_ids:
            balances[split.user_id] -= split.amount

    users = db.query(User).filter(User.id.in_(member_ids)).all()
    user_map = {u.id: u.email for u in users}

    result = []
    for user_id, balance in balances.items():
        result.append({
            "email": user_map[user_id],
            "balance": balance
        })

    return result


@router.get("/{group_id}/expenses", response_model=List[ExpenseResponse])
def get_group_expenses(
    group_id: int,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)
):
    expenses = (
        db.query(Expense)
        .options(joinedload(Expense.splits))
        .filter(Expense.group_id == group_id)
        .order_by(Expense.created_at.desc())
        .all()
    )
    return expenses