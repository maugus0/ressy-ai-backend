# Square Integration Guide For A Restaurant

This guide is for RessyAI developers or operations staff who need to connect a restaurant to Square without a dedicated dashboard UI. Everything below can be done from the Square dashboard plus RessyAI Swagger/OpenAPI or direct HTTP calls.

## Outcome

When setup is complete:

1. RessyAI can submit pickup orders to Square.
2. RessyAI can cancel or replace POS-backed orders in Square.
3. Square catalog and availability changes can sync into RessyAI asynchronously.
4. Live calls continue to read menu data from RessyAI internal tables, not from Square in real time.

## What You Need Before Starting

From RessyAI:

- `restaurant_id`
- an `admin` or `client` JWT for `/api/v1/dashboard/*`
- the public backend base URL, for example `https://api.example.com`

From Square:

- a Square app for the correct environment (`Sandbox` or production)
- a Square access token for the seller account
- the Square `location_id` for the restaurant
- the webhook signature key for the webhook subscription

Recommended Square permissions:

- `MERCHANT_PROFILE_READ`
- `ORDERS_WRITE`
- `ORDERS_READ`

If you want sold-out / availability sync to behave correctly, the relevant item variations and modifiers must also be configured in Square so availability changes are actually reflected in provider data.

## Backend Environment

Make sure these backend environment variables are correct before testing webhooks:

```env
PUBLIC_BASE_URL=https://api.example.com
SQUARE_API_BASE_URL=https://connect.squareup.com
SQUARE_WEBHOOK_SIGNATURE_KEY=...
SQUARE_WEBHOOK_NOTIFICATION_URL=https://api.example.com/api/v1/webhooks/square
```

Notes:

- For sandbox, use `https://connect.squareupsandbox.com` as the Square API base URL.
- `SQUARE_WEBHOOK_NOTIFICATION_URL` should exactly match the notification URL configured in Square.
- If `SQUARE_WEBHOOK_NOTIFICATION_URL` is not set, the backend validates against `PUBLIC_BASE_URL + /api/v1/webhooks/square`.

## Step 1: Get The Square Access Token

Use the Square Developer Console for the correct environment:

1. Open the Square Developer Console.
2. Select the app.
3. Switch to `Sandbox` or production.
4. Authorize the seller account with the required scopes if you are using OAuth test-account authorization.
5. Copy the access token that will be stored in RessyAI.

For sandbox testing, the seller account must belong to the same sandbox app/account context as the token.

## Step 2: Find The Correct `location_id`

The `location_id` must belong to the same seller account as the token.

Use Square `ListLocations` with the exact access token you plan to store in RessyAI:

```bash
curl https://connect.squareupsandbox.com/v2/locations \
  -H "Authorization: Bearer <square_access_token>" \
  -H "Square-Version: 2026-01-22"
```

Example response:

```json
{
  "locations": [
    {
      "id": "LAGN23F43WS06",
      "name": "Ressy's Diner",
      "merchant_id": "ML35Y5E33A17W",
      "currency": "CAD",
      "status": "ACTIVE"
    }
  ]
}
```

Record:

- `location_id`
- `merchant_id`
- `currency`

Important:

- `location_id` is entered manually when creating the RessyAI POS integration.
- `external_account_id` is backfilled automatically during the first successful catalog sync. You do not need to set it through the API.

## Step 3: Configure Square Webhooks

Create a Square webhook subscription pointing to:

```text
POST https://api.example.com/api/v1/webhooks/square
```

Subscribe to these events:

- `catalog.version.updated`
- `inventory.count.updated`

Then copy the webhook signature key into:

```env
SQUARE_WEBHOOK_SIGNATURE_KEY=...
```

Why these events matter:

- `catalog.version.updated` is used to trigger targeted catalog availability refreshes.
- `inventory.count.updated` captures stock-related availability changes.

Square retries failed webhook deliveries automatically. RessyAI persists incoming events in `POS_Webhook_Events` and handles duplicate deliveries idempotently.

## Step 4: Open Swagger And Authorize

In the backend Swagger UI:

