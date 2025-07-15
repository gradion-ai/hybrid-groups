document.addEventListener('DOMContentLoaded', () => {
    // Form references
    const githubAppForm = document.getElementById('github-app-form');
    const githubInstallForm = document.getElementById('github-install-form');

    // Button references
    const startConfigButton = document.getElementById('start-configuration-button');
    const registerAppButton = document.getElementById('register-app-button');
    const installAppButton = document.getElementById('install-app-button');
    const completeSetupButton = document.getElementById('complete-setup-button');
    const resetWizardButton = document.getElementById('reset-wizard-button');

    // Error container references
    const errorContainer = document.getElementById('form-error');
    const errorMessage = document.getElementById('form-error-message');
    const installErrorContainer = document.getElementById('install-form-error');
    const installErrorMessage = document.getElementById('install-form-error-message');

    // Phase container references
    const phase1Container = document.getElementById('phase-1-container');
    const phase2Container = document.getElementById('phase-2-container');
    const phase3Container = document.getElementById('phase-3-container');
    const successContainer = document.getElementById('success-container');

    // Progress indicator references
    const progressSteps = document.querySelectorAll('.progress-step');

    // Display element references
    const appCreatedInfo = document.getElementById('app-created-info');
    const appNameDisplay = document.getElementById('app-name-display');
    const webhookUrlDisplay = document.getElementById('webhook-url-display');
    const appNameSuccessDisplay = document.getElementById('app-name-success-display');
    const webhookUrlSuccessDisplay = document.getElementById('webhook-url-success-display');
    const smeeUrlDisplay = document.getElementById('smee-url-display');

    let appData = null;
    let currentPhase = 1;

    // URL validation function
    const isValidUrl = (string) => {
        try {
            const url = new URL(string);
            return ['http:', 'https:'].includes(url.protocol);
        } catch (_) {
            return false;
        }
    };

    // Phase navigation functions
    const updateProgressIndicator = (phase) => {
        progressSteps.forEach((step, index) => {
            if (index + 1 <= phase) {
                step.classList.add('active');
            } else {
                step.classList.remove('active');
            }
        });
    };

    const showPhase = (phase) => {
        // Hide all phases
        const allPhases = [phase1Container, phase2Container, phase3Container, successContainer];
        allPhases.forEach(container => container.style.display = 'none');

        // Show current phase
        switch (phase) {
            case 1:
                phase1Container.style.display = 'block';
                break;
            case 2:
                phase2Container.style.display = 'block';
                window.scrollTo({ top: 0, behavior: 'auto' });
                break;
            case 3:
                phase3Container.style.display = 'block';
                // Show app created info if app was created
                if (appData) {
                    appCreatedInfo.style.display = 'block';
                    appNameDisplay.textContent = appData.app_name;
                    webhookUrlDisplay.textContent = appData.webhook_url;
                }
                window.scrollTo({ top: 0, behavior: 'auto' });
                break;
            case 'success':
                successContainer.style.display = 'block';
                window.scrollTo({ top: 0, behavior: 'auto' });
                if (appData) {
                    appNameSuccessDisplay.textContent = appData.app_name;
                    webhookUrlSuccessDisplay.textContent = appData.webhook_url;
                    if (smeeUrlDisplay) {
                        smeeUrlDisplay.textContent = appData.webhook_url;
                    }
                    // Format the app name for the example (lowercase, spaces to hyphens, special chars removed)
                    const appNameExample = document.getElementById('app-name-example');
                    if (appNameExample && appData.app_name) {
                        const formattedName = appData.app_name
                            .toLowerCase()
                            .replace(/\s+/g, '-')
                            .replace(/[^a-z0-9-]/g, '');
                        appNameExample.textContent = formattedName;
                    }
                }
                break;
        }

        currentPhase = phase;
        if (phase !== 'success') {
            updateProgressIndicator(phase);
        }
    };

    // Form validation functions
    const validateForm = () => {
        const appName = githubAppForm.app_name.value.trim();
        const isValid = appName;
        registerAppButton.disabled = !isValid;
        return isValid;
    };

    const validateInstallForm = () => {
        const installationId = githubInstallForm.installation_id.value.trim();
        const isValid = installationId && /^\d+$/.test(installationId);
        completeSetupButton.disabled = !isValid;
        return isValid;
    };

    // Error display functions
    const showError = (message) => {
        errorMessage.textContent = message;
        errorContainer.classList.add('show');
        errorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const hideError = () => {
        errorContainer.classList.remove('show');
    };

    const showInstallError = (message) => {
        installErrorMessage.textContent = message;
        installErrorContainer.classList.add('show');
        installErrorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const hideInstallError = () => {
        installErrorContainer.classList.remove('show');
    };

    // GitHub redirect function
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

    // API call function
    const registerApp = async () => {
        if (!validateForm()) return;

        registerAppButton.disabled = true;
        registerAppButton.innerHTML = '<span class="spinner"></span>Creating App...';
        hideError();

        try {
            const formData = {
                app_name: githubAppForm.app_name.value.trim()
            };

            const org = githubAppForm.organization.value.trim();
            if (org) formData.organization = org;

            const response = await fetch('/api/v1/github-app/manifest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            // Store app data in session storage for later phases
            appData = {
                app_name: formData.app_name,
                organization: formData.organization || null,
                ...result
            };

            // Store in session storage to persist across redirect
            sessionStorage.setItem('github_app_data', JSON.stringify(appData));

            // Redirect to GitHub for app creation
            redirectToGitHub(result);
        } catch (error) {
            showError(error.message);
            registerAppButton.disabled = false;
            registerAppButton.innerHTML = 'Create GitHub App';
        }
    };

    const completeSetup = async () => {
        if (!validateInstallForm()) return;

        const installationId = githubInstallForm.installation_id.value.trim();
        if (!installationId || !/^\d+$/.test(installationId)) {
            showInstallError('Installation ID must be a number');
            return;
        }

        completeSetupButton.disabled = true;
        completeSetupButton.innerHTML = '<span class="spinner"></span>Completing Setup...';
        hideInstallError();

        try {
            const formData = {
                app_id: appData.app_id || null,
                app_name: appData.app_name,
                installation_id: installationId
            };

            const response = await fetch('/api/v1/github-app/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `HTTP ${response.status}`);
            }

            if (!result.success) {
                throw new Error(result.error || 'Failed to complete setup');
            }

            // Update app data with installation ID
            if (appData) {
                appData.installation_id = installationId;
            }

            // Clear session storage
            sessionStorage.removeItem('github_app_data');

            showPhase('success');
        } catch (error) {
            showInstallError(error.message);
            completeSetupButton.disabled = false;
            completeSetupButton.innerHTML = 'Complete Setup';
        }
    };

    const openGitHubInstall = () => {
        if (appData && (appData.installation_url || appData.app_slug)) {
            // Use the installation URL from the backend if available
            let installUrl;

            if (appData.installation_url) {
                installUrl = appData.installation_url;
            } else if (appData.app_slug) {
                // Fallback: construct URL from app slug
                installUrl = `https://github.com/apps/${appData.app_slug}/installations/new`;
            }

            if (installUrl) {
                window.open(installUrl, '_blank');
            } else {
                showInstallError('Installation URL not available. Please complete the app creation first.');
            }
        } else {
            showInstallError('App information not available. Please complete the app creation first.');
        }
    };

    // Reset wizard function
    const resetWizard = () => {
        // Clear all data
        appData = null;
        sessionStorage.removeItem('github_app_data');

        // Reset forms
        if (githubAppForm) {
            githubAppForm.reset();
        }
        if (githubInstallForm) {
            githubInstallForm.reset();
        }

        // Reset button states
        registerAppButton.disabled = true;
        registerAppButton.innerHTML = 'Create GitHub App';
        completeSetupButton.disabled = true;
        completeSetupButton.innerHTML = 'Complete Setup';

        // Hide all errors
        hideError();
        hideInstallError();

        // Hide app created info
        appCreatedInfo.style.display = 'none';

        // Go to phase 1
        showPhase(1);
    };

    // Event listeners
    startConfigButton.addEventListener('click', () => {
        showPhase(2);
    });

    resetWizardButton.addEventListener('click', (e) => {
        e.preventDefault();
        resetWizard();
    });

    registerAppButton.addEventListener('click', (e) => {
        e.preventDefault();
        registerApp();
    });

    if (installAppButton) {
        installAppButton.addEventListener('click', (e) => {
            e.preventDefault();
            openGitHubInstall();
        });
    }

    completeSetupButton.addEventListener('click', (e) => {
        e.preventDefault();
        completeSetup();
    });

    // Input validation event listeners
    if (githubAppForm) {
        githubAppForm.addEventListener('input', validateForm);
    }

    if (githubInstallForm) {
        githubInstallForm.addEventListener('input', validateInstallForm);
    }

    // Check if returning from GitHub with success parameters
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('setup') && urlParams.get('setup') === 'complete') {
        // User is returning from successful GitHub app creation
        // The backend has already processed the callback and saved credentials

        // Retrieve stored app data
        const storedData = sessionStorage.getItem('github_app_data');
        if (storedData) {
            appData = JSON.parse(storedData);

            // Extract app info from URL if available
            const appId = urlParams.get('app_id');
            const appSlug = urlParams.get('app_slug');
            const appName = urlParams.get('app_name');
            const installationUrl = urlParams.get('installation_url');
            const webhookUrl = urlParams.get('webhook_url');

            if (appId) {
                appData.app_id = appId;
            }
            if (appSlug) {
                appData.app_slug = appSlug;
            }
            if (appName) {
                appData.app_name = appName;  // Update with actual name from GitHub
            }
            if (installationUrl) {
                appData.installation_url = installationUrl;
            }
            if (webhookUrl) {
                appData.webhook_url = webhookUrl;
            }

            // Update session storage
            sessionStorage.setItem('github_app_data', JSON.stringify(appData));

            // Show installation phase
            showPhase(3);
        } else {
            // No stored data, something went wrong
            showPhase(1);
        }
    } else if (urlParams.has('error')) {
        // GitHub returned an error
        const error = urlParams.get('error');
        const errorDescription = urlParams.get('error_description') || 'Unknown error';
        showPhase(2);
        showError(`GitHub error: ${errorDescription}`);
    } else {
        // Check for stored app data (in case of page refresh)
        const storedData = sessionStorage.getItem('github_app_data');
        if (storedData) {
            appData = JSON.parse(storedData);
            // If we have app_id, show installation phase
            if (appData.app_id) {
                showPhase(3);
            } else {
                showPhase(2);
            }
        } else {
            // Normal start
            showPhase(1);
        }
    }
});
