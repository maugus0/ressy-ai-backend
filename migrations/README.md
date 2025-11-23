# Database Migrations

This directory contains MySQL database migration files for the RessyAI Backend application.

## Migration Order

Migrations should be run in numerical order (001, 002, 003, etc.) as they have dependencies on previous tables.

### Migration Files

1. **001_create_permissions.sql** - Creates the Permissions table (no dependencies)
2. **002_create_crm_roles.sql** - Creates the Crm_roles table (depends on Permissions)
3. **003_create_users.sql** - Creates the Users table (no dependencies)
4. **004_create_restaurants.sql** - Creates the Restaurants table (no dependencies)
5. **005_create_menus.sql** - Creates the Menus table (depends on Restaurants)
6. **006_create_orders.sql** - Creates the Orders table (depends on Users)
7. **007_create_order_details.sql** - Creates the Order_Details table (depends on Orders and Menus)
8. **008_create_faqs.sql** - Creates the FAQs table (depends on Restaurants)
9. **009_create_notifications.sql** - Creates the Notifications table (depends on Orders)
10. **010_create_transcripts.sql** - Creates the Transcripts table (depends on Users and Orders)
11. **011_create_table_availability_requests.sql** - Creates the Table_Availability_Requests table (depends on
    Restaurants)
12. **012_create_slot_bookings.sql** - Creates the Slot_Bookings table (depends on Restaurants)
13. **013_create_reservations.sql** - Creates the Reservations table (depends on Table_Availability_Requests,
    Slot_Bookings, and Users)
14. **014_create_ressy_administrator.sql** - Creates the Ressy_Administrator table (depends on Crm_roles)
15. **015_create_restaurant_administrators.sql** - Creates the Restaurant_Administrators table (depends on Restaurants
    and Crm_roles)

## Running Migrations

### Using MySQL Command Line

```bash
# Connect to your MySQL database
mysql -u your_username -p your_database_name

# Run migrations in order
source migrations/001_create_permissions.sql;
source migrations/002_create_crm_roles.sql;
# ... continue for all migrations
```

### Using a Migration Tool

If you're using a migration tool like Alembic, Flyway, or a custom script, ensure migrations are run in the correct
order.

## Database Schema Overview

### Core Tables

- **Users**: Customer information
- **Restaurants**: Restaurant details and integrations
- **Menus**: Menu items for restaurants
- **Orders**: Order information
- **Order_Details**: Individual items in orders

### Reservation System

- **Table_Availability_Requests**: Table availability requests
- **Slot_Bookings**: Available booking slots
- **Reservations**: Confirmed reservations

### Administrative

- **Permissions**: Route permissions
- **Crm_roles**: Role definitions
- **Ressy_Administrator**: Platform administrators
- **Restaurant_Administrators**: Restaurant-specific administrators

### Supporting Tables

- **FAQs**: Frequently asked questions
- **Notifications**: Order notifications
- **Transcripts**: Call transcripts and logs

## Indexes

All tables include appropriate indexes for:

- Primary keys (automatic)
- Foreign keys
- Frequently queried columns
- Composite indexes for common query patterns
- Full-text search indexes where applicable (FAQs)

## Foreign Key Constraints

Foreign keys are set up with appropriate ON DELETE and ON UPDATE actions:

- **CASCADE**: When parent is deleted/updated, child records are deleted/updated
- **RESTRICT**: Prevents deletion/update if child records exist
- **SET NULL**: Sets foreign key to NULL when parent is deleted (where applicable)

## Notes

- All tables use `utf8mb4` character set and `utf8mb4_unicode_ci` collation for full Unicode support
- Timestamps use `TIMESTAMP` type with automatic `created_at` and `updated_at` handling
- JSON columns are used for flexible data storage (order_details, customization, etc.)
- UUIDs are used for administrator tables (VARCHAR(36))

