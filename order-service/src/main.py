from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import uuid

from .database import get_db, Base, engine
from .models import Order, OrderItem
from .messaging import publish_event, run_consumer_thread

# Create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Start the background listener for RabbitMQ
@app.on_event("startup")
def startup_event():
    run_consumer_thread()

# --- Pydantic Models for Input Validation ---
class OrderItemReq(BaseModel):
    productId: str
    quantity: int

class OrderReq(BaseModel):
    customerId: str
    items: List[OrderItemReq]

# --- Endpoints ---

@app.post("/api/orders", status_code=201)
def create_order(order_req: OrderReq, db: Session = Depends(get_db)):
    order_id = str(uuid.uuid4())
    total_amount = 0.0
    db_items = []

    # Mock Price Lookup (In a real app, query the Product table)
    mock_prices = {"prod-1": 1200.00, "prod-2": 25.00, "prod-3": 75.00}

    # 1. Prepare Data
    for item in order_req.items:
        price = mock_prices.get(item.productId, 0.0) # Default to 0 if not found
        total_amount += price * item.quantity
        
        db_items.append(OrderItem(
            orderId=order_id,
            productId=item.productId,
            quantity=item.quantity,
            price=price
        ))

    # 2. Save Order to DB (Status: PENDING)
    new_order = Order(
        id=order_id,
        customerId=order_req.customerId,
        totalAmount=total_amount,
        status="PENDING"
    )

    try:
        db.add(new_order)
        for item in db_items:
            db.add(item)
        db.commit()
        
        # 3. Publish Event to Queue
        event_payload = {
            "type": "OrderCreated",
            "orderId": order_id,
            "items": [{"productId": i.productId, "quantity": i.quantity} for i in order_req.items]
        }
        publish_event('order_created', event_payload)

        return {
            "orderId": order_id,
            "customerId": new_order.customerId,
            "status": "PENDING",
            "totalAmount": total_amount,
            "message": "Order created successfully"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/orders")
def list_orders(page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    offset = (page - 1) * limit
    orders = db.query(Order).offset(offset).limit(limit).all()
    return {
        "data": orders,
        "page": page,
        "limit": limit,
        "total": db.query(Order).count()
    }