// Modal Form Handler - Handles AJAX form submissions in modals
document.addEventListener('DOMContentLoaded', function() {
    // Handle modal form submissions
    document.querySelectorAll('[data-modal-form]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const url = this.action || window.location.pathname;
            const modalId = this.closest('.modal').id;
            
            // Get CSRF token from form or cookie
            const csrftoken = form.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                             document.cookie.match(/csrftoken=([^;]+)/)?.[1];
            
            fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken || ''
                }
            })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                    return;
                }
                // Check if response is JSON
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return response.json();
                } else {
                    // If not JSON, assume it's a redirect or HTML response
                    window.location.reload();
                    return null;
                }
            })
            .then(data => {
                if (!data) return; // Handled by reload above
                
                if (data.success) {
                    // Close modal
                    const modalElement = document.getElementById(modalId);
                    if (modalElement) {
                        const modal = bootstrap.Modal.getInstance(modalElement);
                        if (modal) modal.hide();
                    }
                    
                    // Show success message
                    if (data.message) {
                        // Create a temporary alert or use Django messages
                        const alertDiv = document.createElement('div');
                        alertDiv.className = 'alert alert-success alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3';
                        alertDiv.style.zIndex = '9999';
                        alertDiv.innerHTML = `
                            ${data.message}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        `;
                        document.body.appendChild(alertDiv);
                        setTimeout(() => alertDiv.remove(), 3000);
                    }
                    
                    // Redirect if specified, otherwise reload
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    } else {
                        window.location.reload();
                    }
                } else if (data.message) {
                    // Show error message
                    alert(data.message || 'An error occurred. Please try again.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            });
        });
    });
    
    // Load modal content via AJAX
    document.querySelectorAll('[data-modal-load]').forEach(function(button) {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.getAttribute('href') || this.dataset.modalLoad;
            const modalId = this.dataset.modalTarget || this.getAttribute('data-bs-target');
            
            fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            })
            .then(response => response.text())
            .then(html => {
                const modalElement = document.querySelector(modalId);
                if (modalElement) {
                    modalElement.querySelector('.modal-content').innerHTML = html;
                    const modal = new bootstrap.Modal(modalElement);
                    modal.show();
                }
            })
            .catch(error => {
                console.error('Error loading modal:', error);
            });
        });
    });
});

