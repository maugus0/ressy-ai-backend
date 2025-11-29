# Admin API - cURL Examples

This document contains cURL examples for all Admin API endpoints.

**Base URL**: `http://localhost:5001/api/v1/admin`

**Note**: Replace `{token}` with your actual JWT authentication token obtained from the login endpoint.

---

## Authentication

### 1. Admin Login

Login endpoint for Ressy Administrators. Returns JWT token for authenticated admin users.

**Endpoint:** `POST /api/v1/admin/login`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/admin/login' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--data-urlencode 'username=admin@example.com' \
--data-urlencode 'password=your_password'
```

**Alternative (using form data):**
```bash
curl --location 'http://localhost:5001/api/v1/admin/login' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--data 'username=admin@example.com&password=your_password'
```

**Request Parameters:**
- `username` (required): Admin email address
- `password` (required): Admin password

**Response Example:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJlbWFpbCI6ImFkbWluQGV4YW1wbGUuY29tIiwicm9sZSI6ImFkbWluIiwidHlwZSI6ImFkbWluIn0...",
  "token_type": "bearer"
}
```

**Error Responses:**
- `401 Unauthorized`: Incorrect email or password
```json
{
  "detail": "Incorrect email or password"
}
```

---

## User Management

### 2. Get All Users

Get all users in the system (Admin only).

**Endpoint:** `GET /api/v1/admin/users`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/admin/users' \
--header 'Authorization: Bearer {token}'
```

**Example:**
```bash
curl --location 'http://localhost:5001/api/v1/admin/users' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

**Response Example:**
```json
{
  "message": "Admin endpoint - implement user listing"
}
```

---

## Restaurant Management

### 3. Create Restaurant

Create a new restaurant with all necessary details.

**Endpoint:** `POST /api/v1/admin/restaurants`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "name": "The Gourmet Restaurant",
    "address": "123 Main Street, City, State 12345",
    "phone_number": "+1-555-123-4567",
    "twilio_phone_number": "+1-555-987-6543",
    "twilio_details": {
        "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "auth_token": "your_auth_token",
        "api_key": "your_api_key"
    },
    "deepgram_details": {
        "api_key": "your_deepgram_api_key",
        "model": "nova-2",
        "language": "en-US"
    },
    "open_table_details": {
        "restaurant_id": "1074796",
        "bearer_token": "your_opentable_token"
    },
    "forward_minutes": 1440,
    "backward_minutes": 0,
    "is_credit_card_required_for_reservation": false
}'
```

**Example (Minimal - only required fields):**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
--data '{
    "name": "The Gourmet Restaurant"
}'
```

**Request Body:**
- `name` (required, string, max 255 chars): Restaurant name
- `address` (optional, text): Restaurant address
- `phone_number` (optional, string, max 20 chars): Phone number
- `twilio_phone_number` (optional, string, max 20 chars): Twilio phone number
- `twilio_details` (optional, JSON object): Twilio configuration
- `deepgram_details` (optional, JSON object): Deepgram configuration
- `open_table_details` (optional, JSON object): OpenTable integration details
- `forward_minutes` (optional, integer, default 0): Forward booking window in minutes
- `backward_minutes` (optional, integer, default 0): Backward booking window in minutes
- `is_credit_card_required_for_reservation` (optional, boolean, default false): Require credit card for reservation

**Response Example (201 Created):**
```json
{
  "id": 1,
  "name": "The Gourmet Restaurant",
  "address": "123 Main Street, City, State 12345",
  "phone_number": "+1-555-123-4567",
  "twilio_phone_number": "+1-555-987-6543",
  "twilio_details": {
    "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "auth_token": "your_auth_token",
    "api_key": "your_api_key"
  },
  "deepgram_details": {
    "api_key": "your_deepgram_api_key",
    "model": "nova-2",
    "language": "en-US"
  },
  "open_table_details": {
    "restaurant_id": "1074796",
    "bearer_token": "your_opentable_token"
  },
  "forward_minutes": 1440,
  "backward_minutes": 0,
  "is_credit_card_required_for_reservation": false,
  "created_at": "2025-01-15T10:30:00",
  "updated_at": "2025-01-15T10:30:00"
}
```

**Error Responses:**
- `400 Bad Request`: Validation error
```json
{
  "detail": "name is required"
}
```
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not authorized (insufficient role)

---

### 4. Get All Restaurants

Get all restaurants with pagination, search, and filtering.

**Endpoint:** `GET /api/v1/admin/restaurants`

**cURL (Basic):**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants' \
--header 'Authorization: Bearer {token}'
```

**cURL (With Pagination):**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants?page=1&limit=20' \
--header 'Authorization: Bearer {token}'
```

**cURL (With Search):**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants?search=Gourmet&page=1&limit=20' \
--header 'Authorization: Bearer {token}'
```

**cURL (With Filtering):**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants?is_credit_card_required=true&page=1&limit=20' \
--header 'Authorization: Bearer {token}'
```

**cURL (Combined):**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants?page=1&limit=20&search=Gourmet&is_credit_card_required=false' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

