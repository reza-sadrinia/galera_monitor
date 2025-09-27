"""
Authentication module for Galera Monitor
Handles user authentication, login, logout functionality
"""

from flask import render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
import os
import yaml


class User(UserMixin):
    """Simple User class for Flask-Login"""
    def __init__(self, id, username=None):
        self.id = id
        self.username = username or id


class AuthManager:
    """Authentication manager class"""
    
    def __init__(self, app=None):
        """Initialize the AuthManager with Flask app"""
        self.login_manager = LoginManager()
        self.users = self._load_users_from_config()
        
        if app:
            self.init_app(app)
    
    def _load_config(self):
        """Load configuration from config.yaml"""
        try:
            with open('config.yaml', 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            # Fallback to default values if config.yaml doesn't exist
            return {
                'authentication': {
                    'username': 'admin',
                    'password': 'admin123'
                }
            }
    
    def _load_users_from_config(self):
        """Load users from config file"""
        config = self._load_config()
        auth_config = config.get('authentication', {})
        username = auth_config.get('username', 'admin')
        password = auth_config.get('password', 'admin123')
        
        return {username: password}
    
    def init_app(self, app):
        """Initialize Flask-Login with the app"""
        self.login_manager.init_app(app)
        self.login_manager.login_view = 'login'
        self.login_manager.login_message = '🔐 Access Denied! Please authenticate to continue.'
        self.login_manager.login_message_category = 'info'
        
        # Set up user loader
        @self.login_manager.user_loader
        def load_user(user_id):
            return User(user_id) if user_id in self.users else None
        
        # Register authentication routes
        @app.route('/login', methods=['GET', 'POST'])
        def login():
            return self.handle_login()
        
        @app.route('/logout')
        @login_required
        def logout():
            return self.handle_logout()
    
    def authenticate_user(self, username, password):
        """Authenticate user with username and password"""
        if username in self.users:
            stored_password = self.users[username]
            # In production, use check_password_hash(stored_password, password)
            if stored_password == password:
                return True
        return False
    
    def add_user(self, username, password):
        """Add a new user (for future use)"""
        # In production, hash the password: generate_password_hash(password)
        self.users[username] = password
    
    def get_users_info(self):
        """Get information about all users (for admin purposes)"""
        return {
            username: {
                'username': username,
                'last_login': None  # You can extend this
            }
            for username in self.users.keys()
        }
    
    def handle_login(self):
        """Handle login POST request"""
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            remember = 'remember' in request.form
            
            if not username or not password:
                flash('⚠️ Oops! Both username and password are required to proceed.', 'error')
                return render_template('login.html')
            
            if self.authenticate_user(username, password):
                user = User(username, username)
                login_user(user, remember=remember)
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('🚫 Authentication failed! Please check your credentials and try again.', 'error')
        
        return render_template('login.html')
    
    def handle_logout(self):
        """Handle logout request"""
        # Clear any existing flash messages
        session.pop('_flashes', None)
        logout_user()
        flash('👋 See you later! You have been safely logged out.', 'info')
        return redirect(url_for('login'))