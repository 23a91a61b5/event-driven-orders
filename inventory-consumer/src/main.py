import pika
import json
import os
import time
from sqlalchemy import create_engine, text

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
            print("Successfully connected to Database")
    except Exception as e:
        print(f"Waiting for Database... ({e})")
        time.sleep(5)

# 2. RabbitMQ Connection with Retry Logic
def get_rabbitmq_connection():
    while True:
        try:
            return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        except Exception as e:
            print(f"Waiting for RabbitMQ... ({e})")
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
    print(f"Processing Order: {data['orderId']}")
    
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
        print(reason)

    # 4. Publish Result (Success or Failure)
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    
    if success:
        print(f"SUCCESS: Inventory deducted for Order {order_id}")
        publish_update(channel, {
            "type": "InventoryDeducted",
            "orderId": order_id,
            "deductedItems": items
        })
    else:
        print(f"FAILED: Inventory check failed for Order {order_id}. Reason: {reason}")
        publish_update(channel, {
            "type": "InventoryFailed",
            "orderId": order_id,
            "reason": reason
        })
    
    connection.close()
    
    # Acknowledge message so RabbitMQ removes it from queue
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    print("Starting Inventory Consumer...")
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    
    # Listen to 'order_created' queue
    channel.queue_declare(queue='order_created', durable=True)
    
    # Process 1 message at a time to ensure fair load balancing
    channel.basic_qos(prefetch_count=1)
    
    channel.basic_consume(queue='order_created', on_message_callback=process_order)
    
    print(" [*] Waiting for orders. To exit press CTRL+C")
    channel.start_consuming()

if __name__ == "__main__":
    main()