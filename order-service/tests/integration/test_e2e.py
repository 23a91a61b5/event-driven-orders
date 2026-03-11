import pytest
import time
import httpx

# These tests expect the docker-compose environment to be running
def test_full_order_flow():
    # Call the API to create an order
    order_req = {
        "customerId": "b371131c-6d8b-4a57-b087-0b1e15fa57c5",
        "items": [
            {"productId": "prod-1", "quantity": 1} # Laptop: 1200.00
        ]
    }
    
    response = httpx.post("http://localhost:8000/api/orders", json=order_req)
    assert response.status_code == 201
    
    order_data = response.json()
    order_id = order_data["orderId"]
    assert order_data["status"] == "PENDING"
    
    # Poll for status change to PROCESSING as inventory consumer processes it
    status_changed = False
    for i in range(15): # wait up to 15 seconds
        time.sleep(1)
        res = httpx.get(f"http://localhost:8000/api/orders/{order_id}")
        if res.status_code == 200:
            current_status = res.json()["status"]
            if current_status == "PROCESSING":
                status_changed = True
                break
            elif current_status == "FAILED":
                assert False, f"Order failed unexpectedly."
                
    assert status_changed, f"Order {order_id} did not reach PROCESSING status"

def test_full_order_flow_insufficient_stock():
    order_req = {
        "customerId": "b371131c-6d8b-4a57-b087-0b1e15fa57c5",
        "items": [
            {"productId": "prod-1", "quantity": 1000} # Too many
        ]
    }
    
    response = httpx.post("http://localhost:8000/api/orders", json=order_req)
    assert response.status_code == 201
    order_id = response.json()["orderId"]
    
    status_changed = False
    for i in range(15):
        time.sleep(1)
        res = httpx.get(f"http://localhost:8000/api/orders/{order_id}")
        if res.status_code == 200:
            current_status = res.json()["status"]
            if current_status == "FAILED":
                status_changed = True
                break
                
    assert status_changed, f"Order {order_id} did not reach FAILED status"
