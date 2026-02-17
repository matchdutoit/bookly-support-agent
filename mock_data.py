"""
Mock data for Bookly customer support agent.
Contains sample orders with varied scenarios for testing.
"""

from datetime import datetime, timedelta

ORDERS = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_email": "alice@email.com",
        "status": "Delivered",
        "items": [
            {"title": "The Great Gatsby", "price": 14.99},
            {"title": "To Kill a Mockingbird", "price": 12.99}
        ],
        "order_date": "2026-01-10",
        "delivery_date": "2026-01-20",
        "estimated_delivery": None,
        "tracking_number": None,
        "total": 27.98,
        "return_eligible": True
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_email": "bob@email.com",
        "status": "In Transit",
        "items": [
            {"title": "1984", "price": 13.99}
        ],
        "order_date": "2026-02-05",
        "delivery_date": None,
        "estimated_delivery": "2026-02-12",
        "tracking_number": "TRK123456789",
        "total": 13.99,
        "return_eligible": False
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_email": "alice@email.com",
        "status": "Delivered",
        "items": [
            {"title": "Pride and Prejudice", "price": 11.99}
        ],
        "order_date": "2025-11-20",
        "delivery_date": "2025-12-01",
        "estimated_delivery": None,
        "tracking_number": None,
        "total": 11.99,
        "return_eligible": False  # Outside 30-day window
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "customer_email": "carol@email.com",
        "status": "Processing",
        "items": [
            {"title": "The Catcher in the Rye", "price": 10.99},
            {"title": "Brave New World", "price": 14.99}
        ],
        "order_date": "2026-02-07",
        "delivery_date": None,
        "estimated_delivery": "2026-02-15",
        "tracking_number": None,
        "total": 25.98,
        "return_eligible": False
    },
    "ORD-1005": {
        "order_id": "ORD-1005",
        "customer_email": "bob@email.com",
        "status": "Delivered",
        "items": [
            {"title": "Moby Dick", "price": 16.99}
        ],
        "order_date": "2026-01-25",
        "delivery_date": "2026-02-01",
        "estimated_delivery": None,
        "tracking_number": None,
        "total": 16.99,
        "return_eligible": True
    }
}


# Mock refund records used by refund-status tooling demos.
# These records are keyed by order_id and include a return_id.
REFUND_RECORDS = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "return_id": "RET-1001",
        "refund_status": "processing",  # pending|processing|issued|completed
        "refund_method": "original_payment",
        "last_updated": "2026-02-14",
        "estimated_completion": "2026-02-18",
        "reference_id": None,
    },
    "ORD-1005": {
        "order_id": "ORD-1005",
        "return_id": "RET-1005",
        "refund_status": "issued",
        "refund_method": "store_credit",
        "last_updated": "2026-02-13",
        "estimated_completion": "2026-02-16",
        "reference_id": "RFN-778211",
    },
}


def get_order_by_id(order_id):
    """Get a single order by its ID."""
    return ORDERS.get(order_id)


def get_orders_by_email(email):
    """Get all orders for a customer by email."""
    return [order for order in ORDERS.values() if order["customer_email"] == email]


def get_refund_by_order_id(order_id):
    """Get refund record by order ID."""
    return REFUND_RECORDS.get(order_id)


def get_refund_by_return_id(return_id):
    """Get refund record by return ID."""
    for record in REFUND_RECORDS.values():
        if record["return_id"] == return_id:
            return record
    return None


def upsert_refund_record(order_id, refund_method, refund_status="processing", reference_id=None):
    """
    Create or update a refund record for an order.
    Used so refund-status demos have realistic lifecycle data.
    """
    return_id = f"RET-{order_id.split('-')[1]}"
    today = datetime.utcnow().date()
    estimated_completion = today + timedelta(days=3)

    REFUND_RECORDS[order_id] = {
        "order_id": order_id,
        "return_id": return_id,
        "refund_status": refund_status,
        "refund_method": refund_method,
        "last_updated": today.isoformat(),
        "estimated_completion": estimated_completion.isoformat(),
        "reference_id": reference_id,
    }

    return REFUND_RECORDS[order_id]
