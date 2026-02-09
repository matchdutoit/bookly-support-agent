"""
Tool functions and definitions for the Bookly support agent.
"""

import json
from mock_data import get_order_by_id, get_orders_by_email


# Reasons that qualify for cash refund
CASH_REFUND_REASONS = ["damaged", "wrong_item", "defective", "never_arrived"]

# Reasons that only qualify for store credit
STORE_CREDIT_REASONS = ["didnt_like", "changed_mind", "no_longer_needed"]


def lookup_order(order_id=None, customer_email=None):
    """
    Look up order details by order ID or customer email.
    Returns order details or error message.
    """
    if order_id:
        order = get_order_by_id(order_id)
        if order:
            return {"success": True, "order": order}
        else:
            return {"success": False, "error": f"Order {order_id} not found"}

    elif customer_email:
        orders = get_orders_by_email(customer_email)
        if orders:
            return {"success": True, "orders": orders}
        else:
            return {"success": False, "error": f"No orders found for {customer_email}"}

    else:
        return {"success": False, "error": "Please provide either order_id or customer_email"}


def check_return_eligibility(order_id):
    """
    Check if an order is eligible for return.
    Returns eligibility status with reason.
    """
    order = get_order_by_id(order_id)

    if not order:
        return {"eligible": False, "reason": f"Order {order_id} not found"}

    if order["status"] != "Delivered":
        return {
            "eligible": False,
            "reason": f"Order is currently '{order['status']}'. Only delivered orders can be returned."
        }

    if not order["return_eligible"]:
        return {
            "eligible": False,
            "reason": f"Order was delivered on {order['delivery_date']}, which is outside the 30-day return window."
        }

    return {
        "eligible": True,
        "reason": "Order is eligible for return.",
        "order_id": order_id,
        "delivery_date": order["delivery_date"],
        "items": order["items"],
        "total": order["total"]
    }


def initiate_return(order_id, reason, refund_type=None):
    """
    Initiate a return for an eligible order.
    Determines refund type based on reason if not specified.
    """
    # First check eligibility
    eligibility = check_return_eligibility(order_id)
    if not eligibility.get("eligible"):
        return {"success": False, "error": eligibility["reason"]}

    order = get_order_by_id(order_id)

    # Determine refund type based on reason
    reason_lower = reason.lower().replace(" ", "_")

    if any(r in reason_lower for r in CASH_REFUND_REASONS):
        determined_refund_type = "cash"
    elif any(r in reason_lower for r in STORE_CREDIT_REASONS):
        determined_refund_type = "store_credit"
    else:
        # Default to store credit for unrecognized reasons
        determined_refund_type = refund_type or "store_credit"

    return {
        "success": True,
        "return_id": f"RET-{order_id.split('-')[1]}",
        "order_id": order_id,
        "items": order["items"],
        "refund_amount": order["total"],
        "refund_type": determined_refund_type,
        "instructions": "Please pack the item(s) securely. A prepaid return label will be sent to your email within 24 hours. Once we receive the return, your refund will be processed within 3-5 business days."
    }


def execute_tool(tool_name, arguments):
    """Execute a tool by name with given arguments."""
    tools_map = {
        "lookup_order": lookup_order,
        "check_return_eligibility": check_return_eligibility,
        "initiate_return": initiate_return
    }

    if tool_name in tools_map:
        return tools_map[tool_name](**arguments)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


# OpenAI function calling tool definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up order details by order ID or customer email. Use this when customer asks about order status, tracking, or delivery.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID (e.g., ORD-1001)"
                    },
                    "customer_email": {
                        "type": "string",
                        "description": "Customer's email address"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_return_eligibility",
            "description": "Check if an order is eligible for return. Use this before processing any return request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to check for return eligibility"
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_return",
            "description": "Initiate a return for an eligible order. Only use after confirming eligibility and collecting the return reason from the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to return"
                    },
                    "reason": {
                        "type": "string",
                        "description": "The reason for the return (e.g., 'damaged', 'wrong_item', 'defective', 'never_arrived', 'didnt_like', 'changed_mind', 'no_longer_needed')"
                    },
                    "refund_type": {
                        "type": "string",
                        "enum": ["cash", "store_credit"],
                        "description": "Type of refund (determined automatically based on reason if not specified)"
                    }
                },
                "required": ["order_id", "reason"]
            }
        }
    }
]
