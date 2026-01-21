from sqlalchemy import Column, String, Integer, DECIMAL, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String(36), primary_key=True)
    customerId = Column(String(36))
    status = Column(String(50), default="PENDING")
    totalAmount = Column(DECIMAL(10, 2))
    createdAt = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to Items
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    orderId = Column(String(36), ForeignKey("orders.id"), primary_key=True)
    productId = Column(String(36), primary_key=True)
    quantity = Column(Integer)
    price = Column(DECIMAL(10, 2))
    
    order = relationship("Order", back_populates="items")