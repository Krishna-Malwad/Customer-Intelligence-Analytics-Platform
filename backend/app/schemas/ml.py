from pydantic import BaseModel, Field


class SegmentRequest(BaseModel):
    recency_days: float = Field(..., ge=0, description="Days since last delivered order")
    frequency: int = Field(..., ge=1, description="Number of delivered orders")
    monetary: float = Field(..., ge=0, description="Total spend across delivered orders")


class RetentionRequest(BaseModel):
    order_total: float = Field(..., ge=0)
    n_items: int = Field(1, ge=1)
    payment_installments: int = Field(1, ge=1)
    review_score: float = Field(4.0, ge=1, le=5)
    product_category_name: str = "unknown"
    primary_payment_type: str = "credit_card"
    customer_state: str = "SP"


class OrderValueRequest(BaseModel):
    payment_installments: int = Field(1, ge=1)
    n_payment_methods: int = Field(1, ge=1)
    review_score: float = Field(4.0, ge=1, le=5)
    n_items: int = Field(1, ge=1)
    product_category_name: str = "unknown"
    primary_payment_type: str = "credit_card"
    customer_state: str = "SP"


class NLQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class BusinessQuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
