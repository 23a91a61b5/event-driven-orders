import pika
import json
import os
import threading
import time
from .database import SessionLocal
from .models import Order

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

def get_connection():
    # Simple retry logic for RabbitMQ connection
    while True:
        try:
            return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        except pika.exceptions.AMQPConnectionError:
            print("Waiting for RabbitMQ...")
            time.sleep(5)

def publish_event(queue_name, message):
    try:
        connection = get_connection()
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2) # Persistent message
        )
        connection.close()
        print(f"Event published to {queue_name}")
    except Exception as e:
        print(f"Failed to publish message: {e}")

# Consumer: Listens for Inventory Updates (Success/Fail)
def start_status_consumer():
    connection = get_connection()
    channel = connection.channel()
    channel.queue_declare(queue='inventory_updates', durable=True)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        print(f"Received status update: {data}")
        
        db = SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == data['orderId']).first()
            if order:
                if data['type'] == 'InventoryDeducted':
                    order.status = 'PROCESSING'
                elif data['type'] == 'InventoryFailed':
                    order.status = 'FAILED'
                
                db.commit()
                print(f"Order {order.id} status updated to {order.status}")
        except Exception as e:
            print(f"Error updating order: {e}")
        finally:
            db.close()
            ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue='inventory_updates', on_message_callback=callback)
    print("Order Service Listening for Inventory Updates...")
    channel.start_consuming()

# Run consumer in a background thread so it doesn't block the API
def run_consumer_thread():
    t = threading.Thread(target=start_status_consumer)
    t.daemon = True
    t.start()