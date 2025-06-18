document.addEventListener('DOMContentLoaded', () => {
    const createForm = document.getElementById('slack-app-create-form');
    const completeForm = document.getElementById('slack-app-complete-form');
    const createButton = document.getElementById('create-app-button');
    const completeButton = document.getElementById('complete-setup-button');

    const createErrorContainer = document.getElementById('create-form-error');
    const createErrorMessage = document.getElementById('create-form-error-message');
    const completeErrorContainer = document.getElementById('complete-form-error');
    const completeErrorMessage = document.getElementById('complete-form-error-message');

    const phase1Container = document.getElementById('phase-1-container');
    const phase2Container = document.getElementById('phase-2-container');
    const successContainer = document.getElementById('success-container');

    const appIdDisplay = document.getElementById('app-id-display');
    const appNameDisplay = document.getElementById('app-name-display');
    const appUserIdDisplay = document.getElementById('app-user-id-display');
    const appLevelTokensLink = document.getElementById('app-level-tokens-link');
    const oauthPermissionsLink = document.getElementById('oauth-permissions-link');

    let appData = null;

    const isValidConfigToken = (token) => {
        return token.startsWith('xoxe');
    };

    const isValidAppToken = (token) => {
        return token.startsWith('xapp-');
    };

    const isValidBotToken = (token) => {
        return token.startsWith('xoxb-');
    };

    const validateCreateForm = () => {
        const appName = createForm.app_name.value.trim();
        const configToken = createForm.config_token.value.trim();
        const isValid = appName && configToken && isValidConfigToken(configToken);
        createButton.disabled = !isValid;
        return isValid;
    };

    const validateCompleteForm = () => {
        const appToken = completeForm.app_token.value.trim();
        const botToken = completeForm.bot_token.value.trim();
        const isValid = appToken && botToken && isValidAppToken(appToken) && isValidBotToken(botToken);
        completeButton.disabled = !isValid;
        return isValid;
    };

    const showCreateError = (message) => {
        createErrorMessage.textContent = message;
        createErrorContainer.classList.add('show');
        createErrorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const hideCreateError = () => {
        createErrorContainer.classList.remove('show');
    };

    const showCompleteError = (message) => {
        completeErrorMessage.textContent = message;
        completeErrorContainer.classList.add('show');
        completeErrorContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    const hideCompleteError = () => {
        completeErrorContainer.classList.remove('show');
    };

    const showPhase2 = (data) => {
        appData = data;
        appIdDisplay.textContent = data.app_id;
        appNameDisplay.textContent = data.app_name;
        appLevelTokensLink.href = `https://api.slack.com/apps/${data.app_id}/general`;
        oauthPermissionsLink.href = `https://api.slack.com/apps/${data.app_id}/install-on-team`;

        // Hide initial info section
        const initialInfoSection = document.getElementById('initial-info-section');
        if (initialInfoSection) {
            initialInfoSection.style.display = 'none';
        }

        phase1Container.style.display = 'none';
        phase2Container.style.display = 'block';
        validateCompleteForm();
    };

    const showSuccess = (data) => {
        appUserIdDisplay.textContent = data.app_user_id;

        phase2Container.style.display = 'none';
        successContainer.style.display = 'block';
    };

    const createSlackApp = async () => {
        if (!validateCreateForm()) return;

        const configToken = createForm.config_token.value.trim();
        if (!isValidConfigToken(configToken)) {
            showCreateError('App Configuration Token must start with "xoxe-" and be valid');
            return;
        }

        createButton.disabled = true;
        createButton.innerHTML = '<span class="spinner"></span>Creating App...';
        hideCreateError();

        try {
            const formData = {
                app_name: createForm.app_name.value.trim(),
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

            showPhase2(result);
        } catch (error) {
            showCreateError(error.message);
            createButton.disabled = false;
            createButton.innerHTML = 'Create Slack App';
        }
    };

    const completeSlackSetup = async () => {
        if (!validateCompleteForm() || !appData) return;

        const appToken = completeForm.app_token.value.trim();
        const botToken = completeForm.bot_token.value.trim();

        if (!isValidAppToken(appToken)) {
            showCompleteError('App-Level Token must start with "xapp-" and be valid');
            return;
        }

        if (!isValidBotToken(botToken)) {
            showCompleteError('Bot User OAuth Token must start with "xoxb-" and be valid');
            return;
        }

        completeButton.disabled = true;
        completeButton.innerHTML = '<span class="spinner"></span>Completing Setup...';
        hideCompleteError();

        try {
            const formData = {
                app_id: appData.app_id,
                app_name: appData.app_name,
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

            showSuccess(result);
        } catch (error) {
            showCompleteError(error.message);
            completeButton.disabled = false;
            completeButton.innerHTML = 'Complete Setup';
        }
    };

    createForm.addEventListener('input', validateCreateForm);
    createButton.addEventListener('click', (e) => {
        e.preventDefault();
        createSlackApp();
    });

    completeForm.addEventListener('input', validateCompleteForm);
    completeButton.addEventListener('click', (e) => {
        e.preventDefault();
        completeSlackSetup();
    });

    validateCreateForm();
});
