from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GroupMember, Settlement, Expense, ExpenseSplit
from app.schemas import SettlementCreate, SettlementResponse
from app.deps import get_group_member

router = APIRouter(prefix="/groups", tags=["Settlements"])

@router.post("/{group_id}/settlements", response_model=SettlementResponse, status_code=status.HTTP_201_CREATED)
def create_settlement(
    group_id: int,
    settlement_in: SettlementCreate,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)
):
    if settlement_in.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if settlement_in.payee_id == membership.user_id:
        raise HTTPException(status_code=400, detail="Cannot settle with yourself")

    payee = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == settlement_in.payee_id
    ).first()
    if not payee:
        raise HTTPException(status_code=400, detail="Payee is not a member of this group")

    new_settlement = Settlement(
        group_id=group_id,
        payer_id=membership.user_id,
        payee_id=settlement_in.payee_id,
        amount=settlement_in.amount
    )
    db.add(new_settlement)
    db.commit()
    db.refresh(new_settlement)
    return new_settlement

@router.get("/{group_id}/settlements/suggested")
def get_suggested_settlements(
    group_id: int,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)
):
    member_ids = {m.user_id for m in db.query(GroupMember.user_id).filter(GroupMember.group_id == group_id).all()}
    balances = {user_id: 0 for user_id in member_ids}

    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    for exp in expenses:
        if exp.paid_by in member_ids:
            balances[exp.paid_by] += exp.amount

    splits = db.query(ExpenseSplit).join(Expense).filter(Expense.group_id == group_id).all()
    for split in splits:
        if split.user_id in member_ids:
            balances[split.user_id] -= split.amount
            
    settlements = db.query(Settlement).filter(Settlement.group_id == group_id).all()
    for s in settlements:
        if s.payer_id in member_ids: 
            balances[s.payer_id] += s.amount
        if s.payee_id in member_ids: 
            balances[s.payee_id] -= s.amount

    debtors = [{"id": k, "amount": -v} for k, v in balances.items() if v < 0]
    creditors = [{"id": k, "amount": v} for k, v in balances.items() if v > 0]
    
    suggestions = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        settle_amount = min(debtors[i]["amount"], creditors[j]["amount"])
        suggestions.append({
            "from": debtors[i]["id"],
            "to": creditors[j]["id"],
            "amount": settle_amount
        })
        debtors[i]["amount"] -= settle_amount
        creditors[j]["amount"] -= settle_amount
        
        if debtors[i]["amount"] == 0: 
            i += 1
        if creditors[j]["amount"] == 0: 
            j += 1

    return suggestions