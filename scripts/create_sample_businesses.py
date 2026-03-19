"""
Script to create sample businesses: Salon, Real Estate Consultancy, and Hotel.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

from app.repositories.mysql_business_repo import MySQLBusinessRepository
from app.repositories.mysql_business_features_repo import MySQLBusinessFeaturesRepository
from app.repositories.mysql_catalogue_repo import MySQLCatalogueRepository
from app.repositories.mysql_business_faq_repo import MySQLBusinessFAQRepository
from app.services.business_service import BusinessService
from app.services.catalogue_service import CatalogueService
from app.services.business_faq_service import BusinessFAQService
from app.utils.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

# Load environment variables
load_dotenv()


def create_salon_business():
    """Create a salon business with services."""
    logger.info("Creating Salon business...")
    
    business_service = BusinessService()
    catalogue_service = CatalogueService()
    faq_service = BusinessFAQService()
    
    # Create salon business
    salon_data = {
        "name": "Elite Hair Salon",
        "business_type": "salon",
        "address": "456 Fashion Avenue, Downtown",
        "phone_number": "+15551234001",
        "twilio_phone_number": "+15557654001",
        "timezone": "America/Vancouver",
        "forward_minutes": 30,
        "backward_minutes": 15,
        "reservation_seating_capacity": 10,
        "reservation_advance_days": 60,
        "operating_hours": {
            "monday": {"open": "09:00:00", "close": "18:00:00", "is_closed": False},
            "tuesday": {"open": "09:00:00", "close": "18:00:00", "is_closed": False},
            "wednesday": {"open": "09:00:00", "close": "18:00:00", "is_closed": False},
            "thursday": {"open": "09:00:00", "close": "20:00:00", "is_closed": False},
            "friday": {"open": "09:00:00", "close": "20:00:00", "is_closed": False},
            "saturday": {"open": "10:00:00", "close": "17:00:00", "is_closed": False},
            "sunday": {"open": "11:00:00", "close": "16:00:00", "is_closed": False},
        },
        "features": {
            "orders_enabled": False,
            "reservations_enabled": True,
            "faqs_enabled": True,
        },
    }
    
    try:
        salon = business_service.create_business(salon_data)
        salon_id = salon["id"]
        logger.info(f"Created salon business with ID: {salon_id}")
    except Exception as e:
        if "already exists" in str(e).lower():
            # Business already exists, get it by name
            salon = business_service.business_repo.get_by_name(salon_data["name"])
            salon_id = salon["id"] if salon else None
            logger.info(f"Salon business already exists with ID: {salon_id}")
        else:
            raise
    
    # Create salon services (catalogue items)
    services = [
        {
            "item_name": "Haircut",
            "item_desc": "Professional haircut and styling",
            "category": "Hair Services",
            "sub_category": "Basic",
            "price": 45.00,
            "avg_prep_time": 30,
            "is_available": True,
            "is_special": False,
        },
        {
            "item_name": "Haircut & Styling",
            "item_desc": "Haircut with professional styling and blow-dry",
            "category": "Hair Services",
            "sub_category": "Premium",
            "price": 65.00,
            "avg_prep_time": 45,
            "is_available": True,
            "is_special": False,
        },
        {
            "item_name": "Hair Color",
            "item_desc": "Full hair coloring service",
            "category": "Hair Services",
            "sub_category": "Color",
            "price": 120.00,
            "avg_prep_time": 120,
            "is_available": True,
            "is_special": False,
        },
        {
            "item_name": "Highlights",
            "item_desc": "Professional hair highlighting",
            "category": "Hair Services",
            "sub_category": "Color",
            "price": 150.00,
            "avg_prep_time": 150,
            "is_available": True,
            "is_special": False,
        },
        {
            "item_name": "Manicure",
            "item_desc": "Classic manicure with polish",
            "category": "Nail Services",
            "sub_category": "Basic",
            "price": 35.00,
            "avg_prep_time": 30,
            "is_available": True,
            "is_special": False,
        },
        {
            "item_name": "Pedicure",
            "item_desc": "Relaxing pedicure with polish",
            "category": "Nail Services",
            "sub_category": "Basic",
            "price": 45.00,
            "avg_prep_time": 45,
            "is_available": True,
            "is_special": False,
        },
    ]
    
    for service in services:
        try:
            catalogue_service.create_catalogue_item(salon_id, service)
            logger.info(f"Created service: {service['item_name']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"Service '{service['item_name']}' already exists, skipping")
            else:
                raise
    
    # Create FAQs
    faqs = [
        {
            "question": "Do you accept walk-ins?",
            "answer": "We recommend making an appointment, but we do accept walk-ins based on availability.",
        },
        {
            "question": "What are your operating hours?",
            "answer": "We're open Monday to Friday 9 AM to 6 PM, Thursday and Friday until 8 PM, Saturday 10 AM to 5 PM, and Sunday 11 AM to 4 PM.",
        },
        {
            "question": "Do you offer gift certificates?",
            "answer": "Yes, we offer gift certificates for any amount. They make perfect gifts!",
        },
    ]
    
    for faq in faqs:
        faq_service.create_faq(salon_id, faq)
        logger.info(f"Created FAQ: {faq['question']}")
    
    return salon_id


def create_real_estate_business():
    """Create a real estate consultancy business with properties."""
    logger.info("Creating Real Estate Consultancy business...")
    
    business_service = BusinessService()
    catalogue_service = CatalogueService()
    faq_service = BusinessFAQService()
    
    # Create real estate business
    real_estate_data = {
        "name": "Premier Real Estate Consultancy",
        "business_type": "real_estate",
        "address": "789 Business District, Financial Center",
        "phone_number": "+15551234002",
        "twilio_phone_number": "+15557654002",
        "timezone": "America/Vancouver",
        "forward_minutes": 60,
        "backward_minutes": 30,
        "reservation_seating_capacity": 5,
        "reservation_advance_days": 90,
        "operating_hours": {
            "monday": {"open": "09:00:00", "close": "17:00:00", "is_closed": False},
            "tuesday": {"open": "09:00:00", "close": "17:00:00", "is_closed": False},
            "wednesday": {"open": "09:00:00", "close": "17:00:00", "is_closed": False},
            "thursday": {"open": "09:00:00", "close": "17:00:00", "is_closed": False},
            "friday": {"open": "09:00:00", "close": "17:00:00", "is_closed": False},
            "saturday": {"open": "10:00:00", "close": "14:00:00", "is_closed": False},
            "sunday": {"is_closed": True},
        },
        "features": {
            "orders_enabled": False,
            "reservations_enabled": True,
            "faqs_enabled": True,
        },
    }
    
    try:
        real_estate = business_service.create_business(real_estate_data)
        real_estate_id = real_estate["id"]
        logger.info(f"Created real estate business with ID: {real_estate_id}")
    except Exception as e:
        if "already exists" in str(e).lower():
            real_estate = business_service.business_repo.get_by_name(real_estate_data["name"])
            real_estate_id = real_estate["id"] if real_estate else None
            logger.info(f"Real estate business already exists with ID: {real_estate_id}")
        else:
            raise
    
    # Create properties (catalogue items with location metadata)
    properties = [
        {
            "item_name": "3BHK Luxury Apartment",
            "item_desc": "Spacious 3 bedroom, 2 bathroom apartment with modern amenities",
            "category": "Residential",
            "sub_category": "Apartment",
            "price": 450000.00,
            "avg_prep_time": None,
            "is_available": True,
            "is_special": False,
            "metadata": {
                "location": "Downtown Vancouver",
                "bedrooms": 3,
                "bathrooms": 2,
                "square_feet": 1500,
                "parking": True,
            },
        },
        {
            "item_name": "3BHK Penthouse",
            "item_desc": "Luxurious 3 bedroom penthouse with stunning city views",
            "category": "Residential",
            "sub_category": "Penthouse",
            "price": 850000.00,
            "avg_prep_time": None,
            "is_available": True,
            "is_special": True,
            "metadata": {
                "location": "West End, Vancouver",
                "bedrooms": 3,
                "bathrooms": 3,
                "square_feet": 2200,
                "parking": True,
                "balcony": True,
            },
        },
        {
            "item_name": "3BHK Townhouse",
            "item_desc": "Modern 3 bedroom townhouse with private garden",
            "category": "Residential",
            "sub_category": "Townhouse",
            "price": 650000.00,
            "avg_prep_time": None,
            "is_available": True,
            "is_special": False,
            "metadata": {
                "location": "Burnaby, BC",
                "bedrooms": 3,
                "bathrooms": 2.5,
                "square_feet": 1800,
                "parking": True,
                "garden": True,
            },
        },
        {
            "item_name": "2BHK Condo",
            "item_desc": "Cozy 2 bedroom condo in prime location",
            "category": "Residential",
            "sub_category": "Condo",
            "price": 380000.00,
            "avg_prep_time": None,
            "is_available": True,
            "is_special": False,
            "metadata": {
                "location": "Yaletown, Vancouver",
                "bedrooms": 2,
                "bathrooms": 2,
                "square_feet": 1100,
                "parking": False,
            },
        },
    ]
    
    for property_item in properties:
        try:
            catalogue_service.create_catalogue_item(real_estate_id, property_item)
            logger.info(f"Created property: {property_item['item_name']} in {property_item['metadata']['location']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"Property '{property_item['item_name']}' already exists, skipping")
            else:
                raise
    
    # Create FAQs
    faqs = [
        {
            "question": "How do I schedule a property viewing?",
            "answer": "You can schedule a viewing by calling us or booking an appointment through our system. We're available Monday to Friday 9 AM to 5 PM, and Saturday 10 AM to 2 PM.",
        },
        {
            "question": "What areas do you cover?",
            "answer": "We specialize in properties throughout Greater Vancouver, including Downtown, West End, Burnaby, and surrounding areas.",
        },
        {
            "question": "Do you help with financing?",
            "answer": "Yes, we work with several mortgage brokers and can help connect you with financing options.",
        },
    ]
    
    for faq in faqs:
        faq_service.create_faq(real_estate_id, faq)
        logger.info(f"Created FAQ: {faq['question']}")
    
    return real_estate_id


def create_hotel_business():
    """Create a hotel business with room types."""
    logger.info("Creating Hotel business...")
    
    business_service = BusinessService()
    catalogue_service = CatalogueService()
    faq_service = BusinessFAQService()
    
    # Create hotel business
    hotel_data = {
        "name": "Grand Vista Hotel",
        "business_type": "hotel",
        "address": "123 Hospitality Boulevard, Tourist District",
        "phone_number": "+15551234003",
        "twilio_phone_number": "+15557654003",
        "timezone": "America/Vancouver",
        "forward_minutes": 120,
        "backward_minutes": 0,
        "reservation_seating_capacity": 100,
        "reservation_advance_days": 365,
        "operating_hours": {
            "monday": {"is_24_hours": True},
            "tuesday": {"is_24_hours": True},
            "wednesday": {"is_24_hours": True},
            "thursday": {"is_24_hours": True},
            "friday": {"is_24_hours": True},
            "saturday": {"is_24_hours": True},
            "sunday": {"is_24_hours": True},
        },
        "features": {
            "orders_enabled": False,
            "reservations_enabled": True,
            "faqs_enabled": True,
        },
    }
    
    try:
        hotel = business_service.create_business(hotel_data)
        hotel_id = hotel["id"]
        logger.info(f"Created hotel business with ID: {hotel_id}")
    except Exception as e:
        if "already exists" in str(e).lower():
            hotel = business_service.business_repo.get_by_name(hotel_data["name"])
            hotel_id = hotel["id"] if hotel else None
            logger.info(f"Hotel business already exists with ID: {hotel_id}")
        else:
            raise
    
    # Create room types (catalogue items)
    rooms = [
        {
            "item_name": "Standard Suite",
            "item_desc": "Comfortable suite with city view, includes king bed and modern amenities",
            "category": "Rooms",
            "sub_category": "Standard",
            "price": 150.00,
            "avg_prep_time": None,
            "is_available": True,
            "is_special": False,
        },
        {
            "item_name": "Deluxe Suite",
            "item_desc": "Spacious suite with premium amenities, includes separate living area",
            "category": "Rooms",
            "sub_category": "Deluxe",
            "price": 220.00,
            "avg_prep_time": None,
            "is_available": True,
            "is_special": False,
        },
        {
            "item_name": "Executive Suite",
            "item_desc": "Luxury suite with panoramic views, includes workspace and premium amenities",
            "category": "Rooms",
            "sub_category": "Executive",
            "price": 320.00,
            "avg_prep_time": None,
            "is_available": True,
            "is_special": True,
        },
        {
            "item_name": "Presidential Suite",
            "item_desc": "Ultra-luxury suite with private balcony, butler service, and premium amenities",
            "category": "Rooms",
            "sub_category": "Presidential",
            "price": 550.00,
            "avg_prep_time": None,
            "is_available": True,
            "is_special": True,
        },
    ]
    
    for room in rooms:
        try:
            catalogue_service.create_catalogue_item(hotel_id, room)
            logger.info(f"Created room type: {room['item_name']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info(f"Room type '{room['item_name']}' already exists, skipping")
            else:
                raise
    
    # Create FAQs
    faqs = [
        {
            "question": "What time is check-in and check-out?",
            "answer": "Check-in is at 3 PM and check-out is at 11 AM. Early check-in and late check-out may be available upon request.",
        },
        {
            "question": "Do you have parking available?",
            "answer": "Yes, we have valet parking available for $25 per night, or self-parking for $15 per night.",
        },
        {
            "question": "Is breakfast included?",
            "answer": "Breakfast is included with Executive and Presidential suites. For other rooms, breakfast is available at our restaurant for an additional charge.",
        },
        {
            "question": "Do you allow pets?",
            "answer": "Yes, we are pet-friendly. A pet fee of $50 per stay applies.",
        },
    ]
    
    for faq in faqs:
        faq_service.create_faq(hotel_id, faq)
        logger.info(f"Created FAQ: {faq['question']}")
    
    return hotel_id


def main():
    """Main function to create all sample businesses."""
    logger.info("Starting sample business creation...")
    
    try:
        salon_id = create_salon_business()
        logger.info(f"✓ Salon created successfully (ID: {salon_id})")
        
        real_estate_id = create_real_estate_business()
        logger.info(f"✓ Real Estate Consultancy created successfully (ID: {real_estate_id})")
        
        hotel_id = create_hotel_business()
        logger.info(f"✓ Hotel created successfully (ID: {hotel_id})")
        
        logger.info("\n" + "="*60)
        logger.info("All sample businesses created successfully!")
        logger.info("="*60)
        logger.info(f"Salon Business ID: {salon_id}")
        logger.info(f"Real Estate Business ID: {real_estate_id}")
        logger.info(f"Hotel Business ID: {hotel_id}")
        logger.info("="*60)
        
    except Exception as e:
        logger.exception("Error creating sample businesses: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
