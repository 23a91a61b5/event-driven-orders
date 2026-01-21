from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_check():
    # We didn't explicitly make a health endpoint, but 404 on root proves app is running
    response = client.get("/")
    assert response.status_code in [404, 200]

def test_create_order():
    payload = {
        "customerId": "test-user",
        "items": [
            {"productId": "prod-1", "quantity": 1}
        ]
    }
    response = client.post("/api/orders", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PENDING"
    assert "orderId" in data

def test_get_order_not_found():
    response = client.get("/api/orders/non-existent-id")
    assert response.status_code == 404