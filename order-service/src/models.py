from sqlalchemy import Column, String, Integer, DECIMAL, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Product(Base):
    __tablename__ = "products"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String(20), default="PENDING")
    createdAt = Column(DateTime, default=datetime.utcnow)

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