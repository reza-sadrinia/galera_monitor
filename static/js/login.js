/**
 * Login Page JavaScript
 * Handles login form interactions and UI enhancements
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeLoginPage();
});

function initializeLoginPage() {
    // Initialize password toggle
    initPasswordToggle();
    
    // Initialize form validation
    initFormValidation();
    
    // Initialize auto-hide alerts
    initAutoHideAlerts();
    
    // Initialize form animations
    initFormAnimations();
    
    // Focus on username field
    const usernameField = document.getElementById('username');
    if (usernameField) {
        usernameField.focus();
    }
}

function initPasswordToggle() {
    const passwordField = document.getElementById('password');
    const toggleIcon = document.getElementById('toggleIcon');
    const toggleButton = document.querySelector('.password-toggle');
    
    if (passwordField && toggleIcon && toggleButton) {
        toggleButton.addEventListener('click', function() {
            togglePassword();
        });
        
        // Add keyboard support
        toggleButton.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                togglePassword();
            }
        });
        
        // Make it focusable
        toggleButton.setAttribute('tabindex', '0');
        toggleButton.setAttribute('role', 'button');
        toggleButton.setAttribute('aria-label', 'نمایش/مخفی کردن رمز عبور');
    }
}

function togglePassword() {
    const passwordField = document.getElementById('password');
    const toggleIcon = document.getElementById('toggleIcon');
    
    if (passwordField && toggleIcon) {
        if (passwordField.type === 'password') {
            passwordField.type = 'text';
            toggleIcon.classList.remove('fa-eye');
            toggleIcon.classList.add('fa-eye-slash');
            toggleIcon.parentElement.setAttribute('aria-label', 'مخفی کردن رمز عبور');
        } else {
            passwordField.type = 'password';
            toggleIcon.classList.remove('fa-eye-slash');
            toggleIcon.classList.add('fa-eye');
            toggleIcon.parentElement.setAttribute('aria-label', 'نمایش رمز عبور');
        }
    }
}

function initFormValidation() {
    const loginForm = document.querySelector('form');
    const usernameField = document.getElementById('username');
    const passwordField = document.getElementById('password');
    const submitButton = document.querySelector('.btn-login');
    
    if (loginForm && usernameField && passwordField && submitButton) {
        // Real-time validation
        [usernameField, passwordField].forEach(field => {
            field.addEventListener('input', function() {
                validateField(field);
                updateSubmitButton();
            });
            
            field.addEventListener('blur', function() {
                validateField(field);
            });
        });
        
        // Form submission
        loginForm.addEventListener('submit', function(e) {
            if (!validateForm()) {
                e.preventDefault();
                return false;
            }
            
            // Show loading state
            showLoadingState(submitButton);
        });
        
        // Initial validation
        updateSubmitButton();
    }
}

function validateField(field) {
    const value = field.value.trim();
    const isValid = value.length > 0;
    
    // Remove existing validation classes
    field.classList.remove('is-valid', 'is-invalid');
    
    // Add appropriate class
    if (field.value.length > 0) {
        field.classList.add(isValid ? 'is-valid' : 'is-invalid');
    }
    
    return isValid;
}

function validateForm() {
    const usernameField = document.getElementById('username');
    const passwordField = document.getElementById('password');
    
    const isUsernameValid = validateField(usernameField);
    const isPasswordValid = validateField(passwordField);
    
    if (!isUsernameValid) {
        showFieldError(usernameField, 'لطفا نام کاربری را وارد کنید');
    }
    
    if (!isPasswordValid) {
        showFieldError(passwordField, 'لطفا رمز عبور را وارد کنید');
    }
    
    return isUsernameValid && isPasswordValid;
}

function showFieldError(field, message) {
    // Remove existing error message
    const existingError = field.parentElement.querySelector('.field-error');
    if (existingError) {
        existingError.remove();
    }
    
    // Create error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error text-danger small mt-1';
    errorDiv.textContent = message;
    
    // Insert after the field
    field.parentElement.appendChild(errorDiv);
    
    // Remove after 3 seconds
    setTimeout(() => {
        if (errorDiv.parentElement) {
            errorDiv.remove();
        }
    }, 3000);
}

function updateSubmitButton() {
    const usernameField = document.getElementById('username');
    const passwordField = document.getElementById('password');
    const submitButton = document.querySelector('.btn-login');
    
    if (usernameField && passwordField && submitButton) {
        const isFormValid = usernameField.value.trim().length > 0 && 
                           passwordField.value.trim().length > 0;
        
        submitButton.disabled = !isFormValid;
        submitButton.style.opacity = isFormValid ? '1' : '0.6';
    }
}

function showLoadingState(button) {
    if (button) {
        button.classList.add('loading');
        button.disabled = true;
        
        // Reset after 10 seconds (in case of network issues)
        setTimeout(() => {
            hideLoadingState(button);
        }, 10000);
    }
}

function hideLoadingState(button) {
    if (button) {
        button.classList.remove('loading');
        button.disabled = false;
    }
}

function initAutoHideAlerts() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        // Add close button
        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'btn-close btn-close-white';
        closeButton.setAttribute('aria-label', 'بستن');
        closeButton.style.cssText = 'position: absolute; top: 8px; left: 8px; font-size: 12px;';
        
        alert.style.position = 'relative';
        alert.appendChild(closeButton);
        
        closeButton.addEventListener('click', () => {
            hideAlert(alert);
        });
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            hideAlert(alert);
        }, 5000);
    });
}

function hideAlert(alert) {
    if (alert && alert.parentElement) {
        alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 500);
    }
}

function initFormAnimations() {
    // Add focus animations to form fields
    const formFields = document.querySelectorAll('.form-control');
    
    formFields.forEach(field => {
        field.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        field.addEventListener('blur', function() {
            if (!this.value) {
                this.parentElement.classList.remove('focused');
            }
        });
        
        // Check if field has value on load
        if (field.value) {
            field.parentElement.classList.add('focused');
        }
    });
}

// Utility functions
function showMessage(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
        <i class="fas fa-info-circle me-2"></i>
        ${message}
    `;
    
    const container = document.querySelector('.login-container');
    const form = container.querySelector('form');
    
    container.insertBefore(alertDiv, form);
    
    // Auto-hide
    setTimeout(() => {
        hideAlert(alertDiv);
    }, 5000);
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Enter key on username field should focus password field
    if (e.key === 'Enter' && e.target.id === 'username') {
        e.preventDefault();
        const passwordField = document.getElementById('password');
        if (passwordField) {
            passwordField.focus();
        }
    }
});

// Export functions for external use
window.LoginPage = {
    togglePassword,
    showMessage,
    validateForm,
    showLoadingState,
    hideLoadingState
};