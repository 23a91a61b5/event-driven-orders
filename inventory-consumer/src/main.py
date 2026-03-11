import pika
import json
import os
import time
from sqlalchemy import create_engine, text
from logger import setup_logger

logger = setup_logger('inventory_consumer')

# Configuration
DB_URL = os.getenv("DB_URL")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

# 1. Database Connection with Retry Logic
engine = None
while not engine:
    try:
        engine = create_engine(DB_URL)
        # Test connection
        with engine.connect() as conn:
            logger.info("Successfully connected to Database")
    except Exception as e:
        logger.warning(f"Waiting for Database... ({e})")
        time.sleep(5)

# 2. RabbitMQ Connection with Retry Logic
def get_rabbitmq_connection():
    while True:
        try:
            return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        except Exception as e:
            logger.warning(f"Waiting for RabbitMQ... ({e})")
            time.sleep(5)

# Helper to publish events back to Order Service
def publish_update(channel, message):
    channel.queue_declare(queue='inventory_updates', durable=True)
    channel.basic_publish(
        exchange='',
        routing_key='inventory_updates',
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2)
    )

# 3. Core Logic: Process the Order
def process_order(ch, method, properties, body):
    data = json.loads(body)
    logger.info(f"Processing Order: {data.get('orderId')}", extra={'orderId': data.get('orderId')})
    
    order_id = data['orderId']
    items = data['items']
    success = True
    reason = ""

    # Transaction: Check Stock -> Deduct if available
    try:
        with engine.begin() as conn: 
            # Step A: Check availability for ALL items first
            for item in items:
                pid = item['productId']
                qty = item['quantity']
                
                # Lock the row for update to prevent race conditions
                result = conn.execute(
                    text("SELECT stock FROM inventory WHERE productId = :pid FOR UPDATE"), 
                    {"pid": pid}
                ).fetchone()
                
                if not result:
                    success = False
                    reason = f"Product {pid} not found"
                    break
                
                if result[0] < qty:
                    success = False
                    reason = f"Insufficient stock for {pid}. Requested: {qty}, Available: {result[0]}"
                    break
            
            # Step B: If all items are available, deduct them
            if success:
                for item in items:
                    conn.execute(
                        text("UPDATE inventory SET stock = stock - :qty WHERE productId = :pid"),
                        {"qty": item['quantity'], "pid": item['productId']}
                    )
    except Exception as e:
        success = False
        reason = f"Database Error: {str(e)}"
        logger.error(reason, exc_info=True)

    # 4. Publish Result (Success or Failure)
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    
    if success:
        logger.info(f"SUCCESS: Inventory deducted for Order {order_id}", extra={'orderId': order_id, 'items': items})
        publish_update(channel, {
            "type": "InventoryDeducted",
            "orderId": order_id,
            "deductedItems": items
        })
    else:
        logger.warning(f"FAILED: Inventory check failed for Order {order_id}. Reason: {reason}", extra={'orderId': order_id, 'reason': reason})
        publish_update(channel, {
            "type": "InventoryFailed",
            "orderId": order_id,
            "reason": reason
        })
    
    connection.close()
    
    # Acknowledge message so RabbitMQ removes it from queue
    ch.basic_ack(delivery_tag=method.delivery_tag)

def process_compensation(ch, method, properties, body):
    data = json.loads(body)
    order_id = data.get('orderId')
    reason = data.get('reason')
    logger.info(f"Received Compensation for Order {order_id}. Reason: {reason}", extra={'orderId': order_id, 'compensation_reason': reason})
    # In a real system, we'd roll back any resources. Here, inventory didn't pass, so no inventory to rollback.
    # Just acknowledge.
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    logger.info("Starting Inventory Consumer...")
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    
    # Listen to 'order_created' queue
    channel.queue_declare(queue='order_created', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='order_created', on_message_callback=process_order)

    # Listen to 'order_compensation' queue
    channel.queue_declare(queue='order_compensation', durable=True)
    channel.basic_consume(queue='order_compensation', on_message_callback=process_compensation)
    
    logger.info(" [*] Waiting for orders and compensations. To exit press CTRL+C")
    try:
        channel.start_consuming()
    except Exception as e:
        logger.error(f"Consumer error", exc_info=True)

if __name__ == "__main__":
    main()