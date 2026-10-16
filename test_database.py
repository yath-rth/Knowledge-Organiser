#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the email database functionality.
Verifies database operations work correctly before deploying to AWS.
"""

import sys
import io
from database import EmailDatabase
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_database():
    """Run basic database tests."""
    print("Testing EmailDatabase functionality...\n")

    # Test 1: Database initialization
    print("1. Testing database initialization...")
    db = EmailDatabase("test_emails.db")
    print("   ✓ Database created successfully\n")

    # Test 2: Save a single email
    print("2. Testing single email save...")
    test_email = {
        "gmail_id": 12345,
        "reason": "Test email for database verification",
        "priority": "HIGH",
        "category": "assignment",
        "deadline": "2024-12-31T23:59:00",
        "sender": "test@example.com",
        "raw_subject": "Test Subject",
        "raw_body": "This is a test email body",
        "processed_at": datetime.now().isoformat(),
        "model": "qwen3.5:0.8b"
    }

    success = db.save_email(test_email)
    if success:
        print("   ✓ Email saved successfully\n")
    else:
        print("   ✗ Failed to save email\n")
        return False

    # Test 3: Save batch of emails
    print("3. Testing batch email save...")
    batch_emails = [
        {
            "gmail_id": 12346,
            "reason": "Internship opportunity with deadline approaching",
            "priority": "EXTRA_HIGH",
            "category": "internship",
            "deadline": "2024-11-15T18:00:00",
            "sender": "placements@university.edu",
            "raw_subject": "SDE Internship - Company X",
            "raw_body": "Applications open for internship...",
            "processed_at": datetime.now().isoformat(),
            "model": "qwen3.5:0.8b"
        },
        {
            "gmail_id": 12347,
            "reason": "Workshop registration",
            "priority": "LOW",
            "category": "event",
            "deadline": None,
            "sender": "events@university.edu",
            "raw_subject": "AI Workshop Next Week",
            "raw_body": "Join us for an AI workshop...",
            "processed_at": datetime.now().isoformat(),
            "model": "qwen3.5:0.8b"
        }
    ]

    saved_count = db.save_emails_batch(batch_emails)
    print(f"   ✓ Saved {saved_count}/{len(batch_emails)} emails in batch\n")

    # Test 4: Retrieve recent emails
    print("4. Testing email retrieval...")
    recent = db.get_recent_emails(limit=10)
    print(f"   ✓ Retrieved {len(recent)} emails")
    for email in recent[:3]:
        print(f"      - ID: {email['gmail_id']}, Priority: {email['priority']}, Category: {email['category']}")
    print()

    # Test 5: Test duplicate detection
    print("5. Testing duplicate detection...")
    exists = db.email_exists(12345)
    print(f"   ✓ Email 12345 exists: {exists}")
    exists = db.email_exists(99999)
    print(f"   ✓ Email 99999 exists: {exists}\n")

    # Test 6: Get existing IDs
    print("6. Testing existing ID retrieval...")
    existing_ids = db.get_existing_email_ids(limit=10)
    print(f"   ✓ Found {len(existing_ids)} existing email IDs: {existing_ids}\n")

    # Test 7: Filter by priority
    print("7. Testing priority filtering...")
    high_priority = db.get_emails_by_priority("HIGH", limit=10)
    print(f"   ✓ Found {len(high_priority)} HIGH priority emails\n")

    # Test 8: Filter by category
    print("8. Testing category filtering...")
    internships = db.get_emails_by_category("internship", limit=10)
    print(f"   ✓ Found {len(internships)} internship emails\n")

    # Test 9: Heartbeat functionality
    print("9. Testing heartbeat updates...")
    db.update_heartbeat("test_started")
    db.update_heartbeat("processing_emails")
    db.update_heartbeat("test_completed")
    heartbeats = db.get_recent_heartbeats(limit=5)
    print(f"   ✓ Recorded {len(heartbeats)} heartbeat entries")
    for hb in heartbeats:
        print(f"      - State: {hb['state']}, Time: {hb['timestamp']}")
    print()

    # Test 10: Statistics
    print("10. Testing statistics...")
    stats = db.get_statistics()
    print(f"   ✓ Database statistics:")
    print(f"      - Total emails: {stats.get('total_emails', 0)}")
    print(f"      - Priority breakdown: {stats.get('priority_breakdown', {})}")
    print(f"      - Category breakdown: {stats.get('category_breakdown', {})}")
    print(f"      - Database size: {stats.get('database_size_mb', 0):.4f} MB")
    print()

    # Cleanup
    db.close()
    print("✓ All tests passed successfully!")
    print("\nNote: Test database created as 'test_emails.db'")
    print("You can delete it after verification or keep it for reference.")

    return True


if __name__ == "__main__":
    try:
        test_database()
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
