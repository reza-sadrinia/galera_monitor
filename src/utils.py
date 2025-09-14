from datetime import datetime

def calculate_rate(current_value, previous_value, current_time, previous_time):
    """Calculate rate of change between two values over time"""
    if previous_value is None or previous_time is None:
        return 0
    
    value_diff = current_value - previous_value
    time_diff = (current_time - previous_time).total_seconds()
    
    if time_diff <= 0:
        return 0
        
    return round(value_diff / time_diff, 2)