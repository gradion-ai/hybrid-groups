document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('github-app-form');
    const button = document.getElementById('register-app-button');
    const errorContainer = document.getElementById('form-error');
    const errorMessage = document.getElementById('form-error-message');

    const validateForm = () => {
        const appName = form.app_name.value.trim();
        const webhookUrl = form.webhook_url.value.trim();
        const isValid = appName && webhookUrl && isValidUrl(webhookUrl);
        button.disabled = !isValid;
        return isValid;
    };

    const isValidUrl = (string) => {
        try {
            const url = new URL(string);
            return ['http:', 'https:'].includes(url.protocol);
        } catch (_) {
            return false;
        }
    };

    const showError = (message) => {
        errorMessage.textContent = message;
        errorContainer.classList.add('show');
        errorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const hideError = () => {
        errorContainer.classList.remove('show');
    };

    const redirectToGitHub = (result) => {
        const form = document.createElement('form');
        form.method = 'post';
        form.action = result.github_url;
        form.style.display = 'none';

        const manifestInput = document.createElement('input');
        manifestInput.type = 'hidden';
        manifestInput.name = 'manifest';
        manifestInput.value = JSON.stringify(result.manifest);

        form.appendChild(manifestInput);
        document.body.appendChild(form);
        form.submit();
    };

    const registerApp = async () => {
        if (!validateForm()) return;

        button.disabled = true;
        button.innerHTML = '<span class="spinner"></span>Registering...';
        hideError();

        try {
            const formData = {
                app_name: form.app_name.value.trim(),
                webhook_url: form.webhook_url.value.trim()
            };

            const org = form.organization.value.trim();
            if (org) formData.organization = org;

            const response = await fetch('/api/v1/github-app/manifest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const result = await response.json();
            redirectToGitHub(result);
        } catch (error) {
            showError(error.message);
            button.disabled = false;
            button.innerHTML = 'Register GitHub App';
        }
    };

    form.addEventListener('input', validateForm);
    button.addEventListener('click', (e) => {
        e.preventDefault();
        registerApp();
    });

    validateForm();
});
