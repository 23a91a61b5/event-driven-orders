from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, UUID4, validator
from typing import List, Optional
from enum import Enum
import uuid
import json
from datetime import datetime, timezone

from .database import get_db, Base, engine
from .models import Order, OrderItem, Product, OutboxEvent
from .messaging import run_consumer_thread

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Start the background listener for RabbitMQ
@app.on_event("startup")
def startup_event():
    run_consumer_thread()

# --- Pydantic Models for Input Validation ---
class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"

class OrderItemReq(BaseModel):
    productId: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1)

class OrderReq(BaseModel):
    customerId: UUID4
    items: List[OrderItemReq]

# --- Endpoints ---

@app.post("/api/orders", status_code=201)
def create_order(order_req: OrderReq, db: Session = Depends(get_db)):
    order_id = str(uuid.uuid4())
    total_amount = 0.0
    db_items = []
    
    # 1. Prepare Data and check inventory prices
    for item in order_req.items:
        prod_id = str(item.productId)
        product = db.query(Product).filter(Product.id == prod_id).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Product {prod_id} not found")
        
        price = product.price
        total_amount += float(price) * item.quantity
        
        db_items.append(OrderItem(
            orderId=order_id,
            productId=prod_id,
            quantity=item.quantity,
            price=price
        ))

    # 2. Save Order to DB (Status: PENDING)
    new_order = Order(
        id=order_id,
        customerId=str(order_req.customerId),
        totalAmount=total_amount,
        status="PENDING"
    )

    try:
        db.add(new_order)
        for item in db_items:
            db.add(item)
        
        # 3. Save Event to Outbox Table
        event_payload = {
            "type": "OrderCreated",
            "orderId": order_id,
            "customerId": str(order_req.customerId),
            "items": [{"productId": i.productId, "quantity": i.quantity, "price": float(i.price)} for i in db_items],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        outbox_event = OutboxEvent(
            type="order_created",
            payload=json.dumps(event_payload),
            status="PENDING"
        )
        db.add(outbox_event)
        
        db.commit()
        db.refresh(new_order)
        
        return {
            "orderId": new_order.id,
            "customerId": new_order.customerId,
            "status": new_order.status,
            "totalAmount": float(new_order.totalAmount),
            "createdAt": new_order.createdAt.isoformat() if new_order.createdAt else datetime.utcnow().isoformat(),
            "items": [
                {"productId": str(i.productId), "quantity": i.quantity, "price": float(i.price)}
                for i in db_items
            ],
            "message": "Order created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/{order_id}")
def get_order(order_id: UUID4, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == str(order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/orders")
def list_orders(status: Optional[OrderStatus] = Query(None), page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    offset = (page - 1) * limit
    
    query = db.query(Order)
    if status is not None:
        query = query.filter(Order.status == status.value)
        
    orders = query.offset(offset).limit(limit).all()
    return {
        "data": orders,
        "page": page,
        "limit": limit,
        "total": query.count()
    }