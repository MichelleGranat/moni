const TOKEN_KEY = 'moni_id_token';

window.addEventListener('load', initializeLogin);

async function initializeLogin() {
  const status = document.getElementById('pageStatus');

  let clientId = '';
  try {
    const response = await fetch('/api/v1/auth/config');
    clientId = (await response.json())?.client_id || '';
  } catch {
    setStatus(status, 'לא ניתן להתחבר לשרת.', true);
    return;
  }

  if (!clientId) {
    setStatus(status, 'ההתחברות לא הוגדרה בשרת. יש למלא MONI_WEB_CLIENT_ID בקובץ .env.', true);
    return;
  }
  if (!window.google?.accounts?.id) {
    setStatus(status, 'לא ניתן לטעון את ההתחברות של Google.', true);
    return;
  }

  google.accounts.id.initialize({ client_id: clientId, callback: handleCredential });
  google.accounts.id.renderButton(document.getElementById('googleButton'), {
    theme: 'outline',
    size: 'large',
    locale: 'he'
  });
}

async function handleCredential({ credential }) {
  const status = document.getElementById('pageStatus');
  setStatus(status, '');

  const response = await fetch('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${credential}` }
  });

  if (response.ok) {
    try {
      sessionStorage.setItem(TOKEN_KEY, credential);
    } catch {}
    window.location.replace('index.html');
    return;
  }

  google.accounts.id.disableAutoSelect();
  const data = await response.json().catch(() => null);
  setStatus(status, data?.message || 'ההתחברות נכשלה.', true);
}

function setStatus(element, message, isError = false) {
  if (!element) return;
  element.textContent = message;
  element.style.color = isError ? '#c62828' : '#2e7d32';
}
