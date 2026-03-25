# Future POS Provider Integration Guide

This guide is for the developer or coding agent who needs to add the next POS provider after Square, for example Toast. It explains the current abstraction, the tables that already exist, the places that are still Square-first, and the flows that must be validated before shipping.

## Design Goal

The current backend is intentionally built so that:

1. live calls read only internal catalog tables
2. provider catalog fetches happen asynchronously
3. provider-specific logic lives behind a shared adapter interface
4. order submission, cancellation, retry, sync tracking, and rollback use generic tables

Do not reintroduce a separate provider-specific data model unless absolutely necessary.

## Current Mental Model

Treat the POS integration stack as three layers:

1. Provider adapter layer
   - provider-specific HTTP client
   - provider-specific normalization into shared DTOs

2. Generic POS orchestration layer
   - catalog import
   - webhook ingestion and retry
   - order submit/cancel/retry
   - archive / restore

3. Internal restaurant runtime layer
   - `Menus`
   - `Menu_Option_Groups`
   - `Menu_Option_Values`
   - `Menu_Item_Option_Groups`
   - snapshot tables used during ordering and rollback

Live agent functions must continue to read only the internal runtime layer.

## Files You Must Understand First

Core abstractions:

- `app/integrations/pos/base.py`
- `app/integrations/pos/models.py`
- `app/integrations/pos/registry.py`

Current Square implementation:

- `app/integrations/pos/square_provider.py`
- `app/integrations/square_client.py`

Generic orchestration:

- `app/services/pos_catalog_import_service.py`
- `app/services/pos_catalog_background_sync.py`
- `app/services/pos_webhook_event_service.py`
- `app/services/pos_service.py`
- `app/services/pos_retry_service.py`
- `app/services/pos_catalog_admin_service.py`
- `app/services/pos_catalog_archive_service.py`

API entry points:

- `app/api/pos_integrations.py`
- `app/api/pos_webhooks.py`

Order-entry flows that depend on POS behavior:

- `app/agent_fc/functions/orders.py`
- `app/services/dashboard_order_service.py`

## Shared Provider Contract

Every provider implementation must satisfy the `POSProvider` interface in `app/integrations/pos/base.py`.

Required methods:

### `fetch_catalog(integration)`

Use this for full async import into internal tables.

Return:

- `POSCatalogSnapshot`

Responsibilities:

- normalize provider catalog objects into shared DTOs
- preserve provider external ids and source metadata
- emit import issues when the provider data cannot be mapped cleanly

### `fetch_availability_updates(integration, begin_time=None)`

Use this for targeted async availability changes.

Return:

- `POSCatalogAvailabilitySnapshot`

Responsibilities:

- fetch only the provider data needed to refresh availability
- return item and option-value availability keyed by external ids
- keep this separate from the live call path

### `submit_pickup_order(integration, request, idempotency_key=...)`

Use this for initial order submission and replacement order creation.

Return:

- `POSOrderSubmissionResult`

Responsibilities:

- submit the provider order
- collect or record payment if the provider flow requires it
- return `external_order_id`
- return `external_payment_id` if the provider has one
- make provider totals match Ressy snapshots

### `cancel_pickup_order(integration, external_order_id, external_payment_id=None, idempotency_key=..., reason=None)`

Use this for:

- dashboard cancellation
- voice cancellation
- replace-order flows before creating the replacement order

Return:

- `POSOrderCancellationResult`

Responsibilities:

- cancel the provider order or fulfillment in the correct provider-specific way
- refund or void the payment if the provider requires it
- return enough raw payload for debugging / audit

## Shared DTOs

All provider implementations should normalize into the shared dataclasses in `app/integrations/pos/models.py`.

The most important ones are:

- `POSCatalogMenuItem`
- `POSCatalogOptionGroup`
- `POSCatalogOptionValue`
- `POSCatalogAvailabilitySnapshot`
- `POSSubmitOrderRequest`
- `POSOrderLineItem`
- `POSOrderModifierSelection`
- `POSOrderSubmissionResult`
- `POSOrderCancellationResult`

If the new provider needs an extra field, first ask whether it belongs in:

- `metadata`
- a shared DTO field used by multiple providers

Only add new shared fields if the concept is likely to matter beyond one provider.

## Generic Tables Already In Place

Use the existing schema first.

### `POS_Integrations`

Migration: `043_create_pos_integration_tables.sql`

Purpose:

- one row per restaurant/provider pair
- stores credentials, `location_id`, `currency`, provider enablement
- stores `external_account_id` for webhook routing

Important note:

- today the API still validates `pos_type == "SQUARE"` on create
- adding a new provider requires opening that validation up

### `Order_POS_Sync`

Migrations:

- `043_create_pos_integration_tables.sql`
- `049_add_pos_order_management_fields.sql`

Purpose:

