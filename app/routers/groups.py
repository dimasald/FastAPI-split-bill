from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import Group, GroupMember, User
from app.schemas import GroupCreate, GroupResponse, InviteMember, GroupMemberResponse
from app.deps import get_current_user, get_group_member


router = APIRouter(prefix="/groups", tags=["Groups"])

@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    group_in: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):

    new_group = Group(name=group_in.name)
    db.add(new_group)
    db.flush()
    
    new_member = GroupMember(
        group_id=new_group.id,
        user_id=current_user.id,
        role="admin"
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_group)
    
    return new_group


@router.get("", response_model=List[GroupResponse])
def get_my_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    groups = (
        db.query(Group)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .filter(GroupMember.user_id == current_user.id)
        .all()
    )
    return groups


@router.post("/{group_id}/invite")
def invite_member(
    group_id: int,
    user_invite: InviteMember,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)
):
    

    if membership.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only admin can invite members"
        )

    target_user = db.query(User).filter(User.email == user_invite.email).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )

    existing_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == target_user.id
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User already in group"
        )

    new_member = GroupMember(
        group_id=group_id,
        user_id=target_user.id,
        role="member"
    )
    try:
        db.add(new_member)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user already in group"
        )
    
    return {"message": f"Successfully invited {target_user.email}"}

@router.get("/{group_id}/members", response_model=List[GroupMemberResponse])
def get_members(
    group_id: int,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)):
    
    
    all_members = (
        db.query(GroupMember.user_id, User.email, GroupMember.role)
        .join(User, GroupMember.user_id == User.id)
        .filter(GroupMember.group_id == group_id)
        .all()
    )

    return all_members


@router.delete("/{group_id}/members/{user_id}")
def remove_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)
):
    if membership.role != "admin" and user_id != membership.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only admin can remove others"
        )

    target_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first()

    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Member not found"
        )

    if target_member.role == "admin":
        admin_count = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.role == "admin"
        ).count()
        
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Cannot leave group. You are the last admin. Promote someone else first."
            )    

    db.delete(target_member)
    db.commit()

    return {"message": "Member removed successfully"}

@router.patch("/{group_id}/members/{user_id}/promote")
def promote_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    membership: GroupMember = Depends(get_group_member)
):
    if membership.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Only admin can promote others"
            )

    target_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
        ).first()
    
    
    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Member not found"
        )
    
    if target_member.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Member is already admin"
        )

    target_member.role = "admin"
    db.commit()

    return {"message": f"User {target_member.user_id} promoted to admin successfully"}