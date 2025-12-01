#!/usr/bin/env python3
"""
Script to create default admin user manually.
Run this if the automatic user creation fails during startup.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal, init_db
from app.models import User
from app.api.auth import get_password_hash
from app.config import get_settings

def create_admin_user():
    """Create default admin user."""
    settings = get_settings()
    
    # Initialize database
    init_db()
    
    db = SessionLocal()
    try:
        # Check if user already exists
        admin_user = db.query(User).filter(User.email == settings.default_admin_email).first()
        if admin_user:
            print(f"✅ Admin user already exists: {settings.default_admin_email}")
            return
        
        # Create new admin user
        password_hash = get_password_hash(settings.default_admin_password)
        admin_user = User(
            email=settings.default_admin_email,
            password_hash=password_hash,
            is_admin="true",
            must_change_password="true"
        )
        db.add(admin_user)
        db.commit()
        print(f"✅ Successfully created admin user: {settings.default_admin_email}")
        print(f"   Password: {settings.default_admin_password}")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()