- one row per order-to-provider submission attempt
- stores `idempotency_key`
- stores provider status, retry schedule, raw request/response payloads
- stores `external_order_id`
- stores `external_payment_id`

### Internal catalog tables with POS metadata

Migration: `044_add_pos_catalog_metadata.sql`

Tables:

- `Menus`
- `Menu_Option_Groups`
- `Menu_Option_Values`
- `Menu_Item_Option_Groups`

Purpose:

- internal runtime catalog used by calls and dashboards
- imported provider data lands here with `catalog_source = 'POS'`
- source metadata is stored separately from editable display fields
- `is_active` and `is_available` are tracked independently

### Mapping tables

Migration: `045_create_pos_catalog_mapping_tables.sql`

Tables:

- `POS_Menu_Item_Mappings`
- `POS_Option_Group_Mappings`
- `POS_Option_Value_Mappings`

Purpose:

- map internal rows to provider external ids
- allow inactive mappings to remain for traceability
- support replay and rollback even after provider catalog changes

### Sync tracking tables

Migration: `046_create_pos_catalog_sync_tracking.sql`

Tables:

- `POS_Catalog_Sync_Runs`
- `POS_Catalog_Sync_Issues`

Purpose:

- operator-visible history of imports
- structured issues for partial failures or unmapped data

### Archive table

Migration: `047_create_pos_catalog_archives.sql`

Table:

- `POS_Catalog_Archives`

Purpose:

- rollback snapshots of internal catalog state

### Webhook event table

Migration: `048_add_pos_webhook_tracking.sql`

Table:

- `POS_Webhook_Events`

Purpose:

- webhook idempotency
- duplicate delivery handling
- provider retry metadata
- internal retry processing

### Order snapshot fields

Migrations:

- earlier customization migrations for option snapshots
- `049_add_pos_order_management_fields.sql`

Important snapshot fields:

- `Order_Item_Snapshots.external_item_id_snapshot`
- `Order_Item_Options_Snapshots.external_group_id_snapshot`
- `Order_Item_Options_Snapshots.external_value_id_snapshot`

Purpose:

- keep order replay, replace-order rollback, and late retries resilient even if live mappings change

## Current Flow By Concern

### 1. Integration creation

Today:

- API is in `app/api/pos_integrations.py`
- repository is `app/repositories/mysql_pos_integration_repo.py`
- create route currently accepts only `SQUARE`

For a new provider:

1. update request validation
2. define what credentials JSON shape should look like
3. define whether `location_id`, `external_account_id`, or some other routing identifier is required
4. update API docs/examples

### 2. Full catalog import

Primary service:

- `app/services/pos_catalog_import_service.py`

Flow:

1. load integration row
2. resolve provider from registry
3. call `provider.fetch_catalog(...)`
4. upsert internal menu/group/value rows
5. upsert mapping tables
6. mark missing mappings inactive
7. attach groups to items
8. record sync run and issues
9. backfill integration metadata like `external_account_id` when available

Rules:

- preserve internal operator-edited names/descriptions when they differ from stored source fields
- keep provider raw names in `source_*`
- do not let import logic bypass generic tracking tables

### 3. Availability sync

Primary service:

- `app/services/pos_catalog_import_service.py`

Webhook entry point:

- `app/api/pos_webhooks.py`
- `app/services/pos_webhook_event_service.py`

Flow:

1. accept provider webhook
2. validate provider signature
3. persist `POS_Webhook_Events`
4. route to matching integrations by provider account/location identifiers
5. call `provider.fetch_availability_updates(...)`
6. update internal `is_available`

Rules:

- do not fetch provider availability during the call
- do not collapse `is_active` and `is_available`
- keep availability refresh narrow and cheap when the provider supports incremental reads

### 4. Order submission

Primary service:

- `app/services/pos_service.py`

Caller entry points:

- voice: `app/agent_fc/functions/orders.py`
- dashboard: `app/services/dashboard_order_service.py`

Flow:

1. build provider request from internal order snapshots
2. prefer live mappings
3. fall back to snapshot external ids if current mappings changed
4. submit through `provider.submit_pickup_order(...)`
5. persist `Order_POS_Sync`

Rules:

- the provider total must match internal pricing
- use explicit discounts if the provider catalog price alone cannot represent internal free-allowance pricing
- use provider-returned totals/payments where appropriate instead of recomputing blindly
- voice create flow must not confirm to the caller before the provider confirms success

### 5. Order cancellation

Primary service:

- `app/services/pos_service.py`

Flow:

1. find latest successful sync row
2. call `provider.cancel_pickup_order(...)`
3. persist cancellation payload/result
4. update internal order state only after provider success

Rules:

- treat payment and order cancellation together
- provider-specific refund/void semantics belong in the provider adapter

### 6. Order updates

Current behavior:

- cart-changing updates are handled as cancel/refund + recreate
- this protects the system from paid-order mutation complexity

Implication for a new provider:

