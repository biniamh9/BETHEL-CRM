(() => {
  const sharedUrl = value => {
    const url = new URL(value || window.location.href, window.location.origin);
    url.searchParams.set('shared', '1');
    return url.toString();
  };

  const copy = async (value, status, message = 'Link copied. Open your social app and paste it into a post.') => {
    try {
      await navigator.clipboard.writeText(value);
      if (status) status.textContent = message;
    } catch (error) {
      window.prompt('Copy this link:', value);
    }
  };

  const share = async ({ title, text, url, status, platform = '' }) => {
    const data = { title: title || document.title, text: text || document.querySelector('meta[name="description"]')?.content || '', url: sharedUrl(url) };
    if (navigator.share) {
      try {
        await navigator.share(data);
        if (status) status.textContent = platform ? `Choose ${platform} from your share menu.` : 'Thanks for sharing.';
        return;
      } catch (error) {
        if (error.name === 'AbortError') return;
      }
    }
    await copy(data.url, status, platform ? `${platform} link copied. Open ${platform} and paste it into your post.` : undefined);
  };

  window.bethelShare = share;

  document.querySelectorAll('[data-share-panel]').forEach(panel => {
    const status = panel.querySelector('[data-share-status]');
    const title = panel.dataset.shareTitle || document.title;
    const text = panel.dataset.shareText || document.querySelector('meta[name="description"]')?.content || '';
    const url = sharedUrl(panel.dataset.shareUrl);
    const facebook = panel.querySelector('[data-share-facebook]');
    if (facebook) facebook.href = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
    panel.querySelector('[data-share-native]')?.addEventListener('click', () => share({ title, text, url, status }));
    panel.querySelector('[data-share-copy]')?.addEventListener('click', () => copy(url, status, 'Link copied.'));
    panel.querySelectorAll('[data-share-platform]').forEach(button => button.addEventListener('click', () => share({ title, text, url, status, platform: button.dataset.sharePlatform })));
  });
})();