**Query Parameters:**
- `page` (optional, default 1, min 1): Page number
- `limit` (optional, default 20, min 1, max 100): Items per page
- `search` (optional): Search by restaurant name (partial match)
- `is_credit_card_required` (optional, boolean): Filter by credit card requirement

**Response Example:**
```json
{
  "data": [
    {
      "id": 1,
      "name": "The Gourmet Restaurant",
      "address": "123 Main Street, City, State 12345",
      "phone_number": "+1-555-123-4567",
      "twilio_phone_number": "+1-555-987-6543",
      "twilio_details": {
        "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      },
      "deepgram_details": {
        "api_key": "your_deepgram_api_key"
      },
      "open_table_details": {
        "restaurant_id": "1074796"
      },
      "forward_minutes": 1440,
      "backward_minutes": 0,
      "is_credit_card_required_for_reservation": false,
      "created_at": "2025-01-15T10:30:00",
      "updated_at": "2025-01-15T10:30:00"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20,
  "total_pages": 1
}
```

**Error Responses:**
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not authorized

---

### 5. Get Restaurant by ID

Get complete restaurant details by ID.

**Endpoint:** `GET /api/v1/admin/restaurants/{id}`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Authorization: Bearer {token}'
```

**Example:**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

**Path Parameters:**
- `id` (required, integer): Restaurant ID

**Response Example:**
```json
{
  "id": 1,
  "name": "The Gourmet Restaurant",
  "address": "123 Main Street, City, State 12345",
  "phone_number": "+1-555-123-4567",
  "twilio_phone_number": "+1-555-987-6543",
  "twilio_details": {
    "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "auth_token": "your_auth_token",
    "api_key": "your_api_key"
  },
  "deepgram_details": {
    "api_key": "your_deepgram_api_key",
    "model": "nova-2",
    "language": "en-US"
  },
  "open_table_details": {
    "restaurant_id": "1074796",
    "bearer_token": "your_opentable_token"
  },
  "forward_minutes": 1440,
  "backward_minutes": 0,
  "is_credit_card_required_for_reservation": false,
  "created_at": "2025-01-15T10:30:00",
  "updated_at": "2025-01-15T10:30:00"
}
```

**Error Responses:**
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not authorized
- `404 Not Found`: Restaurant not found
```json
{
  "detail": "Restaurant not found"
}
```

---

### 6. Update Restaurant

Update restaurant details. Accepts partial updates - only provided fields will be updated.

**Endpoint:** `PUT /api/v1/admin/restaurants/{id}`

**cURL (Update Name Only):**
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "name": "The Updated Gourmet Restaurant"
}'
```

**cURL (Update Multiple Fields):**
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "name": "The Updated Gourmet Restaurant",
    "address": "456 New Street, City, State 12345",
    "phone_number": "+1-555-999-8888",
    "forward_minutes": 2880,
    "is_credit_card_required_for_reservation": true
}'
```

**cURL (Update Integration Details):**
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
--data '{
    "twilio_details": {
        "account_sid": "ACyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
        "auth_token": "new_auth_token",
        "api_key": "new_api_key"
    },
    "deepgram_details": {
        "api_key": "new_deepgram_api_key",
        "model": "nova-3",
        "language": "en-US"
    }
}'
```

**Path Parameters:**
- `id` (required, integer): Restaurant ID

**Request Body (All fields optional):**
- `name` (optional, string, max 255 chars): Restaurant name
- `address` (optional, text): Restaurant address
- `phone_number` (optional, string, max 20 chars): Phone number
- `twilio_phone_number` (optional, string, max 20 chars): Twilio phone number
- `twilio_details` (optional, JSON object): Twilio configuration
- `deepgram_details` (optional, JSON object): Deepgram configuration
- `open_table_details` (optional, JSON object): OpenTable integration details
- `forward_minutes` (optional, integer, min 0): Forward booking window in minutes
- `backward_minutes` (optional, integer, min 0): Backward booking window in minutes
- `is_credit_card_required_for_reservation` (optional, boolean): Require credit card for reservation

**Response Example (200 OK):**
```json
{
  "id": 1,
  "name": "The Updated Gourmet Restaurant",
  "address": "456 New Street, City, State 12345",
  "phone_number": "+1-555-999-8888",
  "twilio_phone_number": "+1-555-987-6543",
  "twilio_details": {
    "account_sid": "ACyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
    "auth_token": "new_auth_token",
    "api_key": "new_api_key"
  },
  "deepgram_details": {
    "api_key": "new_deepgram_api_key",
    "model": "nova-3",
    "language": "en-US"
  },
  "open_table_details": {
    "restaurant_id": "1074796",
    "bearer_token": "your_opentable_token"
  },
  "forward_minutes": 2880,
  "backward_minutes": 0,
  "is_credit_card_required_for_reservation": true,
  "created_at": "2025-01-15T10:30:00",
  "updated_at": "2025-01-15T11:45:00"
}
```

**Error Responses:**
- `400 Bad Request`: Validation error
```json
{
  "detail": "forward_minutes must be a non-negative integer"
}
```
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not authorized
- `404 Not Found`: Restaurant not found