- do not assume in-place order mutation is required
- if the provider supports safe paid-order edits, you still need a clear reconciliation strategy before using them

### 7. Retry processing

Primary service:

- `app/services/pos_retry_service.py`

Flow:

1. load pending `Order_POS_Sync` rows
2. rebuild submission context
3. retry through `POSService`
4. update sync record status

Rules:

- use provider idempotency keys
- only retry errors that are actually retryable
- keep live voice-create behavior separate from back-office retries

### 8. Archive / restore

Primary service:

- `app/services/pos_catalog_archive_service.py`

Purpose:

- create rollback snapshots of internal catalog state
- restore internal catalog and mappings if a provider import goes wrong

If you add a provider and change the internal catalog model, make sure archive payloads still capture everything needed to restore a coherent internal state.

## Current Square-First Areas You Must Touch For A New Provider

The codebase has a real abstraction layer now, but it is not provider-agnostic end to end yet.

You must review at least these areas:

### API validation

- `app/api/pos_integrations.py`

Current state:

- create route rejects anything except `SQUARE`

### Provider registry

- `app/integrations/pos/registry.py`

Current state:

- only `SquarePOSProvider` is registered

### Runtime submission branch

- `app/services/pos_service.py`

Current state:

- unsupported `pos_type` values are rejected early
- some helper logic still prefers Square if multiple integrations exist

### Webhook API

- `app/api/pos_webhooks.py`

Current state:

- only `/api/v1/webhooks/square` exists

### Webhook processing

- `app/services/pos_webhook_event_service.py`

Current state:

- Square signature validation
- Square payload extraction
- Square supported event types

### Scheduler

- `app/services/pos_catalog_background_sync.py`

Current state:

- webhook retry processing is called with `pos_type="SQUARE"`

That is deliberate for today, but it must be generalized when another provider is added.

## What A Clean New Provider Implementation Should Look Like

If you add Toast, aim for this shape:

1. Add `app/integrations/toast_client.py` or equivalent provider-specific HTTP client.
2. Add `app/integrations/pos/toast_provider.py`.
3. Register it in `build_default_pos_provider_registry()`.
4. Expand `CreatePOSIntegrationRequest` validation to allow `TOAST`.
5. Add provider routing in `POSService` and webhook/event processing.
6. Add a provider-specific webhook endpoint only if needed.
7. Reuse generic tables and generic services wherever possible.
8. Extend docs and tests.

Do not resurrect deleted branch-only Toast code. Build on the current generic provider contract instead.

## Testing Checklist

Before shipping a new provider, extend tests in the same pattern as the Square work.

High-value test files:

- `tests/test_square_integration_helpers.py`
- `tests/test_pos_service.py`
- `tests/test_pos_webhook_event_service.py`
- `tests/test_pos_retry_service.py`
- `tests/test_dashboard_order_service.py`
- `app/agent_fc/tests/test_orders_call_session_guard.py`

At minimum, cover:

1. provider catalog normalization
2. availability update normalization
3. order submission success
4. retryable submission failure
5. cancellation success
6. replace-order flow
7. webhook signature validation
8. webhook dedupe / retry behavior
9. mapping fallback to snapshot external ids

## Design Rules To Keep

### Keep live calls internal-only

Do not add provider catalog or availability fetches to agent functions.

### Preserve operator edits

If the internal display name/description differs from the stored provider source value, imports should not stomp the operator edit.

### Keep `is_active` and `is_available` separate

- `is_active` means the object is part of the current usable catalog
- `is_available` means temporarily orderable right now

### Use snapshots for resiliency

If mappings drift after order creation, retries and replacements should still work from snapshot external ids.

### Keep provider logic in the provider

Refund semantics, fulfillment cancellation semantics, signature validation rules, provider pricing quirks, and provider availability queries all belong in the provider client/adapter layer, not the live agent functions.

### Prefer additive generic schema over provider-specific schema

If a new provider needs one more shared field, add one migration to the generic tables instead of building a parallel storage model.

## Practical Build Order For The Next Provider

Recommended sequence:

1. provider HTTP client
2. provider adapter with `fetch_catalog`
3. full catalog import working
4. provider adapter with `fetch_availability_updates`
5. webhook ingest and retry path
6. provider adapter with `submit_pickup_order`
7. provider adapter with `cancel_pickup_order`
8. dashboard and voice validation
9. archive / restore verification
10. documentation and tests

## References Inside This Repo

- `migrations/043_create_pos_integration_tables.sql`
- `migrations/044_add_pos_catalog_metadata.sql`
- `migrations/045_create_pos_catalog_mapping_tables.sql`
- `migrations/046_create_pos_catalog_sync_tracking.sql`
- `migrations/047_create_pos_catalog_archives.sql`
- `migrations/048_add_pos_webhook_tracking.sql`
- `migrations/049_add_pos_order_management_fields.sql`

