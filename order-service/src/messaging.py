import pika
import json
import os
import threading
import time
from sqlalchemy import exc
from .database import SessionLocal
from .models import Order, OutboxEvent
from .logger import setup_logger

logger = setup_logger('order_service.messaging')

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
        logger.info(f"Event published to {queue_name}", extra={'event_type': message.get('type'), 'orderId': message.get('orderId')})
    except Exception as e:
        logger.error(f"Failed to publish message: {e}", exc_info=True)

# Consumer: Listens for Inventory Updates (Success/Fail)
def start_status_consumer():
    connection = get_connection()
    channel = connection.channel()
    channel.queue_declare(queue='inventory_updates', durable=True)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        logger.info(f"Received status update", extra={'data': data})
        
        db = SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == data['orderId']).first()
            if order:
                if data['type'] == 'InventoryDeducted':
                    order.status = 'PROCESSING'
                elif data['type'] == 'InventoryFailed':
                    order.status = 'FAILED'
                    # Initiate Compensation
                    logger.warning(f"Initiating compensation for order {order.id}", extra={'orderId': order.id})
                    publish_event('order_compensation', {
                        'type': 'OrderFailedCompensation',
                        'orderId': order.id,
                        'reason': data.get('reason', 'Inventory Failed')
                    })
                
                db.commit()
                logger.info(f"Order status updated", extra={'orderId': order.id, 'status': order.status})
        except Exception as e:
            logger.error(f"Error updating order", exc_info=True)
        finally:
            db.close()
            ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue='inventory_updates', on_message_callback=callback)
    logger.info("Order Service Listening for Inventory Updates...")
    try:
        channel.start_consuming()
    except Exception as e:
        logger.error(f"Consumer error", exc_info=True)

# Poller: Scans OutboxEvent for pending messages
def start_outbox_poller():
    logger.info("Starting outbox poller thread...")
    while True:
        try:
            db = SessionLocal()
            pending_events = db.query(OutboxEvent).filter(OutboxEvent.status == 'PENDING').limit(50).with_for_update(skip_locked=True).all()
            for event in pending_events:
                queue_name = event.type
                payload = json.loads(event.payload)
                publish_event(queue_name, payload)
                
                event.status = 'PROCESSED'
                
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Error in outbox poller loop: {e}")
        time.sleep(2)

# Run consumer and poller in background threads
def run_consumer_thread():
    t1 = threading.Thread(target=start_status_consumer)
    t1.daemon = True
    t1.start()
    
    t2 = threading.Thread(target=start_outbox_poller)
    t2.daemon = True
    t2.start()