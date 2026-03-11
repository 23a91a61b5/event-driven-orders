# Event-Driven Order Processing Service

## Overview
A scalable, highly-resilient, event-driven backend system for processing e-commerce orders. It utilizes FastAPI for its RESTful API, RabbitMQ for asynchronous event messaging, and MySQL for robust relational persistence. The system carefully decouples the order reception gateway from backend inventory management, enforcing high availability and eventual consistency.

## Architecture & Trade-offs
1. **Order Service (API + Producer)**: Exposes endpoints for managing orders. Employs the **Transactional Outbox Pattern** to ensure atomicity between saving the order in the database and publishing the `OrderCreated` event to RabbitMQ. 
2. **RabbitMQ**: The central message broker handling `order_created`, `inventory_updates`, and `order_compensation` queues. Ensures messages are decoupled and load-balanced.
3. **Inventory Consumer**: Subscribes to `order_created` events. It applies database-level locks (`FOR UPDATE`) to ensure idempotency and prevent race conditions when checking stock availability. It reports back by publishing either `InventoryDeducted` or `InventoryFailed`.
4. **Order Service (Consumer)**: Listens for inventory updates to transition the order state to `PROCESSING` or `FAILED`. If `FAILED`, it triggers an `OrderFailedCompensation` event to support distributed transaction rollbacks.
5. **Observability**: Implements structured JSON logging for all key system events, errors, and trace steps, significantly aiding in debugging and production monitoring.

## Setup Instructions

### Prerequisites
- Docker & Docker Compose (v3.8+)

### How to Run Locally
1. Clone the repository to your local environment.
2. Ensure you have the required environment variables. You can copy the template:
   ```bash
   cp .env.example .env
   ```
3. Spin up the orchestrator:
   ```bash
   docker-compose up --build
   ```
   *Note: This will install MySQL, RabbitMQ, order-service, inventory-consumer, run schema migrations, and automatically seed initial data (Products and Inventory stocks).*

## API Documentation

### 1. Create Order
- **Endpoint**: `POST /api/orders`
- **Request Body**:
```json
{
  "customerId": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
  "items": [
    { "productId": "prod-1", "quantity": 1 }
  ]
}
```
- **Responses**: 
    - `201 Created` on valid schema and product existence.
    - `400 Bad Request` if required parameters are missing or invalid, or if product does not exist.

### 2. Get Order by ID
- **Endpoint**: `GET /api/orders/{orderId}`
- **Response**:
```json
{
  "orderId": "UUID",
  "customerId": "UUID",
  "status": "PENDING|PROCESSING|FAILED",
  "totalAmount": 1200.0,
  "createdAt": "2026-01-21T12:00:00.000000",
  "items": [
    { "productId": "prod-1", "quantity": 1, "price": 1200.0 }
  ]
}
```

### 3. List Orders
- **Endpoint**: `GET /api/orders`
- **Query Parameters**: 
    - `page` (default: 1)
    - `limit` (default: 10)
    - `status` (optional, e.g. `PENDING`, `PROCESSING`, `FAILED`)
- **Response**: Paginated list of basic order structures.

## Testing Instructions

Automated tests are developed using `pytest`. Ensure the application's docker containers are running (`docker-compose up -d`) before executing integration assessments.

### Unit Tests
Unit tests use patched database connections and mock objects to verify standalone logic in total isolation.
- **Order Service**: `docker-compose exec order-service pytest tests/unit/`
- **Inventory Consumer**: `docker-compose exec inventory-consumer pytest tests/unit/`

### Integration Tests
Integration tests execute end-to-end API invocations, verifying messaging delivery and dynamic eventual consistency processes via the broker.
- **E2E Integration Flows**: `docker-compose exec order-service pytest tests/integration/`