import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from src.main import app, get_db
from src.models import Product, Order

client = TestClient(app)

def test_create_order_invalid_product():
    # Mock DB session
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None # Product not found

    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.post("/api/orders", json={
        "customerId": "b371131c-6d8b-4a57-b087-0b1e15fa57c5",
        "items": [
            {"productId": "b371131c-6d8b-4a57-b087-0b1e15fa57c6", "quantity": 1}
        ]
    })
    
    assert response.status_code == 400
    assert "not found" in response.json()["detail"]
    app.dependency_overrides.clear()

def test_create_order_success():
    mock_db = MagicMock()
    mock_product = Product(id="123e4567-e89b-12d3-a456-426614174001", price=100.0)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_product

    # Mock order save
    def mock_add(obj):
        if isinstance(obj, Order):
            obj.id = "order-123"
            obj.createdAt = None
    mock_db.add.side_effect = mock_add

    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.post("/api/orders", json={
        "customerId": "b371131c-6d8b-4a57-b087-0b1e15fa57c5",
        "items": [
            {"productId": "b371131c-6d8b-4a57-b087-0b1e15fa57c6", "quantity": 2}
        ]
    })
    
    if response.status_code != 201:
        print("Error response:", response.json())
    assert response.status_code == 201
    assert response.json()["totalAmount"] == 200.0
    assert response.json()["status"] == "PENDING"
    assert mock_db.commit.called
    app.dependency_overrides.clear()
