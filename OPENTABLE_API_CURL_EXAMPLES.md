# OpenTable API - cURL Examples

This document contains cURL examples for all OpenTable API endpoints.

**Base URL**: `http://localhost:5001/api/v1/opentable`

**Note**: Replace `{token}` with your actual JWT authentication token and `{restaurant_id}` with your internal restaurant ID.

---

## 1. Get Table Availability

Get available table times for a restaurant.

### Request
```bash
curl --location -g 'http://localhost:5001/api/v1/opentable/availability/{restaurant_id}/{rid}?start_date_time=2025-03-05T12:00&forward_minutes=60&backward_minutes=30&party_size=2&require_attributes=default&include_credit_card_results=true&include_experiences=false' \
--header 'Authorization: Bearer {token}'
```

### Example
```bash
curl --location -g 'http://localhost:5001/api/v1/opentable/availability/1/1074796?start_date_time=2025-03-05T12:00&forward_minutes=60&backward_minutes=30&party_size=2&require_attributes=default&include_credit_card_results=true&include_experiences=false' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

### Query Parameters
- `start_date_time` (required): Start date and time in format `yyyy-mm-ddThh:ss` (e.g., `2025-03-05T12:00`)
- `forward_minutes` (optional): Forward booking window in minutes
- `backward_minutes` (optional): Backward booking window in minutes
- `party_size` (optional): Party size (must be > 0)
- `require_attributes` (optional): Table types (comma-separated, e.g., `default,window`)
- `include_credit_card_results` (optional): Include credit card results (`true` or `false`)
- `include_experiences` (optional): Include experiences (`true` or `false`)

### Response Example
```json
{
  "rid": 1074796,
  "party_size": 2,
  "times": [
    "2025-03-05T07:00",
    "2025-03-05T07:15",
    "2025-03-05T07:30"
  ],
  "times_available": [
    {
      "time": "2025-03-05T07:00",
      "availability_types": [
        {
          "type": "Standard",
          "cancellationPolicy": {},
          "diningArea": [
            {
              "id": 1,
              "attributes": ["default"],
              "environment": "Indoor",
              "booking_url": "https://www.opentable.com/book/validate?...",
              "booking_restref_url": "https://www.opentable.com/restref/client?..."
            }
          ]
        }
      ]
    }
  ],
  "no_availability_reasons": [],
  "href": "https://platform.otqa.com/sync/listings/1074796"
}
```

---

## 2. Lock a Booking Slot

Lock a booking slot before creating a reservation.

### Request
```bash
curl --location 'http://localhost:5001/api/v1/opentable/booking/{restaurant_id}/{rid}/slot_locks' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "party_size": 2,
    "date_time": "2025-10-13T16:00",
    "reservation_attribute": "default",
    "experience": {
        "id": 512031,
        "version": 1,
        "party_size_per_price_type": [
            {
                "id": 121058,
                "count": 1
            },
            {
                "id": 121059,
                "count": 1
            }
        ],
        "add_ons": [
            {
                "item_id": "4cb68e46-39be-4110-b345-884bf57635bd",
                "quantity": 2
            }
        ]
    },
    "dining_area_id": 2632,
    "environment": "Indoor"
}'
```

### Example (Minimal)
```bash
curl --location 'http://localhost:5001/api/v1/opentable/booking/1/1074796/slot_locks' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
--data '{
    "party_size": 2,
    "date_time": "2025-10-13T16:00",
    "reservation_attribute": "default"
}'
```

### Request Body
- `party_size` (required): Party size (must be > 0)
- `date_time` (required): Date and time in format `yyyy-mm-ddThh:ss`
- `reservation_attribute` (optional, default: "default"): Reservation attribute
- `experience` (optional): Experience details object
- `dining_area_id` (optional): Dining area ID
- `environment` (optional): Environment (e.g., "Indoor", "Outdoor")

### Response Example
```json
{
  "expires_at": "2025-01-06T21:24:50",
  "reservation_token": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiI2MTc3MzgxNDJ8MnwyMDI1LTEwLTEzVDE2OjAwfDEwMzgwMDcifQ.6uVQiE9gzI8nRxIP0qUjP2o__5pwV7DwYeW_0-VPq8oJUvltg-HIj8iel3acYzWeKZuQqLHNiBQ3VlSVeONYGQ"
}
```

---

## 3. Create a Reservation

Create a reservation using a reservation token from slot lock.

### Request
```bash
curl --location 'http://localhost:5001/api/v1/opentable/booking/{restaurant_id}/{rid}/reservations' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "reservation_token": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiI2MTc3MzgxNDJ8MnwyMDI1LTEwLTEzVDE2OjAwfDEwMzgwMDcifQ.6uVQiE9gzI8nRxIP0qUjP2o__5pwV7DwYeW_0-VPq8oJUvltg-HIj8iel3acYzWeKZuQqLHNiBQ3VlSVeONYGQ",
    "first_name": "Jane",
    "last_name": "Doe",
    "email_address": "JaneDoe@mailanator.com",
    "phone": {
        "number": "4155555555",
        "country_code": "US",
        "phone_type": "mobile"
    },
    "reservation_attribute": "default",
    "special_request": "This is my special request",
    "credit_card": {
        "token": "tok_0SDBnhjrulGLaJAMRTatEB0N",
        "last4": "4242"
    },
    "restaurant_email_marketing_opt_in": "true",
    "dining_area_id": "2632",
    "environment": "Indoor",
    "experience": {
        "id": 512031,
        "version": 1,
        "party_size_per_price_type": [
            {
                "id": 121058,
                "count": 1
            },
            {
                "id": 121059,
                "count": 1
            }
        ],
        "add_ons": [
            {
                "item_id": "4cb68e46-39be-4110-b345-884bf57635bd",
                "quantity": 2
            }
        ]
    }
}'
```

### Example (Minimal)
```bash
curl --location 'http://localhost:5001/api/v1/opentable/booking/1/1074796/reservations' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
--data '{
    "reservation_token": "eyJhbGciOiJIUzUxMiJ9...",
    "first_name": "Jane",
    "last_name": "Doe",
    "email_address": "jane.doe@example.com",
    "phone": {
        "number": "4155555555",
        "country_code": "US",
        "phone_type": "mobile"
    }
}'
```

### Request Body
- `reservation_token` (required): Token from slot lock
- `first_name` (required): First name (min length: 1)
- `last_name` (required): Last name (min length: 1)
- `email_address` (required): Email address
- `phone` (required): Phone object with `number`, `country_code`, `phone_type`
- `reservation_attribute` (optional, default: "default"): Reservation attribute
- `special_request` (optional): Special request text
- `credit_card` (optional): Credit card object with `token` and `last4`
- `restaurant_email_marketing_opt_in` (optional): Marketing opt-in ("true" or "false")
- `dining_area_id` (optional): Dining area ID
- `environment` (optional): Environment
- `experience` (optional): Experience details object

### Response Example
```json
{
  "message": "We have a 5 minute grace period. Please call us if you are running later than 5 minutes after your reservation time.<br /><br />We may contact you about this reservation, so please ensure your email and phone number are up to date.<br /><br />Your table will be reserved for 1 hour 30 minutes for parties of up to 2; 2 hours for parties of up to 4; 2 hours 30 minutes for parties of up to 6; and 3 hours for parties of 7+.",
  "confirmation_number": 1751,
  "offer_confirmation_number": 0,
  "date_time": "2025-10-13T16:00",
  "party_size": 2,
  "notes": "This is my special request",
  "manage_reservation_url": "https://www.opentable.com/book/view?rid=1038007&confnumber=1751&token=01EMM9tRYsZ5LWf59HhG_iCHIzHSs1Spu-9JvrwKx0nzI1"
}
```

---

## 4. Update a Reservation

Update an existing reservation.

### Request
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/opentable/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "party_size": 2,
    "date_time": "2025-11-13T16:00",
    "reservation_attribute": "default",
    "reservation_token": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiI5OTgyNjg2Mzd8MnwyMDI1LTExLTEzVDE2OjAwfDEwMzgwMDcifQ.SEmbFYjVeGjmFzh987EzHCjg6Gwg0sK8lDPlHbj7Ca0zYlfJAJyZGNLWmHgVkLXvVAYVTPNiejZ6znJ2jG5WUQ",
    "special_request": "Window Table",
    "experience": {
        "id": 512031,
        "version": 1,
        "party_size_per_price_type": [
            {
                "id": 121058,
                "count": 1
            },
            {
                "id": 121059,
                "count": 1
            }
        ],
        "add_ons": [
            {
                "item_id": "4cb68e46-39be-4110-b345-884bf57635bd",
                "quantity": 2
            }
        ]
    }
}'
```

