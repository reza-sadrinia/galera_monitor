from flask import jsonify, request
from src.database import api_transactions, api_process_list, api_kill_process

def handle_transactions():
    """Handle transactions API endpoint"""
    return api_transactions()

def handle_process_list():
    """Handle process list API endpoint"""
    return api_process_list()

def handle_kill_process():
    """Handle kill process API endpoint"""
    return api_kill_process()