# Event-Driven Order Processing Service

## Overview
A scalable, event-driven backend system for processing e-commerce orders. It uses FastAPI for the REST API, RabbitMQ for asynchronous messaging, and MySQL for persistence. The system decouples order reception from inventory processing to ensure high availability.

## Architecture
1. **Order Service (Producer)**: Receives HTTP POST requests, saves 'PENDING' orders, and publishes `OrderCreated` events.
2. **RabbitMQ**: Acts as the message broker handling `order_created` and `inventory_updates` queues.
3. **Inventory Consumer**: Subscribes to events, checks/updates stock in MySQL, and publishes `InventoryDeducted` or `InventoryFailed` events.
4. **Order Service (Consumer)**: Listens for inventory updates and finalizes order status to 'PROCESSING' or 'FAILED'.

## Setup Instructions

### Prerequisites
- Docker & Docker Compose installed.

### How to Run
1. Clone the repository.
2. Create a `.env` file (see `.env.example`).
3. Run the system:
   ```bash
   docker-compose up --build