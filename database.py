import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
import json


class EmailDatabase:
    """
    Lightweight SQLite database for storing processed emails and system state.
    Optimized for t3.micro AWS instances with minimal resource usage.
    """

    def __init__(self, db_path: str = "emails.db"):
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.connection = None
        self._connect()
        self._initialize_tables()

    def _connect(self):
        """Establish database connection."""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Return rows as dictionaries
            # Enable WAL mode for better concurrency
            self.connection.execute("PRAGMA journal_mode=WAL")
            # Optimize for speed on t3.micro
            self.connection.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            raise

    def _initialize_tables(self):
        """Create tables if they don't exist."""
        cursor = self.connection.cursor()

        # Emails table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                gmail_id INTEGER PRIMARY KEY,
                reason TEXT NOT NULL,
                priority TEXT NOT NULL,
                category TEXT NOT NULL,
                deadline TEXT,
                sender TEXT NOT NULL,
                raw_subject TEXT NOT NULL,
                raw_body TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_priority_deadline
            ON emails(priority, deadline)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category
            ON emails(category)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_at
            ON emails(processed_at)
        """)

        # Heartbeat/state tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS heartbeat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_heartbeat_timestamp
            ON heartbeat(timestamp)
        """)

        self.connection.commit()

    def save_email(self, email_data: Dict) -> bool:
        """
        Save a single processed email to the database.

        Args:
            email_data: Dictionary containing email metadata

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO emails
                (gmail_id, reason, priority, category, deadline, sender,
                 raw_subject, raw_body, processed_at, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email_data["gmail_id"],
                email_data["reason"],
                email_data["priority"],
                email_data["category"],
                email_data["deadline"],
                email_data["sender"],
                email_data["raw_subject"],
                email_data["raw_body"],
                datetime.now().isoformat(),
                email_data["model"]
            ))
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error saving email {email_data.get('gmail_id')}: {e}")
            return False

    def save_emails_batch(self, emails: List[Dict]) -> int:
        """
        Save multiple emails in a single transaction for better performance.

        Args:
            emails: List of email data dictionaries

        Returns:
            Number of emails successfully saved
        """
        if not emails:
            return 0

        saved_count = 0
        cursor = self.connection.cursor()

        try:
            for email_data in emails:
                cursor.execute("""
                    INSERT OR REPLACE INTO emails
                    (gmail_id, reason, priority, category, deadline, sender,
                     raw_subject, raw_body, processed_at, model)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email_data["gmail_id"],
                    email_data["reason"],
                    email_data["priority"],
                    email_data["category"],
                    email_data["deadline"],
                    email_data["sender"],
                    email_data["raw_subject"],
                    email_data["raw_body"],
                    datetime.now().isoformat(),
                    email_data["model"]
                ))
                saved_count += 1

            self.connection.commit()
            return saved_count

        except sqlite3.Error as e:
            print(f"Error in batch save: {e}")
            self.connection.rollback()
            return saved_count

    def get_recent_emails(self, limit: int = 50) -> List[Dict]:
        """
        Retrieve recent emails ordered by gmail_id (descending).

        Args:
            limit: Maximum number of emails to return

        Returns:
            List of email dictionaries
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT gmail_id, reason, priority, category, deadline,
                       sender, raw_subject, raw_body, processed_at, model, created_at
                FROM emails
                ORDER BY gmail_id DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"Error fetching recent emails: {e}")
            return []

    def get_emails_by_priority(self, priority: str, limit: int = 50) -> List[Dict]:
        """Get emails filtered by priority level."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT gmail_id, reason, priority, category, deadline,
                       sender, raw_subject, raw_body, processed_at, model, created_at
                FROM emails
                WHERE priority = ?
                ORDER BY gmail_id DESC
                LIMIT ?
            """, (priority, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"Error fetching emails by priority: {e}")
            return []

    def get_emails_by_category(self, category: str, limit: int = 50) -> List[Dict]:
        """Get emails filtered by category."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT gmail_id, reason, priority, category, deadline,
                       sender, raw_subject, raw_body, processed_at, model, created_at
                FROM emails
                WHERE category = ?
                ORDER BY gmail_id DESC
                LIMIT ?
            """, (category, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"Error fetching emails by category: {e}")
            return []

    def email_exists(self, gmail_id: int) -> bool:
        """Check if an email with given gmail_id already exists in database."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT 1 FROM emails WHERE gmail_id = ? LIMIT 1
            """, (gmail_id,))
            return cursor.fetchone() is not None

        except sqlite3.Error as e:
            print(f"Error checking email existence: {e}")
            return False

    def get_existing_email_ids(self, limit: int = 100) -> List[int]:
        """Get list of existing email IDs (gmail_id) for deduplication."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT gmail_id FROM emails
                ORDER BY gmail_id DESC
                LIMIT ?
            """, (limit,))
            return [row[0] for row in cursor.fetchall()]

        except sqlite3.Error as e:
            print(f"Error fetching existing email IDs: {e}")
            return []

    def update_heartbeat(self, state: str):
        """
        Record system heartbeat/state for monitoring.

        Args:
            state: Current state of the system
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO heartbeat (state, timestamp)
                VALUES (?, ?)
            """, (state, datetime.now().isoformat()))
            self.connection.commit()

        except sqlite3.Error as e:
            print(f"Error updating heartbeat: {e}")

    def get_recent_heartbeats(self, limit: int = 20) -> List[Dict]:
        """Retrieve recent heartbeat entries."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, state, timestamp, created_at
                FROM heartbeat
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"Error fetching heartbeats: {e}")
            return []

    def get_statistics(self) -> Dict:
        """Get database statistics for monitoring."""
        try:
            cursor = self.connection.cursor()

            # Total emails
            cursor.execute("SELECT COUNT(*) FROM emails")
            total_emails = cursor.fetchone()[0]

            # Emails by priority
            cursor.execute("""
                SELECT priority, COUNT(*) as count
                FROM emails
                GROUP BY priority
            """)
            priority_stats = {row[0]: row[1] for row in cursor.fetchall()}

            # Emails by category
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM emails
                GROUP BY category
            """)
            category_stats = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_emails": total_emails,
                "priority_breakdown": priority_stats,
                "category_breakdown": category_stats,
                "database_size_mb": os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0
            }

        except sqlite3.Error as e:
            print(f"Error getting statistics: {e}")
            return {}

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()


# Utility function for easy database access
def get_database(db_path: str = "emails.db") -> EmailDatabase:
    """
    Factory function to get a database instance.

    Args:
        db_path: Path to SQLite database file

    Returns:
        EmailDatabase instance
    """
    return EmailDatabase(db_path)
