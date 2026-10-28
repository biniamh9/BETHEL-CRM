(() => {
  const inputs = [...document.querySelectorAll('input[type="file"][data-optimize-image]')];
  if (!inputs.length || !window.createImageBitmap || !window.DataTransfer) return;
  const toBlob = (canvas, quality) => new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
  const optimize = async file => {
    const bitmap = await createImageBitmap(file, {imageOrientation: 'from-image'});
    let width = bitmap.width, height = bitmap.height;
    const scale = Math.min(1, 2400 / Math.max(width, height));
    width = Math.round(width * scale); height = Math.round(height * scale);
    const canvas = document.createElement('canvas'), context = canvas.getContext('2d', {alpha: false});
    const render = () => {
      canvas.width = width; canvas.height = height;
      context.fillStyle = '#fff'; context.fillRect(0, 0, width, height);
      context.drawImage(bitmap, 0, 0, width, height);
    };
    render(); let quality = .88, blob = await toBlob(canvas, quality);
    while (blob.size > 950 * 1024 && quality > .52) { quality -= .07; blob = await toBlob(canvas, quality); }
    while (blob.size > 950 * 1024 && Math.max(width, height) > 900) {
      width = Math.round(width * .82); height = Math.round(height * .82); render(); blob = await toBlob(canvas, .78);
    }
    bitmap.close();
    if (!blob || blob.size > 1024 * 1024) throw new Error(`${file.name} could not be reduced below 1 MB.`);
    return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg', {type: 'image/jpeg'});
  };
  new Set(inputs.map(input => input.form).filter(Boolean)).forEach(form => form.addEventListener('submit', async event => {
    if (form.dataset.imagesOptimized === '1') return;
    const selected = inputs.filter(input => input.form === form && input.files.length);
    if (!selected.length) return;
    event.preventDefault();
    const submitter = event.submitter, originalText = submitter?.textContent;
    if (submitter) { submitter.disabled = true; submitter.textContent = 'Optimizing image…'; }
    try {
      for (const input of selected) {
        const transfer = new DataTransfer();
        for (const file of [...input.files]) transfer.items.add(await optimize(file));
        input.files = transfer.files;
      }
      form.dataset.imagesOptimized = '1';
      form.requestSubmit(submitter || undefined);
    } catch (error) {
      if (submitter) { submitter.disabled = false; submitter.textContent = originalText; }
      window.alert(error.message);
    }
  }));
})();
