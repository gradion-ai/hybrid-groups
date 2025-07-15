document.addEventListener('DOMContentLoaded', () => {
    // Static app name
    const APP_NAME = "Hybrid Groups";

    // Form references
    const configForm = document.getElementById('slack-app-config-form');
    const appLevelForm = document.getElementById('slack-app-level-form');
    const botTokenForm = document.getElementById('slack-bot-token-form');

    // Button references
    const startConfigButton = document.getElementById('start-configuration-button');
    const configTokenNextButton = document.getElementById('config-token-next-button');
    const appTokenNextButton = document.getElementById('app-token-next-button');
    const completeSetupButton = document.getElementById('complete-setup-button');

    // Error container references
    const configErrorContainer = document.getElementById('config-form-error');
    const configErrorMessage = document.getElementById('config-form-error-message');
    const appLevelErrorContainer = document.getElementById('app-level-form-error');
    const appLevelErrorMessage = document.getElementById('app-level-form-error-message');
    const botTokenErrorContainer = document.getElementById('bot-token-form-error');
    const botTokenErrorMessage = document.getElementById('bot-token-form-error-message');

    // Phase container references
    const phase1Container = document.getElementById('phase-1-container');
    const phase2Container = document.getElementById('phase-2-container');
    const phase3Container = document.getElementById('phase-3-container');
    const phase4Container = document.getElementById('phase-4-container');
    const successContainer = document.getElementById('success-container');

    // Progress indicator references
    const progressSteps = document.querySelectorAll('.progress-step');

    // Display element references
    const appIdDisplay = document.getElementById('app-id-display');
    const appCreatedInfo = document.getElementById('app-created-info');
    const appUserIdDisplay = document.getElementById('app-user-id-display');
    const appLevelTokensButton = document.getElementById('app-level-tokens-button');
    const installAppButton = document.getElementById('install-app-button');

    let appData = null;
    let currentPhase = 1;

    // Token validation functions
    const isValidConfigToken = (token) => {
        return token.startsWith('xoxe');
    };

    const isValidAppToken = (token) => {
        return token.startsWith('xapp-');
    };

    const isValidBotToken = (token) => {
        return token.startsWith('xoxb-');
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
        const allPhases = [phase1Container, phase2Container, phase3Container, phase4Container, successContainer];
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
                    appIdDisplay.textContent = appData.app_id;
                }
                window.scrollTo({ top: 0, behavior: 'auto' });
                break;
            case 4:
                phase4Container.style.display = 'block';
                window.scrollTo({ top: 0, behavior: 'auto' });
                break;
            case 'success':
                successContainer.style.display = 'block';
                break;
        }

        currentPhase = phase;
        if (phase !== 'success') {
            updateProgressIndicator(phase);
        }
    };

    // Form validation functions
    const validateConfigForm = () => {
        const configToken = configForm.config_token.value.trim();
        const isValid = configToken && isValidConfigToken(configToken);
        configTokenNextButton.disabled = !isValid;
        return isValid;
    };

    const validateAppLevelForm = () => {
        const appToken = appLevelForm.app_token.value.trim();
        const isValid = appToken && isValidAppToken(appToken);
        appTokenNextButton.disabled = !isValid;
        return isValid;
    };

    const validateBotTokenForm = () => {
        const botToken = botTokenForm.bot_token.value.trim();
        const isValid = botToken && isValidBotToken(botToken);
        completeSetupButton.disabled = !isValid;
        return isValid;
    };

    // Error display functions
    const showConfigError = (message) => {
        configErrorMessage.textContent = message;
        configErrorContainer.classList.add('show');
        configErrorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const hideConfigError = () => {
        configErrorContainer.classList.remove('show');
    };

    const showAppLevelError = (message) => {
        appLevelErrorMessage.textContent = message;
        appLevelErrorContainer.classList.add('show');
        appLevelErrorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const hideAppLevelError = () => {
        appLevelErrorContainer.classList.remove('show');
    };

    const showBotTokenError = (message) => {
        botTokenErrorMessage.textContent = message;
        botTokenErrorContainer.classList.add('show');
        botTokenErrorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const hideBotTokenError = () => {
        botTokenErrorContainer.classList.remove('show');
    };

    // API call functions
    const createSlackApp = async () => {
        if (!validateConfigForm()) return;

        const configToken = configForm.config_token.value.trim();
        if (!isValidConfigToken(configToken)) {
            showConfigError('App Configuration Token must start with "xoxe-" and be valid');
            return;
        }

        configTokenNextButton.disabled = true;
        configTokenNextButton.innerHTML = '<span class="spinner"></span>Creating App...';
        hideConfigError();

        try {
            const formData = {
                app_name: APP_NAME,
                config_token: configToken
            };

            const response = await fetch('/api/v1/slack-app/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `HTTP ${response.status}`);
            }

            if (!result.success) {
                throw new Error(result.error || 'Failed to create Slack app');
            }

            appData = result;
            showPhase(3);
        } catch (error) {
            showConfigError(error.message);
            configTokenNextButton.disabled = false;
            configTokenNextButton.innerHTML = 'Next';
        }
    };

    const completeSlackSetup = async () => {
        if (!validateBotTokenForm() || !appData) return;

        const appToken = appLevelForm.app_token.value.trim();
        const botToken = botTokenForm.bot_token.value.trim();

        if (!isValidAppToken(appToken)) {
            showBotTokenError('App-Level Token must start with "xapp-" and be valid');
            return;
        }

        if (!isValidBotToken(botToken)) {
            showBotTokenError('Bot User OAuth Token must start with "xoxb-" and be valid');
            return;
        }

        completeSetupButton.disabled = true;
        completeSetupButton.innerHTML = '<span class="spinner"></span>Completing Setup...';
        hideBotTokenError();

        try {
            const formData = {
                app_id: appData.app_id,
                app_name: APP_NAME,
                app_token: appToken,
                bot_token: botToken
            };

            const response = await fetch('/api/v1/slack-app/complete', {
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

            appUserIdDisplay.textContent = result.app_user_id;
            showPhase('success');
        } catch (error) {
            showBotTokenError(error.message);
            completeSetupButton.disabled = false;
            completeSetupButton.innerHTML = 'Complete Setup';
        }
    };

    // Event listeners
    startConfigButton.addEventListener('click', () => {
        showPhase(2);
    });

    configTokenNextButton.addEventListener('click', (e) => {
        e.preventDefault();
        createSlackApp();
    });

    appTokenNextButton.addEventListener('click', (e) => {
        e.preventDefault();
        if (validateAppLevelForm()) {
            showPhase(4);
        }
    });

    completeSetupButton.addEventListener('click', (e) => {
        e.preventDefault();
        completeSlackSetup();
    });

    // Input validation event listeners
    if (configForm) {
        configForm.addEventListener('input', validateConfigForm);
    }

    if (appLevelForm) {
        appLevelForm.addEventListener('input', validateAppLevelForm);
    }

    if (botTokenForm) {
        botTokenForm.addEventListener('input', validateBotTokenForm);
    }

    // Click handler for app-level tokens button
    if (appLevelTokensButton) {
        appLevelTokensButton.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (!appData || !appData.app_id) {
                return false;
            }

            // Open the URL in a new tab
            const url = `https://api.slack.com/apps/${appData.app_id}/general?selected=app_level_tokens`;
            window.open(url, '_blank');
            return false;
        });
    }

    // Click handler for install app button
    if (installAppButton) {
        installAppButton.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (!appData || !appData.app_id) {
                return false;
            }

            // Open the URL in a new tab
            const url = `https://api.slack.com/apps/${appData.app_id}/install-on-team`;
            window.open(url, '_blank');
            return false;
        });
    }
});
