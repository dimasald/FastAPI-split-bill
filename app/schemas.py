from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str


class GroupCreate(BaseModel):
    name: str

class GroupResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class InviteMember(BaseModel):
    email: EmailStr

class GroupMemberResponse(BaseModel):
    user_id: int
    email: EmailStr
    role: str


class ExpenseSplitCreate(BaseModel):
    user_id: int
    amount: int

class ExpenseCreate(BaseModel):
    description: str
    amount: int
    paid_by: int
    splits: List[ExpenseSplitCreate]

class ExpenseSplitResponse(BaseModel):
    user_id: int
    amount: int

    model_config = ConfigDict(from_attributes=True)

class ExpenseResponse(BaseModel):
    id: int
    description: str
    amount: int
    paid_by: int
    created_at: datetime
    splits: List[ExpenseSplitResponse]

    model_config = ConfigDict(from_attributes=True)

class BalanceResponse(BaseModel):
    email: EmailStr
    balance: int

class SettlementCreate(BaseModel):
    payee_id: int
    amount: int

class SettlementResponse(BaseModel):
    id: int
    payer_id: int
    payee_id: int
    amount: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)