---

### 7. Delete Restaurant

Delete a restaurant by ID. Cascade deletion will handle associated data automatically.

**Endpoint:** `DELETE /api/v1/admin/restaurants/{id}`

**cURL:**
```bash
curl --location --request DELETE 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Authorization: Bearer {token}'
```

**Example:**
```bash
curl --location --request DELETE 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

**Path Parameters:**
- `id` (required, integer): Restaurant ID

**Response Example (200 OK):**
```json
{
  "message": "Restaurant deleted successfully"
}
```

**Error Responses:**
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not authorized
- `404 Not Found`: Restaurant not found
- `500 Internal Server Error`: Failed to delete restaurant

---

### 8. Get Restaurant Statistics

Get comprehensive statistics for a restaurant.

**Endpoint:** `GET /api/v1/admin/restaurants/{id}/stats`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants/1/stats' \
--header 'Authorization: Bearer {token}'
```

**Example:**
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants/1/stats' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

**Path Parameters:**
- `id` (required, integer): Restaurant ID

**Response Example:**
```json
{
  "total_menu_items": 45,
  "available_menu_items": 42,
  "special_items_count": 5,
  "total_faqs": 12,
  "total_administrators": 3,
  "total_calls": 156,
  "total_minute_usage": 2340.5
}
```

**Response Fields:**
- `total_menu_items` (integer): Total number of menu items
- `available_menu_items` (integer): Number of available menu items (is_available = TRUE)
- `special_items_count` (integer): Number of special items (is_special = TRUE)
- `total_faqs` (integer): Total number of FAQs
- `total_administrators` (integer): Total number of restaurant administrators
- `total_calls` (integer): Total number of calls
- `total_minute_usage` (float): Total minute usage (sum of call_duration in minutes)

**Error Responses:**
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not authorized
- `404 Not Found`: Restaurant not found

---

## Complete Flow Example

Here's a complete example of managing a restaurant:

### Step 1: Login
```bash
curl --location 'http://localhost:5001/api/v1/admin/login' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--data-urlencode 'username=admin@example.com' \
--data-urlencode 'password=your_password'
```

Save the `access_token` from the response.

### Step 2: Create Restaurant
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE' \
--data '{
    "name": "The Gourmet Restaurant",
    "address": "123 Main Street",
    "phone_number": "+1-555-123-4567",
    "twilio_phone_number": "+1-555-987-6543",
    "forward_minutes": 1440,
    "backward_minutes": 0
}'
```

Save the `id` from the response (e.g., `1`).

### Step 3: Get Restaurant Details
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE'
```

### Step 4: Update Restaurant
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE' \
--data '{
    "forward_minutes": 2880,
    "is_credit_card_required_for_reservation": true
}'
```

### Step 5: Get Restaurant Statistics
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants/1/stats' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE'
```

### Step 6: List All Restaurants
```bash
curl --location 'http://localhost:5001/api/v1/admin/restaurants?page=1&limit=20' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE'
```

### Step 7: Delete Restaurant (if needed)
```bash
curl --location --request DELETE 'http://localhost:5001/api/v1/admin/restaurants/1' \
--header 'Authorization: Bearer YOUR_TOKEN_HERE'
```

---

## Authentication

All endpoints (except login) require JWT authentication. Include the token in the `Authorization` header:

```
Authorization: Bearer {your_jwt_token}
```

The token is obtained from the `/api/v1/admin/login` endpoint and expires after 24 hours (configurable).

---

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "Validation error message"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated as admin"
}
```
or
```json
{
  "detail": "Token expired"
}
```

### 403 Forbidden
```json
{
  "detail": "Not authorized - insufficient role"
}
```

### 404 Not Found
```json
{
  "detail": "Restaurant not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error message describing the server error"
}
```

---

## Notes

1. **Token Expiration**: JWT tokens expire after 24 hours by default. You'll need to login again to get a new token.

2. **Pagination**: The `limit` parameter has a maximum value of 100. If you need more results, use pagination.

3. **Search**: The search parameter performs a partial match on restaurant names (case-insensitive).

4. **Partial Updates**: The update endpoint accepts partial updates. Only include the fields you want to change.

5. **JSON Fields**: Integration details (`twilio_details`, `deepgram_details`, `open_table_details`) are stored as JSON objects. Ensure proper JSON formatting when sending these fields.

6. **Cascade Deletion**: When deleting a restaurant, associated data (menus, FAQs, orders, etc.) will be automatically deleted due to foreign key constraints.

7. **Phone Number Format**: Phone numbers should be in a valid format (max 20 characters). The system accepts various formats including international formats.

8. **Minute Values**: `forward_minutes` and `backward_minutes` must be non-negative integers (0 or greater).

9. **Statistics**: The statistics endpoint provides real-time counts from the database. These values may change as data is added or removed.

10. **Role-Based Access**: All endpoints require the "admin" role. Ensure your admin user has the appropriate role assigned in the `Crm_roles` table.