### Example (Minimal)
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/opentable/booking/1/1074796/reservations/1751' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
--data '{
    "date_time": "2025-11-13T16:00",
    "special_request": "Window Table"
}'
```

### Path Parameters
- `restaurant_id`: Internal restaurant ID
- `rid`: OpenTable restaurant ID
- `confirmation_id`: Confirmation number from the reservation

### Request Body (All fields optional)
- `party_size` (optional): New party size (must be > 0)
- `date_time` (optional): New date and time in format `yyyy-mm-ddThh:ss`
- `reservation_attribute` (optional): Reservation attribute
- `reservation_token` (optional): Reservation token (required if changing date/time)
- `special_request` (optional): Special request text
- `experience` (optional): Experience details object

### Response Example
```json
{
  "message": "We have a 5 minute grace period. Please call us if you are running later than 5 minutes after your reservation time.<br /><br />We may contact you about this reservation, so please ensure your email and phone number are up to date.<br /><br />Your table will be reserved for 1 hour 30 minutes for parties of up to 2; 2 hours for parties of up to 4; 2 hours 30 minutes for parties of up to 6; and 3 hours for parties of 7+.",
  "confirmation_number": 1751,
  "date_time": "2025-11-13T16:00",
  "party_size": 2,
  "notes": "Window Table"
}
```

---

## 5. Cancel a Reservation

Cancel an existing reservation.

### Request
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/opentable/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}/cancel' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}'
```

