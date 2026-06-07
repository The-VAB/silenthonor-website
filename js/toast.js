/**
 * Toast Notification System for Silent Honor Foundation
 * Usage: showToast('Title', 'Message', 'success|error|warning|info')
 */

(function() {
    // Create toast container if it doesn't exist
    function getContainer() {
        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    // Get icon based on type
    function getIcon(type) {
        switch (type) {
            case 'success': return '&#10003;';
            case 'error': return '&#10005;';
            case 'warning': return '&#9888;';
            case 'info': return '&#8505;';
            default: return '&#8226;';
        }
    }

    // Show toast notification
    window.showToast = function(title, message, type, duration) {
        type = type || 'info';
        duration = duration || 5000;

        var container = getContainer();

        var toast = document.createElement('div');
        toast.className = 'toast ' + type;
        toast.innerHTML =
            '<span class="toast-icon">' + getIcon(type) + '</span>' +
            '<div class="toast-content">' +
                '<div class="toast-title">' + title + '</div>' +
                '<div class="toast-message">' + message + '</div>' +
            '</div>' +
            '<button class="toast-close" onclick="closeToast(this.parentElement)">&times;</button>';

        container.appendChild(toast);

        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(function() {
                if (toast.parentElement) {
                    closeToast(toast);
                }
            }, duration);
        }

        return toast;
    };

    // Close toast with animation
    window.closeToast = function(toast) {
        if (!toast) return;
        toast.classList.add('removing');
        setTimeout(function() {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    };

    // Convenience methods
    window.toastSuccess = function(title, message, duration) {
        return showToast(title, message, 'success', duration);
    };

    window.toastError = function(title, message, duration) {
        return showToast(title, message, 'error', duration);
    };

    window.toastWarning = function(title, message, duration) {
        return showToast(title, message, 'warning', duration);
    };

    window.toastInfo = function(title, message, duration) {
        return showToast(title, message, 'info', duration);
    };
})();
