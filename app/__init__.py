"""
app/__init__.py
===============
Flask Application Factory for Smarter Patient Care.

Per ARCHITECTURE.md Section 2.7:
- create_app() factory function initializes Flask app and registers routes.
"""

from flask import Flask


def create_app() -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)

    # Register routes blueprint / handlers
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