### Example
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/opentable/booking/1/1074796/reservations/1751/cancel' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

### Path Parameters
- `restaurant_id`: Internal restaurant ID
- `rid`: OpenTable restaurant ID
- `confirmation_id`: Confirmation number from the reservation

### Response Example
```json
{
  "success": true,
  "message": "Reservation cancelled successfully"
}
```

---

## Authentication

All endpoints require JWT authentication. Include the token in the `Authorization` header:

```
Authorization: Bearer {your_jwt_token}
```

To get a token, use the authentication endpoint:
```bash
curl --location 'http://localhost:5001/api/v1/auth/login' \
--header 'Content-Type: application/json' \
--data '{
    "username": "your_username",
    "password": "your_password"
}'
```

---

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "Error message describing what went wrong"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
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

1. **Date/Time Format**: All date/time values should be in format `yyyy-mm-ddThh:ss` (e.g., `2025-03-05T12:00`)
2. **URL Encoding**: When using query parameters with special characters, ensure proper URL encoding (e.g., `%3A` for `:`)
3. **Restaurant Configuration**: Ensure the restaurant has OpenTable configuration in the `open_table_details` JSON field:
   ```json
   {
     "base_url": "https://platform.otqa.com/sync",
     "bearer_token": "your_bearer_token"
   }
   ```
4. **Reservation Flow**: The typical flow is:
   - Get availability → Lock slot → Create reservation
   - To update: Update reservation (may need new slot lock if changing time)
   - To cancel: Cancel reservation


