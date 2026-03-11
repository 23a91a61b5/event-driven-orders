import pytest
import json
from unittest.mock import MagicMock, patch
from src.main import process_order

@patch('src.main.engine.begin')
@patch('src.main.publish_update')
@patch('src.main.get_rabbitmq_connection')
def test_process_order_success(mock_rabbit, mock_publish, mock_db_begin):
    mock_conn = MagicMock()
    mock_db_begin.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = [10] # Stock = 10
    
    # Mock rabbitmq channel and method
    mock_channel = MagicMock()
    mock_rabbit.return_value.channel.return_value = mock_channel
    
    ch = MagicMock()
    method = MagicMock()
    method.delivery_tag = 1
    properties = MagicMock()
    
    body = json.dumps({
        "orderId": "order-123",
        "items": [{"productId": "prod-1", "quantity": 2}]
    }).encode('utf-8')
    
    process_order(ch, method, properties, body)
    
    # Assert
    assert mock_publish.call_count == 1
    published_msg = mock_publish.call_args[0][1]
    assert published_msg["type"] == "InventoryDeducted"
    assert published_msg["orderId"] == "order-123"
    assert "deductedItems" in published_msg
    
    # Assert Ack
    ch.basic_ack.assert_called_once_with(delivery_tag=1)

@patch('src.main.engine.begin')
@patch('src.main.publish_update')
@patch('src.main.get_rabbitmq_connection')
def test_process_order_insufficient_stock(mock_rabbit, mock_publish, mock_db_begin):
    mock_conn = MagicMock()
    mock_db_begin.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = [1] # Stock = 1
    
    mock_channel = MagicMock()
    mock_rabbit.return_value.channel.return_value = mock_channel
    
    ch = MagicMock()
    method = MagicMock()
    body = json.dumps({
        "orderId": "order-123",
        "items": [{"productId": "prod-1", "quantity": 2}]
    }).encode('utf-8')
    
    process_order(ch, method, properties=None, body=body)
    
    assert mock_publish.call_count == 1
    published_msg = mock_publish.call_args[0][1]
    assert published_msg["type"] == "InventoryFailed"
    assert "reason" in published_msg
    assert ch.basic_ack.called
