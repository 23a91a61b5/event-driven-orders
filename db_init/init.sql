CREATE TABLE IF NOT EXISTS products (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    productId VARCHAR(36) PRIMARY KEY,
    stock INT NOT NULL DEFAULT 0,
    FOREIGN KEY (productId) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(36) PRIMARY KEY,
    customerId VARCHAR(36) NOT NULL,
    status ENUM('PENDING', 'PROCESSING', 'FAILED') NOT NULL DEFAULT 'PENDING',
    totalAmount DECIMAL(10, 2) NOT NULL,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    orderId VARCHAR(36) NOT NULL,
    productId VARCHAR(36) NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (orderId, productId),
    FOREIGN KEY (orderId) REFERENCES orders(id),
    FOREIGN KEY (productId) REFERENCES products(id)
);

-- Seed Data (Mock Data)
INSERT IGNORE INTO products (id, name, price) VALUES
('prod-1', 'Laptop', 1200.00),
('prod-2', 'Mouse', 25.00),
('prod-3', 'Keyboard', 75.00);

INSERT IGNORE INTO inventory (productId, stock) VALUES
('prod-1', 100),
('prod-2', 500),
('prod-3', 200);