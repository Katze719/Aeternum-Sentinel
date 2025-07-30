import { showToast, toastTypes } from './show_toast.js';

window.showToast = showToast;
window.toastTypes = toastTypes;

document.addEventListener('DOMContentLoaded', () => {
    // Toast handling
    const params = new URLSearchParams(window.location.search);
    const msgKey = params.get('msg');

    const messages = {
        login_required: 'Bitte einloggen, um fortzufahren.',
        guild_not_found: 'Guild nicht gefunden.',
        user_not_in_guild: 'Du bist nicht Mitglied dieser Guild.',
        insufficient_perms: 'Administratorrechte erforderlich.',
    };

    if (msgKey) {
        if (!Object.prototype.hasOwnProperty.call(messages, msgKey)) {
            showToast(`Fehler, unbekannter key: ${msgKey}`, toastTypes.ERROR);
        } else {
            showToast(messages[msgKey], toastTypes.ERROR);
        }
    }

    // Activate Choices.js on any select with data-choices attribute
    document.querySelectorAll('select[data-choices]').forEach((choiceElement) => {
        // eslint-disable-next-line no-undef
        new Choices(choiceElement, { searchEnabled: true, itemSelectText: '', renderSelectedChoices: 'always', removeItemButton: true });
    });
}); 
