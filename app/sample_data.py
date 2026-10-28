"""
Synthetic sample data for /users and /products endpoints.
No real customer data. No database required (TECH-02: database optional).
"""

SAMPLE_USERS = [
    {"id": 1, "name": "Alice Johnson", "email": "alice@example.com", "role": "admin"},
    {"id": 2, "name": "Bob Smith", "email": "bob@example.com", "role": "user"},
    {"id": 3, "name": "Carol Williams", "email": "carol@example.com", "role": "user"},
    {"id": 4, "name": "David Brown", "email": "david@example.com", "role": "moderator"},
    {"id": 5, "name": "Eve Davis", "email": "eve@example.com", "role": "user"},
]

SAMPLE_PRODUCTS = [
    {"id": 101, "name": "Wireless Mouse", "price": 29.99, "in_stock": True},
    {"id": 102, "name": "Mechanical Keyboard", "price": 89.95, "in_stock": True},
    {"id": 103, "name": "USB-C Hub", "price": 45.00, "in_stock": False},
    {"id": 104, "name": "Monitor Stand", "price": 34.50, "in_stock": True},
    {"id": 105, "name": "Webcam HD", "price": 59.99, "in_stock": True},
]
