"""Set restaurant to 24 hours for all days."""
import os
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

load_dotenv()


def main():
    restaurant_id = 1
    
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USERNAME', 'root'),
            password=os.getenv('DB_PASSWORD', 'root'),
            database=os.getenv('DB_NAME', 'ressy')
        )
        
        cursor = connection.cursor()
        
        query = """
            UPDATE Restaurants 
            SET 
                monday_24_hours = TRUE,
                tuesday_24_hours = TRUE,
                wednesday_24_hours = TRUE,
                thursday_24_hours = TRUE,
                friday_24_hours = TRUE,
                saturday_24_hours = TRUE,
                sunday_24_hours = TRUE
            WHERE id = %s
        """
        
        cursor.execute(query, (restaurant_id,))
        connection.commit()
        
        logger.info(f"Updated restaurant {restaurant_id} to 24 hours for all days")
        logger.info(f"Rows affected: {cursor.rowcount}")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"Error updating restaurant: {e}")
        raise


if __name__ == "__main__":
    main()
