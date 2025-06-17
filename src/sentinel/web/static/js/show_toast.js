export const toastTypes = {
    INFO: 'is-info', // Bulma notification info color
    WARN: 'is-warning', // Bulma notification warning color
    ERROR: 'is-danger', // Bulma notification danger color
};

/**
 * Render a toast notification.
 *
 * @param {string} message The text to display inside the toast.
 * @param {string} [type]  The toast type (use a value from toastTypes). Defaults to INFO.
 * @param {number} [hideAfterMs] Milliseconds until the toast disappears. Defaults to 4000 ms.
 */
export function showToast(message, type = toastTypes.INFO, hideAfterMs = 4000) {
    if (!Object.values(toastTypes).includes(type)) {
        throw new Error(`Invalid toast type: ${type}`);
    }

    const toastElement = document.createElement('div');
    toastElement.classList.add('notification', type, 'toast');
    toastElement.innerText = message;

    document.body.appendChild(toastElement);
    setTimeout(() => toastElement.remove(), hideAfterMs);
} 
