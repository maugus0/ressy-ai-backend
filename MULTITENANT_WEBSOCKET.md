# Multitenant WebSocket Implementation

## Overview

The WebSocket handler has been updated to support multitenancy, where each incoming call is automatically routed to the correct restaurant based on the Twilio phone number. The system now:

1. **Identifies Restaurant**: Extracts Twilio phone number from the call and finds the corresponding restaurant
2. **Loads Context**: Fetches available menu items and FAQs for that restaurant
3. **Dynamic Prompts**: Builds AI prompts with restaurant-specific context
4. **Data Extraction**: Extracts structured data (user details, orders, transcripts) from conversations
5. **Data Storage**: Stores extracted data in MySQL tables

## Architecture

### Components

1. **WebSocket Service** (`app/services/websocket_service.py`)
   - Handles multitenant call routing
   - Manages conversation history
   - Processes and stores extracted data

2. **Deepgram Service** (`app/services/deepgram_service.py`)
   - Builds dynamic prompts with restaurant context
   - Includes menu items and FAQs in the prompt

3. **Data Extraction Service** (`app/services/data_extraction_service.py`)
   - Extracts user details (name, phone, email, address)
   - Extracts order details (items, quantities, totals)
   - Builds transcript logs

4. **MySQL Repositories** (`app/repositories/mysql_*.py`)
   - Restaurant repository: Get restaurant by Twilio number
   - Menu repository: Get available menu items
   - FAQ repository: Get restaurant FAQs
   - User repository: Create/update users
   - Order repository: Create orders and order details
   - Transcript repository: Store call transcripts

## Flow

```
1. Call comes in via WebSocket
   ↓
2. Extract Twilio phone number from "start" event
   ↓
3. Query Restaurants table by twilio_phone_number
   ↓
4. Fetch available menu items (is_available = TRUE)
   ↓
5. Fetch FAQs for restaurant
   ↓
6. Build dynamic prompt with menu + FAQs
   ↓
7. Send prompt to Deepgram STS
   ↓
8. Process conversation (collect history)
   ↓
9. On call end: Extract structured data
   ↓
10. Store in MySQL:
    - Users table (user details)
    - Orders table (order info)
    - Order_Details table (order items)
    - Transcripts table (full conversation)
```

## SQL Queries

All required SQL queries are in `migrations/queries.sql`:

- Get restaurant by Twilio number
- Get available menu items
- Get FAQs
- Create/update user
- Create order
- Create order details
- Create transcript

## Environment Variables

Add these MySQL connection variables to your `.env`:

```env
MYSQL_HOST=localhost
MYSQL_DATABASE=ressy_ai
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_PORT=3306
```

## Dependencies

Add to `requirements.txt`:

```
mysql-connector-python>=8.0.0
```

## Twilio Number Extraction

The system extracts the Twilio phone number from the WebSocket "start" event. The number is typically found in:
- `data["start"]["callSidTo"]` or
- `data["start"]["to"]`

If the number is not found, the system falls back to default configuration.

## Data Extraction

The system uses regex patterns to extract:

### User Details
- Name: Patterns like "my name is...", "I'm...", "call me..."
- Phone: Various phone number formats
- Email: Standard email pattern
- Address: Patterns like "address is...", "live at..."

### Order Details
- Menu items: Matches spoken items with menu items (case-insensitive)
- Quantities: Extracts "2x", "two times", etc.
- Totals: Calculated from item prices and quantities

### Transcripts
- Complete conversation history with timestamps
- Stored as JSON in the `call_log` field

## Error Handling

- If restaurant not found: Falls back to default prompt
- If menu/FAQs not found: Continues with empty context
- If data extraction fails: Logs error but doesn't crash
- MySQL connection errors: Logged and handled gracefully

## Testing

1. Ensure MySQL database is set up with migrations
2. Add a restaurant with `twilio_phone_number` set
3. Add menu items with `is_available = TRUE`
4. Add FAQs for the restaurant
5. Make a call to the Twilio number
6. Check MySQL tables for extracted data

## Notes

- The system maintains backward compatibility with DynamoDB for call sessions
- MySQL is used for multitenant data (restaurants, menus, orders, users, transcripts)
- Conversation history is collected in memory and processed at call end
- Data extraction uses pattern matching - may need refinement based on actual conversations

