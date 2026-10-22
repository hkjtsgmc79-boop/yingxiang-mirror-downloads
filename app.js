(() => {
  'use strict';
  const field = document.getElementById('share-link');
  const button = document.getElementById('copy-link');
  const status = document.getElementById('copy-status');
  const allowedHttps = value => typeof value === 'string' && /^https:\/\//.test(value);
  const setLink = (id, value) => {
    if (allowedHttps(value)) document.getElementById(id).href = value;
  };

  fetch('./entry-config.json', {cache: 'no-cache'})
    .then(response => {
      if (!response.ok) throw new Error('Configuration unavailable');
      return response.json();
    })
    .then(config => {
      const share = config.short_url || config.share_url || config.page_url;
      if (allowedHttps(share)) field.value = share;
      setLink('apk-download', config.apk_url);
      setLink('release-link', config.release_url);
      setLink('install-link', config.install_url);
      if (typeof config.version === 'string') document.getElementById('version-name').textContent = config.version;
      if (typeof config.size_label === 'string') document.getElementById('size-label').textContent = config.size_label;
    })
    .catch(() => {
      // Static links and version details remain usable without JavaScript configuration.
    });

  button.addEventListener('click', async () => {
    const value = field.value;
    let copied = false;
    if (window.isSecureContext && navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(value);
        copied = true;
      } catch (_) {
        // Keep a direct-selection fallback for browsers that deny clipboard access.
      }
    }
    if (!copied) {
      field.focus();
      field.select();
      field.setSelectionRange(0, value.length);
      try { copied = document.execCommand('copy'); } catch (_) {}
    }
    status.textContent = copied ? '链接已复制，可直接分享。' : '请长按或选中上方链接复制。';
    button.textContent = copied ? '已复制' : '复制';
  });
})();