1. Open `/docs`.
2. Click `Authorize`.
3. Paste the JWT from an `admin` or `client` account.

Role behavior:

- `admin` can manage integrations for any restaurant.
- `client` can only manage integrations for its own restaurant.

All integration-management endpoints are under:

```text
/api/v1/dashboard
```

## Step 5: Create The Square POS Integration In RessyAI

Create the integration with:

```text
POST /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations
```

Example request body:

```json
{
  "pos_type": "SQUARE",
  "enabled": true,
  "credentials": {
    "access_token": "<square_access_token>"
  },
  "location_id": "LAGN23F43WS06",
  "currency": "CAD",
  "default_order_options": {}
}
```

Equivalent `curl`:

```bash
curl -X POST "https://api.example.com/api/v1/dashboard/restaurants/9/pos-integrations" \
  -H "Authorization: Bearer <ressy_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "pos_type": "SQUARE",
    "enabled": true,
    "credentials": {
      "access_token": "<square_access_token>"
    },
    "location_id": "LAGN23F43WS06",
    "currency": "CAD",
    "default_order_options": {}
  }'
```

Example response:

```json
{
  "id": 1,
  "restaurant_id": 9,
  "pos_type": "SQUARE",
  "enabled": true,
  "credentials": {
    "access_token": "<square_access_token>"
  },
  "location_id": "LAGN23F43WS06",
  "external_account_id": null,
  "currency": "CAD",
  "default_order_options": {},
  "created_at": "2026-03-25T10:00:00",
  "updated_at": "2026-03-25T10:00:00"
}
```

Save the returned `id`. You will need it for sync/admin/archive endpoints.

Current API behavior to know about:

- `GET /restaurants/{restaurant_id}/pos-integrations` currently returns enabled integrations only.
- If you later disable the integration, keep the `pos_integration_id` from the create response so you can update it again.

## Step 6: Trigger The First Catalog Sync

Run the initial import:

```text
POST /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-catalog
```

Example:

```bash
curl -X POST "https://api.example.com/api/v1/dashboard/restaurants/9/pos-integrations/1/sync-catalog" \
  -H "Authorization: Bearer <ressy_jwt>"
```

This imports the provider catalog into the internal tables and usually backfills:

- `POS_Integrations.external_account_id`
- menu item mappings
- option group mappings
- option value mappings

## Step 7: Review Sync Results

List recent sync runs:

```text
GET /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-runs
```

Get a specific run with attached issues:

```text
GET /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-runs/{sync_run_id}
```

List open issues:

```text
GET /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-issues
```

Update an issue status:

```text
PATCH /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-issues/{issue_id}
```

Example body:

```json
{
  "status": "ACKNOWLEDGED"
}
```

Valid issue statuses are:

- `OPEN`
- `ACKNOWLEDGED`
- `RESOLVED`
- `IGNORED`

## Step 8: Review Inactive Imported Catalog Rows

If an imported object disappears from Square or becomes unmapped, inspect inactive rows with:

```text
GET /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/inactive-catalog
```

This is useful when a restaurant reports that something used to exist in Square but is no longer visible or orderable in RessyAI.

## Step 9: Optional Archive / Restore Workflow

Before a risky import or restaurant migration, archive the current internal catalog state:

```text
POST /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/archives
```

Example request:

```json
{
  "label": "Pre-Square cutover",
  "notes": "Backup before first production import",
  "deactivate_current_catalog": false
}
```

List archives:

```text
GET /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/archives
```

Restore an archive:

```text
POST /api/v1/dashboard/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/archives/{archive_id}/restore
```

Use restore if an import introduced the wrong catalog state and you need to roll internal tables back quickly.

## Step 10: Verify Webhook Delivery

After the integration and first sync are live:

1. Change an item or variation in Square.
2. Or change inventory / sold-out state in Square.
3. Confirm Square sends a webhook to `POST /api/v1/webhooks/square`.

What to expect:

- the webhook endpoint should return `200`
- the event is stored in `POS_Webhook_Events`
- background processing either triggers an availability sync or a wider catalog sync

Common setup for sold-out testing:

1. Open the item variation in Square.
2. Make sure inventory tracking / sold-out behavior is actually configured for that variation.
3. Mark it sold out or change stock so Square emits the relevant event and availability data.

Important product behavior:

- live voice calls do not call Square for menu availability
- availability must first sync into RessyAI internal tables

## Step 11: Verify Order Submission

Once catalog sync is healthy:

1. Place a test order through the normal RessyAI flow.
2. Confirm the order reaches Square.
3. Confirm payment and pickup flow appear correctly in Square.
4. Confirm cancel / replace flows work if you test modifications or cancellations.

Current backend behavior:

- voice orders wait for POS confirmation before the caller hears a final confirmation
- transient Square failures get one immediate retry in-process
- if the order still cannot be confirmed, the call is escalated instead of silently leaving a background retry that could create ghost orders

## Updating Or Disabling The Integration

Update the integration:

```text
PUT /api/v1/dashboard/pos-integrations/{pos_integration_id}
```

Example:

```json
{
  "enabled": false
}
```

Delete the integration:

```text
DELETE /api/v1/dashboard/pos-integrations/{pos_integration_id}
```

Use delete only if you really want to remove the integration row. For most operational changes, `enabled=false` is safer.

## Troubleshooting

### `403` from Square when creating orders

Usually one of these:

- token and `location_id` belong to different Square seller accounts
- token is missing required Square permissions
- the wrong environment is being used

First check `ListLocations` with the exact token stored in RessyAI.

### `403` on `POST /api/v1/webhooks/square`

Usually one of these:

- wrong `SQUARE_WEBHOOK_SIGNATURE_KEY`
- `SQUARE_WEBHOOK_NOTIFICATION_URL` does not exactly match the URL configured in Square
- `PUBLIC_BASE_URL` does not reflect the real public URL used by Square

### Webhook returns `200` but availability did not change

Check the provider data, not just the webhook status.

Possible causes:

- the Square variation is not configured to expose sold-out state
- inventory tracking is not enabled for that variation
- the provider object does not yet contain `location_overrides.sold_out`

The webhook only triggers processing. RessyAI changes availability only when the provider data actually says the item or modifier is unavailable.

### Catalog import succeeded but mapping/issues exist

Use:

- sync runs
- sync issues
- inactive catalog

These endpoints are the primary manual debugging tools until there is a dedicated integrations UI.

## Optional SQL Checks

If you need to verify state directly in the database:

```sql
SELECT * FROM POS_Integrations WHERE restaurant_id = 9;
SELECT * FROM POS_Catalog_Sync_Runs WHERE pos_integration_id = 1 ORDER BY id DESC;
SELECT * FROM POS_Catalog_Sync_Issues WHERE pos_integration_id = 1 ORDER BY id DESC;
SELECT * FROM POS_Webhook_Events ORDER BY id DESC;
SELECT * FROM Order_POS_Sync WHERE restaurant_id = 9 ORDER BY id DESC;
```

## Relevant Internal Files

These are the main backend files involved in the Square integration:

- `app/api/pos_integrations.py`
- `app/api/pos_webhooks.py`
- `app/integrations/square_client.py`
- `app/integrations/pos/square_provider.py`
- `app/services/pos_catalog_import_service.py`
- `app/services/pos_catalog_background_sync.py`
- `app/services/pos_webhook_event_service.py`
- `app/services/pos_service.py`
- `app/services/pos_retry_service.py`

## External References

- Square Locations API: https://developer.squareup.com/docs/locations-api
- Square ListLocations reference: https://developer.squareup.com/reference/square/locations/list-locations
- Square sandbox seller authorization: https://developer.squareup.com/docs/testing/create-and-authorize-sandbox-account
- Square catalog webhooks: https://developer.squareup.com/docs/catalog-api/webhooks
- Square inventory webhooks: https://developer.squareup.com/docs/inventory-api/webhooks
- Square sold-out monitoring: https://developer.squareup.com/docs/inventory-api/monitor-sold-out-status-on-item-variation
- Square webhook validation: https://developer.squareup.com/docs/webhooks/step3validate

