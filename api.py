#!/usr/bin/env python3
"""
Lightweight Flask API for email data access.
Optimized for AWS t3.micro instances.
"""

from flask import Flask, jsonify, request
from database import EmailDatabase
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "emails.db")
API_PORT = int(os.getenv("API_PORT", "5000"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Initialize database
db = EmailDatabase(DB_PATH)


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for monitoring.
    Returns database stats and recent heartbeat.
    """
    try:
        stats = db.get_statistics()
        heartbeats = db.get_recent_heartbeats(limit=1)

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'total_emails': stats.get('total_emails', 0),
                'size_mb': stats.get('database_size_mb', 0)
            },
            'last_heartbeat': heartbeats[0] if heartbeats else None
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/emails', methods=['GET'])
def get_emails():
    """
    Get emails with optional filtering and pagination.

    Query Parameters:
    - limit: Maximum number of emails (default: 50, max: 200)
    - since: ISO timestamp - only return emails processed after this time
    - priority: Filter by priority (HIGH, EXTRA_HIGH, LOW)
    - category: Filter by category (internship, placement, etc.)
    """
    try:
        # Parse query parameters
        limit = min(int(request.args.get('limit', 50)), 200)
        since = request.args.get('since')
        priority = request.args.get('priority')
        category = request.args.get('category')

        # Get emails based on filters
        if priority:
            emails = db.get_emails_by_priority(priority, limit=limit)
        elif category:
            emails = db.get_emails_by_category(category, limit=limit)
        else:
            emails = db.get_recent_emails(limit=limit)

        # Filter by timestamp if 'since' is provided
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                emails = [
                    e for e in emails
                    if datetime.fromisoformat(e['processed_at']) > since_dt
                ]
            except ValueError:
                return jsonify({
                    'error': 'Invalid since parameter. Use ISO format: YYYY-MM-DDTHH:MM:SS'
                }), 400

        return jsonify({
            'count': len(emails),
            'emails': emails,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails/priority/<priority>', methods=['GET'])
def get_emails_by_priority(priority):
    """
    Get emails filtered by priority level.

    Path Parameters:
    - priority: HIGH, EXTRA_HIGH, or LOW

    Query Parameters:
    - limit: Maximum number of emails (default: 50)
    """
    try:
        priority = priority.upper()
        if priority not in ['HIGH', 'EXTRA_HIGH', 'LOW']:
            return jsonify({
                'error': 'Invalid priority. Must be HIGH, EXTRA_HIGH, or LOW'
            }), 400

        limit = min(int(request.args.get('limit', 50)), 200)
        emails = db.get_emails_by_priority(priority, limit=limit)

        return jsonify({
            'priority': priority,
            'count': len(emails),
            'emails': emails,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails/category/<category>', methods=['GET'])
def get_emails_by_category(category):
    """
    Get emails filtered by category.

    Path Parameters:
    - category: internship, placement, hackathon, assignment, exam, etc.

    Query Parameters:
    - limit: Maximum number of emails (default: 50)
    """
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        emails = db.get_emails_by_category(category, limit=limit)

        return jsonify({
            'category': category,
            'count': len(emails),
            'emails': emails,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails/sync', methods=['GET'])
def sync_emails():
    """
    Optimized endpoint for Android app sync.
    Returns only new emails since last sync timestamp.

    Query Parameters:
    - last_sync: ISO timestamp of last successful sync (required)
    - limit: Maximum number of emails (default: 100)
    """
    try:
        last_sync = request.args.get('last_sync')
        if not last_sync:
            return jsonify({
                'error': 'last_sync parameter is required (ISO format: YYYY-MM-DDTHH:MM:SS)'
            }), 400

        try:
            last_sync_dt = datetime.fromisoformat(last_sync)
        except ValueError:
            return jsonify({
                'error': 'Invalid last_sync format. Use ISO format: YYYY-MM-DDTHH:MM:SS'
            }), 400

        limit = min(int(request.args.get('limit', 100)), 200)
        all_emails = db.get_recent_emails(limit=limit)

        # Filter emails processed after last sync
        new_emails = [
            e for e in all_emails
            if datetime.fromisoformat(e['processed_at']) > last_sync_dt
        ]

        return jsonify({
            'count': len(new_emails),
            'new_emails': new_emails,
            'sync_timestamp': datetime.now().isoformat(),
            'has_more': len(all_emails) == limit  # Indicates if there might be more data
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Get database statistics.
    Returns total counts, priority breakdown, and category breakdown.
    """
    try:
        stats = db.get_statistics()

        return jsonify({
            'total_emails': stats.get('total_emails', 0),
            'priority_breakdown': stats.get('priority_breakdown', {}),
            'category_breakdown': stats.get('category_breakdown', {}),
            'database_size_mb': round(stats.get('database_size_mb', 0), 4),
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/heartbeat', methods=['GET'])
def get_heartbeat():
    """
    Get recent system heartbeat entries for monitoring.

    Query Parameters:
    - limit: Number of heartbeat entries (default: 10, max: 50)
    """
    try:
        limit = min(int(request.args.get('limit', 10)), 50)
        heartbeats = db.get_recent_heartbeats(limit=limit)

        return jsonify({
            'count': len(heartbeats),
            'heartbeats': heartbeats,
            'timestamp': datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Endpoint not found',
        'timestamp': datetime.now().isoformat()
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        'error': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500


# CORS support for development (optional)
@app.after_request
def after_request(response):
    """Add CORS headers if needed."""
    # Uncomment if you need CORS support during development
    # response.headers.add('Access-Control-Allow-Origin', '*')
    # response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    # response.headers.add('Access-Control-Allow-Methods', 'GET')
    return response


if __name__ == '__main__':
    print(f"Starting Email API server...")
    print(f"Database: {DB_PATH}")
    print(f"Listening on {API_HOST}:{API_PORT}")
    print(f"\nEndpoints:")
    print(f"  GET /api/health              - Health check")
    print(f"  GET /api/emails              - Get emails (with filters)")
    print(f"  GET /api/emails/sync         - Optimized sync endpoint")
    print(f"  GET /api/emails/priority/<p> - Filter by priority")
    print(f"  GET /api/emails/category/<c> - Filter by category")
    print(f"  GET /api/stats               - Database statistics")
    print(f"  GET /api/heartbeat           - System heartbeat")
    print(f"\n[Ctrl+C to stop]\n")

    # For production on t3.micro, use gunicorn instead:
    # gunicorn -w 2 -b 0.0.0.0:5000 api:app
    app.run(host=API_HOST, port=API_PORT, debug=False)
