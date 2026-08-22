"""Database backend for chatinho using SQLAlchemy."""

import logging
from typing import Any, Optional, Union
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

from .base import BaseBackend

logger = logging.getLogger(__name__)

# SQLAlchemy setup
Base = declarative_base()


class ChatData(Base):
    """Model for storing chat data."""
    __tablename__ = 'chat_data'
    
    id = Column(String, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    data_type = Column(String, default='json')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DatabaseBackend(BaseBackend):
    """Backend that stores data in a SQL database."""
    
    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        **kwargs
    ):
        super().__init__(database_url=database_url, echo=echo, **kwargs)
        self.database_url = database_url
        self.echo = echo
        self.engine = None
        self.SessionLocal = None
    
    def initialize(self):
        """Initialize the database connection and create tables."""
        logger.info(f"Initializing database backend with URL: {self.database_url}")
        try:
            # Create engine
            self.engine = create_engine(
                self.database_url,
                echo=self.echo,
                future=True
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Create tables
            Base.metadata.create_all(bind=self.engine)
            
            logger.info("Database backend initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database backend: {e}")
            raise
    
    def _get_session(self):
        """Get a database session."""
        if self.SessionLocal is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.SessionLocal()
    
    def save(self, key: str, data: Any) -> bool:
        """Save data to the database.
        
        Args:
            key: Identifier for the data
            data: Data to save (will be converted to string)
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.debug(f"Saving data with key: {key}")
        session = self._get_session()
        try:
            # Convert data to string for storage
            if isinstance(data, (dict, list)):
                import json
                value = json.dumps(data, ensure_ascii=False)
                data_type = "json"
            elif isinstance(data, str):
                value = data
                data_type = "string"
            else:
                value = str(data)
                data_type = type(data).__name__
            
            # Check if record exists
            record = session.query(ChatData).filter(ChatData.key == key).first()
            
            if record:
                # Update existing record
                record.value = value
                record.data_type = data_type
                record.updated_at = func.now()
            else:
                # Create new record
                record = ChatData(
                    key=key,
                    value=value,
                    data_type=data_type
                )
                session.add(record)
            
            session.commit()
            logger.debug(f"Data saved successfully with key: {key}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save data with key {key}: {e}")
            return False
        finally:
            session.close()
    
    def load(self, key: str) -> Any:
        """Load data from the database by key.
        
        Args:
            key: Identifier for the data
            
        Returns:
            Any: The loaded data, or None if not found
        """
        logger.debug(f"Loading data with key: {key}")
        session = self._get_session()
        try:
            record = session.query(ChatData).filter(ChatData.key == key).first()
            
            if record is None:
                logger.debug(f"No data found for key: {key}")
                return None
            
            # Convert value back to appropriate type
            value = record.value
            data_type = record.data_type
            
            if data_type == "json":
                import json
                return json.loads(value)
            elif data_type == "string":
                return value
            else:
                # For other types, try to convert back (basic implementation)
                try:
                    if data_type == "int":
                        return int(value)
                    elif data_type == "float":
                        return float(value)
                    elif data_type == "bool":
                        return value.lower() in ('true', '1', 'yes')
                    else:
                        return value  # Return as string if unsure
                except (ValueError, AttributeError):
                    return value  # Return as string on conversion error
                    
        except Exception as e:
            logger.error(f"Failed to load data with key {key}: {e}")
            return None
        finally:
            session.close()
    
    def delete(self, key: str) -> bool:
        """Delete data from the database by key.
        
        Args:
            key: Identifier for the data
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.debug(f"Deleting data with key: {key}")
        session = self._get_session()
        try:
            record = session.query(ChatData).filter(ChatData.key == key).first()
            
            if record:
                session.delete(record)
                session.commit()
                logger.debug(f"Data deleted successfully with key: {key}")
                return True
            else:
                logger.debug(f"No data found for key: {key}")
                return False
                
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete data with key {key}: {e}")
            return False
        finally:
            session.close()