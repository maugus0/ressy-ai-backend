# In-House Reservation API - cURL Examples

This document provides cURL examples for all in-house reservation APIs.

## Base URL
```
http://localhost:5001/api/v1
```

## Authentication
All endpoints are publicly accessible and do not require authentication.

---

## Public/User APIs

### 1. Get Table Availability

Get available time slots for a restaurant.

**Endpoint:** `GET /reservations/availability/{restaurant_id}`

**cURL:**
```bash
curl -X GET "http://localhost:5001/api/v1/reservations/availability/1?start_date_time=2024-12-20T18:00:00&forward_minutes=1440&backward_minutes=0&party_size=2" \
  -H "Content-Type: application/json"
```

**Parameters:**
- `restaurant_id` (path): Restaurant ID
- `start_date_time` (query, required): Start date and time in ISO format (e.g., `2024-12-20T18:00:00`)
- `forward_minutes` (query, optional): Forward booking window in minutes (default: restaurant's forward_minutes)
- `backward_minutes` (query, optional): Backward booking window in minutes (default: restaurant's backward_minutes)
- `party_size` (query, optional): Party size

**Response:**
```json
{
  "restaurant_id": 1,
  "start_date_time": "2024-12-20T18:00:00",
  "forward_minutes": 1440,
  "backward_minutes": 0,
  "party_size": 2,
  "slots": [
    {
      "date_time": "2024-12-20T18:00:00",
      "available": true,
      "reservation_token": "abc123..."
    }
  ],
  "total_available": 1
}
```

---

### 2. Lock a Booking Slot

Lock a specific time slot for a reservation.

**Endpoint:** `POST /reservations/booking/{restaurant_id}/slot_locks`

**cURL:**
```bash
curl -X POST "http://localhost:5001/api/v1/reservations/booking/1/slot_locks" \
  -H "Content-Type: application/json" \
  -d '{
    "party_size": 2,
    "date_time": "2024-12-20T18:00:00",
    "reservation_attribute": "default"
  }'
```

**Request Body:**
```json
{
  "party_size": 2,
  "date_time": "2024-12-20T18:00:00",
  "reservation_attribute": "default"
}
```

**Response:**
```json
{
  "reservation_token": "550e8400-e29b-41d4-a716-446655440000",
  "date_time": "2024-12-20T18:00:00",
  "party_size": 2,
  "expires_at": "2024-12-20T18:15:00",
  "slot_id": 123
}
```

---

### 3. Create Reservation

Create a reservation with pending status.

**Endpoint:** `POST /reservations/booking/{restaurant_id}/reservations`

**cURL:**
```bash
curl -X POST "http://localhost:5001/api/v1/reservations/booking/1/reservations" \
  -H "Content-Type: application/json" \
  -d '{
    "reservation_token": "550e8400-e29b-41d4-a716-446655440000",
    "name": "John Doe",
    "phone_number": "+1234567890",
    "email_address": "john.doe@example.com",
    "special_request": "Window seat preferred"
  }'
```

**Request Body:**
```json
{
  "reservation_token": "550e8400-e29b-41d4-a716-446655440000",
  "name": "John Doe",
  "phone_number": "+1234567890",
  "email_address": "john.doe@example.com",
  "special_request": "Window seat preferred"
}
```

**Note:** Only `name` and `phone_number` are required. `email_address` and `special_request` are optional.

**Response:**
```json
{
  "reservation_id": 456,
  "confirmation_number": "INH-1-A1B2C3D4",
  "status": "pending",
  "date_time": "2024-12-20T18:00:00",
  "message": "Reservation created successfully. Awaiting confirmation from restaurant."
}
```

---

### 4. Get Reservation by ID

Get details of a specific reservation.

**Endpoint:** `GET /reservations/{reservation_id}`

**cURL:**
```bash
curl -X GET "http://localhost:5001/api/v1/reservations/456" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "id": 456,
  "reservation_type": "inhouse",
  "table_availability_request_id": null,
  "slot_booking_id": 123,
  "user_id": 789,
  "confirmation_number": "INH-1-A1B2C3D4",
  "last_cancel_time": null,
  "manage_reservation_url": null,
  "status": "pending",
  "created_at": "2024-12-20T17:00:00",
  "updated_at": "2024-12-20T17:00:00",
  "date_time": "2024-12-20T18:00:00",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone_number": "+1234567890"
}
```

---

### 5. Cancel Reservation

Cancel a reservation.

**Endpoint:** `PUT /reservations/{reservation_id}/cancel`

**cURL:**
```bash
curl -X PUT "http://localhost:5001/api/v1/reservations/456/cancel" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "reservation_id": 456,
  "status": "cancelled",
  "message": "Reservation cancelled successfully"
}
```

---

## Dashboard APIs

All dashboard APIs are publicly accessible.

### 6. Finalize Reservation (Dashboard Only)

Finalize a pending reservation by changing status to confirmed.

**Endpoint:** `PUT /dashboard/reservations/{reservation_id}/finalize`

**cURL:**
```bash
curl -X PUT "http://localhost:5001/api/v1/dashboard/reservations/456/finalize" \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation_number": "INH-1-A1B2C3D4"
  }'
```

**Request Body (optional):**
```json
{
  "confirmation_number": "INH-1-A1B2C3D4"
}
```

**Response:**
```json
{
  "reservation_id": 456,
  "confirmation_number": "INH-1-A1B2C3D4",
  "status": "confirmed",
  "message": "Reservation confirmed successfully"
}
```

---

### 7. Get Reservations by Restaurant (Dashboard)

Get all reservations for a restaurant with filtering options.

**Endpoint:** `GET /dashboard/restaurants/{restaurant_id}/reservations`

**cURL:**
```bash
curl -X GET "http://localhost:5001/api/v1/dashboard/restaurants/1/reservations?status=pending&start_date=2024-12-20T00:00:00&end_date=2024-12-21T23:59:59&limit=100&offset=0" \
  -H "Content-Type: application/json"
```

**Parameters:**
- `restaurant_id` (path): Restaurant ID
- `status` (query, optional): Filter by status (`pending`, `confirmed`, `cancelled`, `completed`)
- `start_date` (query, optional): Filter by start date (ISO format)
- `end_date` (query, optional): Filter by end date (ISO format)
- `limit` (query, optional): Limit results (default: 100, max: 1000)
- `offset` (query, optional): Offset for pagination (default: 0)

**Response:**
```json
{
  "restaurant_id": 1,
  "reservations": [
    {
      "id": 456,
      "reservation_type": "inhouse",
      "table_availability_request_id": null,
      "slot_booking_id": 123,
      "user_id": 789,
      "confirmation_number": "INH-1-A1B2C3D4",
      "last_cancel_time": null,
      "manage_reservation_url": null,
      "status": "pending",
      "created_at": "2024-12-20T17:00:00",
      "updated_at": "2024-12-20T17:00:00",
      "date_time": "2024-12-20T18:00:00",
      "name": "John Doe",
      "email": "john.doe@example.com",
      "phone_number": "+1234567890"
    }
  ],
  "total": 1
}
```

---

### 8. Get Reservation by ID (Dashboard)

Get details of a specific reservation (dashboard version).

**Endpoint:** `GET /dashboard/reservations/{reservation_id}`

**cURL:**
```bash
curl -X GET "http://localhost:5001/api/v1/dashboard/reservations/456" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "id": 456,
  "reservation_type": "inhouse",
  "table_availability_request_id": null,
  "slot_booking_id": 123,
  "user_id": 789,
  "confirmation_number": "INH-1-A1B2C3D4",
  "last_cancel_time": null,
  "manage_reservation_url": null,
  "status": "pending",
  "created_at": "2024-12-20T17:00:00",
  "updated_at": "2024-12-20T17:00:00",
  "date_time": "2024-12-20T18:00:00",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone_number": "+1234567890"
}
```

---

### 9. Cancel Reservation (Dashboard)

Cancel a reservation (dashboard version).

**Endpoint:** `PUT /dashboard/reservations/{reservation_id}/cancel`

**cURL:**
```bash
curl -X PUT "http://localhost:5001/api/v1/dashboard/reservations/456/cancel" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "reservation_id": 456,
  "status": "cancelled",
  "message": "Reservation cancelled successfully"
}
```

---

## Complete Flow Example

Here's a complete example of the reservation flow:

### Step 1: Check Availability
```bash
curl -X GET "http://localhost:5001/api/v1/reservations/availability/1?start_date_time=2024-12-20T18:00:00&forward_minutes=1440&party_size=2"
```

### Step 2: Lock a Slot
```bash
curl -X POST "http://localhost:5001/api/v1/reservations/booking/1/slot_locks" \
  -H "Content-Type: application/json" \
  -d '{
    "party_size": 2,
    "date_time": "2024-12-20T18:00:00",
    "reservation_attribute": "default"
  }'
```

### Step 3: Create Reservation
```bash
curl -X POST "http://localhost:5001/api/v1/reservations/booking/1/reservations" \
  -H "Content-Type: application/json" \
  -d '{
    "reservation_token": "RESERVATION_TOKEN_FROM_STEP_2",
    "name": "John Doe",
    "phone_number": "+1234567890",
    "email_address": "john.doe@example.com",
    "special_request": "Window seat preferred"
  }'
```

### Step 4: Finalize Reservation
```bash
curl -X PUT "http://localhost:5001/api/v1/dashboard/reservations/RESERVATION_ID_FROM_STEP_3/finalize" \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## Error Responses

All endpoints may return the following error responses:

**400 Bad Request:**
```json
{
  "detail": "Invalid date_time format: 2024-12-20"
}
```


**404 Not Found:**
```json
{
  "detail": "Reservation with ID 456 not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error fetching availability: ..."
}
```

---

## Notes

1. **Reservation Types**: The system differentiates between `opentable` and `inhouse` reservations using the `reservation_type` flag.

2. **Reservation Status Flow**:
   - `pending` → Created but not yet confirmed
   - `confirmed` → Finalized by restaurant (dashboard only)
   - `cancelled` → Cancelled by user or restaurant
   - `completed` → Reservation completed
   - `no_show` → Customer did not show up

3. **Slot Expiration**: Slots expire after 15 minutes if not used to create a reservation.

4. **Finalization**: Only pending reservations can be finalized. Finalization can only be done through the dashboard API.

5. **Authentication**: All endpoints are publicly accessible and do not require authentication.

